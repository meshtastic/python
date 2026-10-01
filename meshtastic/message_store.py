"""message_store.py

Client-side message history for the Meshtastic CLI, in small pieces:

  MessageSettings  the persistent on/off setting (config.json). Always cheap
                   to create; used even when logging is off.
  MessageLog       the JSONL file (messages.jsonl): append and read. Reading
                   works whether or not logging is currently on.
  MessageStore     the pubsub listener that captures messages and writes them
                   through a MessageLog. Only create it when logging is on.
  print_messages   display of stored messages (--show-messages). Lives at
                   module level, NOT on MessageStore, because showing history
                   must work when no store exists (logging off, no radio).

Typical wiring in the CLI:

    enabled = ...  # from --messages: saved setting, or True for "live"

    store = None
    if enabled:
        store = MessageStore(MessageLog())   # subscribe BEFORE the interface
    interface = SerialInterface(...)         # is created, and keep `store`
                                             # referenced until exit
    ...
    interface.sendText("hi")
    if store:
        store.log_sent("hi")

    # --show-messages all (local only, no connection needed)
    print_messages()
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, TextIO

from pubsub import pub

ENV_DIR = "MESHTASTIC_MESSAGES_DIR"  # override, mainly for tests
CONFIG_NAME = "config.json"
LOG_NAME = "messages.jsonl"
TEXT_PORT = "TEXT_MESSAGE_APP"
BROADCAST_NUM = 0xFFFFFFFF


def _warn(msg: str) -> None:
    print(f"Warning: {msg}", file=sys.stderr)


def _data_dir(directory: Optional[Path] = None) -> Path:
    if directory is not None:
        return Path(directory)
    if os.environ.get(ENV_DIR):
        return Path(os.environ[ENV_DIR])
    return Path.home() / ".meshtastic"


def _tighten_permissions(fd: int) -> None:
    """The 0o600 passed to os.open only applies when the file is created, so
    a file that already existed with looser permissions is tightened here.
    Best effort; no-op where the OS has no POSIX permissions."""
    if os.name != "posix":
        return
    
    mode = stat.S_IMODE(os.fstat(fd).st_mode)

    if mode & 0o077:
        os.fchmod(fd, 0o600)   # let OSError propagate -- MessageLog.append will catch


def _ensure_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)


def hops_from_packet(packet: dict) -> Optional[int]:
    """Hops traveled = hopStart - hopLimit, when both are present.
    (Older firmware doesn't send hopStart, so this can be None.)"""
    hop_start = packet.get("hopStart")
    hop_limit = packet.get("hopLimit")
    if hop_start is not None and hop_limit is not None:
        try:
            return max(0, int(hop_start) - int(hop_limit))
        except (TypeError, ValueError):
            return None
    return None


def _node_id(packet: dict, id_key: str, num_key: str) -> str:
    """'!xxxxxxxx' style id for a packet's sender/recipient.

    fromId/toId can be present but None when the node isn't in the node
    database yet, so fall back to formatting the numeric from/to.
    """
    nid = packet.get(id_key)
    if nid:
        return str(nid)
    num = packet.get(num_key)
    if isinstance(num, int):
        return "^all" if num == BROADCAST_NUM else f"!{num:08x}"
    return "unknown"


def normalize_node_id(dest: Any, my_id: Optional[str] = None) -> str:
    """Canonical form of a user-supplied destination: '!xxxxxxxx' or '^all'.

    Accepts '^all', '^local' (our own node, if my_id is known), '!hex' in any
    case, '0x...' hex, a decimal node number, or an int. Anything it can't
    make sense of is returned unchanged rather than guessed at.
    """
    if dest is None:
        return "^all"
    num = None
    if isinstance(dest, int) and not isinstance(dest, bool):
        num = dest
    else:
        text = str(dest).strip()
        if text == "^all":
            return "^all"
        if text == "^local":
            return my_id or "^local"
        try:
            if text.startswith("!"):
                num = int(text[1:], 16)
            elif text.lower().startswith("0x"):
                num = int(text, 16)
            elif text.isdigit():
                num = int(text)
        except ValueError:
            num = None
        if num is None:
            return text
    if not 0 <= num <= BROADCAST_NUM:
        return str(dest)
    return "^all" if num == BROADCAST_NUM else f"!{num:08x}"


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------


@dataclass
class Message:
    """A single sent or received text message."""

    from_id: str
    to_id: str
    timestamp: float  # UTC epoch seconds
    text: Optional[str] = None
    port: str = TEXT_PORT
    channel: int = 0
    direction: str = "received"  # "received" or "sent"
    packet_id: Optional[int] = None
    rx_snr: Optional[float] = None
    rx_rssi: Optional[int] = None
    from_name: Optional[str] = None  # sender's name at the time, if known
    hops: Optional[int] = None
    my_id: Optional[str] = None  # our node id when logged, so display can say "You"

    @classmethod
    def from_packet(cls, packet: dict) -> "Message":
        """Build a Message from a raw pubsub packet dict."""
        decoded = packet.get("decoded") or {}
        return cls(
            from_id=_node_id(packet, "fromId", "from"),
            to_id=_node_id(packet, "toId", "to"),
            # rxTime can be missing or 0 if the radio has no clock
            timestamp=float(packet.get("rxTime") or time.time()),
            text=decoded.get("text"),
            port=decoded.get("portnum", "UNKNOWN_APP"),
            # proto3 omits default values, so a missing channel means 0
            channel=int(packet.get("channel", 0) or 0),
            packet_id=packet.get("id"),
            rx_snr=packet.get("rxSnr"),
            rx_rssi=packet.get("rxRssi"),
            hops=hops_from_packet(packet),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Tolerant of unknown keys, so older/newer log lines still load."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


# ---------------------------------------------------------------------------
# Settings (config.json)
# ---------------------------------------------------------------------------


class MessageSettings:
    """Persistent client setting: is message logging on?"""

    def __init__(self, directory: Optional[Path] = None) -> None:
        self.dir = _data_dir(directory)
        self.path = self.dir / CONFIG_NAME

    def _load(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def is_enabled(self) -> bool:
        """Saved setting. Missing or corrupt config means off."""
        return self._load().get("messages_enabled") is True

    def set_enabled(self, value: bool) -> bool:
        """Persist the setting. Returns True if it was saved."""
        try:
            _ensure_dir(self.dir)
            data = self._load()  # keep any other keys
            data["messages_enabled"] = bool(value)

            # atomic write: temp file in the same dir, then replace
            fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".config-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp, self.path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
            return True
        except OSError as e:
            _warn(f"could not save message setting ({e})")
            return False


# ---------------------------------------------------------------------------
# Log (messages.jsonl)
# ---------------------------------------------------------------------------


class MessageLog:
    """Append-only JSONL file of messages. This is the backend to swap out
    if you ever move to sqlite: keep append() and iter_messages()."""

    def __init__(self, directory: Optional[Path] = None) -> None:
        self.dir = _data_dir(directory)
        self.path = self.dir / LOG_NAME

    def append(self, msg: Message) -> bool:
        """Append one record as a single JSON line. Never raises."""
        try:
            _ensure_dir(self.dir)

            # Reject if any path component is a symlink
            path = Path(self.path).resolve(strict=False)
            for parent in [path] + list(path.parents):
                if parent.exists() and parent.is_symlink():
                    _warn(f"refusing to log: symlink in path ({parent})")

            line = json.dumps(msg.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"

            # Open with O_NOFOLLOW where available (prevents following a symlink
            # that appears between the check above and the open call)
            flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW

            fd = os.open(str(path), flags, 0o600)
            try:
                with os.fdopen(fd, "ab") as f:
                    _tighten_permissions(f.fileno())
                    f.write(line.encode("utf-8"))
            except Exception:
                # fd is already owned by the with-statement if fdopen succeeded;
                # if fdopen itself failed we still need to close the raw fd
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise

            return True
        
        except (OSError, TypeError, ValueError) as e:
            # O_NOFOLLOW raises OSError (ELOOP) when the final component is a symlink
            _warn(f"could not log message ({e})")
            return False

    def iter_messages(self) -> Iterator[Message]:
        """Yield stored messages in file order, skipping unreadable lines."""
        try:
            f = open(self.path, "r", encoding="utf-8")
        except OSError:
            return
        with f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        yield Message.from_dict(data)
                except (ValueError, TypeError):
                    continue  # e.g. a partially written last line


# ---------------------------------------------------------------------------
# Store (pubsub capture)
# ---------------------------------------------------------------------------


class MessageStore:
    """Captures messages from pubsub and writes them through a MessageLog.

    Create it only when logging is enabled. It subscribes immediately, so
    build it before the interface so no early packets are missed, and keep a
    reference to it: pypubsub holds only a weak reference to the bound
    method, so a dropped store silently stops receiving.
    """

    def __init__(
        self,
        log: Optional[MessageLog] = None,
        interface=None,
        my_id: Optional[str] = None,
        text_only: bool = True, #Save Normal Chat Messages Only
    ) -> None:
        self.log = log if log is not None else MessageLog()
        self.interface = interface
        self._my_id = my_id
        self.text_only = text_only
        self._seen = set()  # (from_id, packet_id) seen this run
        pub.subscribe(self._on_receive, "meshtastic.receive")

    def close(self) -> None:
        """Detach from pubsub."""
        try:
            pub.unsubscribe(self._on_receive, "meshtastic.receive")
        except Exception:  # already unsubscribed
            pass

    @property
    def my_id(self) -> Optional[str]:
        """Our own node id in '!xxxxxxxx' form, resolved lazily because the
        interface usually isn't connected yet when the store is created."""
        if self._my_id is None and self.interface is not None:
            num = None
            try:
                num = self.interface.localNode.nodeNum
            except AttributeError:
                pass
            if not isinstance(num, int) or num < 0:
                try:
                    num = self.interface.myInfo.my_node_num
                except AttributeError:
                    num = None
            if isinstance(num, int) and num >= 0:
                self._my_id = f"!{num:08x}"
        return self._my_id

    @staticmethod
    def _lookup_name(interface, num) -> Optional[str]:
        """Sender's long/short name from the live node database, if known."""
        if interface is None or num is None:
            return None
        try:
            node = (interface.nodesByNum or {}).get(num) or {}
            user = node.get("user") or {}
            return user.get("longName") or user.get("shortName")
        except Exception:
            return None

    def _on_receive(self, packet: dict, interface) -> None:
        """pubsub callback for every incoming packet. Must never raise."""
        try:
            if self.interface is None:
                self.interface = interface  # learn it from the first packet
            elif interface is not None and interface is not self.interface:
                return  # a packet from some other interface: not ours to log
            msg = Message.from_packet(packet)
            if self.text_only and msg.port != TEXT_PORT:
                return
            if msg.packet_id is not None:
                key = (msg.from_id, msg.packet_id)
                if key in self._seen:
                    return  # same packet delivered twice this run
                self._seen.add(key)
            msg.from_name = self._lookup_name(interface or self.interface, packet.get("from"))
            msg.my_id = self.my_id
            self.add(msg)
        except Exception as e:  # logging must not break the receive path
            _warn(f"message logging error ({e})")

    def add(self, msg: Message) -> bool:
        """Persist one message."""
        return self.log.append(msg)

    def log_sent(
        self,
        text: str,
        destination_id: str = "^all",
        channel: int = 0,
        port: str = TEXT_PORT,
    ) -> bool:
        """Record an outgoing message. sendText() doesn't fire
        "meshtastic.receive", so call this right after sending."""
        my_id = self.my_id
        return self.add(
            Message(
                from_id=my_id or "self",
                my_id=my_id,
                to_id=normalize_node_id(destination_id, my_id),
                timestamp=time.time(),
                text=text,
                port=port,
                channel=channel,
                direction="sent",
            )
        )

    # ---- reading (thin wrappers; work off the file, in order) ------------

    def all(self) -> List[Message]:
        """Every stored message, in the order it was written."""
        return list(self.log.iter_messages())

    def for_node(self, node_id: str) -> List[Message]:
        """Messages sent by or to a node id, in the order written."""
        return [m for m in self.log.iter_messages() if node_id in (m.from_id, m.to_id)]


# ---------------------------------------------------------------------------
# Display (--show-messages). Plain text only: no extra dependencies, and it
# works offline because everything it needs was saved at log time.
# ---------------------------------------------------------------------------


def _clean(value: Any) -> str:
    """Make untrusted text safe to print: escape control characters (ESC,
    newlines, CR, ...) and other non-printable characters such as bidi
    overrides, so a received message can't forge extra log lines or drive the
    terminal. Display only: the stored values are left exactly as received.
    Side effect: zero-width joiners inside emoji sequences also get escaped."""
    text = "" if value is None else str(value)
    return "".join(
        ch if ch.isprintable() else ch.encode("unicode_escape").decode("ascii")
        for ch in text
    )


def _label(node_id: str, name: Optional[str], my_id: Optional[str]) -> str:
    """'You (!id)' for our own node, 'Name (!id)' when a name is known,
    otherwise just the id. Records logged before my_id existed can't say."""
    node_id = _clean(node_id)
    if my_id and node_id == _clean(my_id):
        return f"You ({node_id})"
    if name and name != node_id:
        return f"{_clean(name)} ({node_id})"
    return node_id


def format_message(msg: Message) -> str:
    """One line per message:

    2026-09-30 14:03:22  Alice (!a1b2c3d4) -> ^all  [ch0 | 1 hop | SNR 5.5]: hello
    2026-09-30 14:05:10  Alice (!a1b2c3d4) -> You (!1ba5fa0c)  [ch0]: hi (a DM to us)
    """
    try:
        when = datetime.fromtimestamp(msg.timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError, TypeError):
        when = "unknown time"

    if msg.direction == "sent":
        who = f"You ({_clean(msg.my_id)})" if msg.my_id else "You"
    else:
        who = _label(msg.from_id, msg.from_name, msg.my_id)
    dest = _label(msg.to_id, None, msg.my_id)

    meta = [f"ch{msg.channel}"]
    if msg.port and msg.port != TEXT_PORT:
        meta.insert(0, _clean(msg.port))
    if msg.hops is not None:
        meta.append(f"{msg.hops} hop" + ("" if msg.hops == 1 else "s"))
    if msg.rx_snr is not None:
        meta.append(f"SNR {msg.rx_snr}")
    if msg.rx_rssi is not None:
        meta.append(f"RSSI {msg.rx_rssi}")

    return f"{when}  {who} -> {dest}  [{' | '.join(meta)}]: {_clean(msg.text)}"


def print_messages(log: Optional[MessageLog] = None, out: Optional[TextIO] = None) -> int:
    """Print every stored message, oldest first. Returns how many were shown."""
    log = log if log is not None else MessageLog()
    out = out if out is not None else sys.stdout
    count = 0
    for msg in log.iter_messages():
        print(format_message(msg), file=out)
        count += 1
    if count == 0:
        print(f"No stored messages ({log.path}).", file=out)
    return count