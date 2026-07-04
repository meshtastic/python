"""Shared helpers for meshtasticd-backed smoke tests.

Both ``test_smokevirt`` (single node) and ``test_smokemesh`` (multi-node
chain) use these helpers to drive the ``meshtastic`` CLI against real
``meshtasticd`` simulator instances and then verify the resulting firmware
state through the Python library's ``TCPInterface``.

Verifying through the library (rather than regex on CLI stdout) is the
core design choice: it makes tests robust against CLI wording changes
while still exercising both the CLI argparse path and the firmware I/O
path of every feature.
"""
from __future__ import annotations

import logging
import shlex
import socket
import subprocess
import sys
import time
from typing import Callable, List, Optional, Tuple

from pubsub import pub  # type: ignore[import-untyped]

from meshtastic.tcp_interface import TCPInterface

logger = logging.getLogger(__name__)

# Pause between a CLI command finishing and a verification interface
# opening, to let the firmware flush its TCP bookkeeping. Keeps the
# simulator happy when many short-lived connections are happening.
PAUSE_AFTER_CLI = 0.2


# ---------------------------------------------------------------------------
# CLI invocation
# ---------------------------------------------------------------------------

def resolve_cli() -> str:
    """Return a shell-invokable ``meshtastic`` command.

    Prefers the in-tree module run through the current interpreter so
    tests exercise the source we are editing, regardless of any
    separately-installed ``meshtastic`` entry point on PATH.
    """
    # The PATH binary may live outside the nono sandbox's allowed paths;
    # ``python -m meshtastic`` is more portable and always available.
    return f"{sys.executable} -m meshtastic"


def run_cli(
    port: int,
    *args: str,
    timeout: int = 60,
    retries: int = 2,
    retry_delay: float = 1.0,
) -> Tuple[int, str]:
    """Run the ``meshtastic`` CLI against the sim node on *port*.

    Returns ``(return_code, merged_stdout_stderr)``. ``--host
    localhost:PORT`` is prefixed automatically. stderr is merged into
    stdout so callers can match warning text such as "Warning: Need to
    specify ..." regardless of which stream it lands on.

    If the CLI fails to connect on the first attempt (which happens
    transiently when a freshly-booted sim node needs a moment to settle
    after the harness interface connects), retry up to *retries*
    additional times after *retry_delay* seconds.
    """
    cli = resolve_cli()
    argv = [*_shlex_split(cli)]
    argv.extend(["--host", f"localhost:{port}"])
    argv.extend(args)
    logger.debug("run_cli: %s", argv)

    last_out = ""
    for attempt in range(retries + 1):
        try:
            proc = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as ex:
            last_out = ex.stdout.decode("utf-8", errors="replace") if ex.stdout else ""
            if attempt < retries:
                time.sleep(retry_delay)
                continue
            return 124, last_out

        out = proc.stdout.decode("utf-8", errors="replace")
        rc = proc.returncode

        # Retry on transient connection-refused / timed-out errors that
        # are common right after a sim node spins up.
        transient = (
            "Error connecting" in out
            or "Timed out waiting for connection" in out
            or "Connection reset by peer" in out
        )
        if rc != 0 and transient and attempt < retries:
            logger.debug("run_cli: transient failure, retry %d/%d", attempt + 1, retries)
            time.sleep(retry_delay)
            last_out = out
            continue
        return rc, out
    return rc, last_out


def _shlex_split(cmd: str) -> List[str]:
    """Split a shell string into argv, honoring quotes."""
    return shlex.split(cmd)


# ---------------------------------------------------------------------------
# Fresh-connection state verification
# ---------------------------------------------------------------------------

def _wait_for_port(port: int, timeout: float = 30.0) -> None:
    """Wait until *port* accepts a TCP connection (firmware sim comes up
    or comes back after a config-commit reboot)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            s = socket.create_connection(("localhost", port), timeout=0.5)
            s.close()
            return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(
        f"port {port} did not accept connections within {timeout}s"
    )


def connect_iface(
    port: int,
    no_nodes: bool = False,
    retries: int = 4,
    wait_timeout: float = 30.0,
) -> TCPInterface:
    """Open a fresh ``TCPInterface`` to *port* and block on the config exchange.

    Firmware config writes (``writeChannel``, ``--seturl``, ``--factory_reset``)
    can briefly restart the sim's TCP listener. We wait for the port to
    come up first, then retry the connect+config-exchange a few times.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            _wait_for_port(port, timeout=wait_timeout)
            return TCPInterface(
                hostname="localhost",
                portNumber=port,
                connectNow=True,
                noNodes=no_nodes,
            )
        except Exception as ex:  # pylint: disable=broad-except
            last_exc = ex
            if attempt < retries:
                logger.debug(
                    "connect_iface attempt %d/%d failed: %s",
                    attempt + 1, retries, ex,
                )
                time.sleep(0.5)
                continue
            raise
    assert last_exc is not None  # type guard; unreachable
    raise last_exc  # pragma: no cover


def verify_state(
    port: int,
    verifier: Callable[[TCPInterface], None],
    *,
    no_nodes: bool = False,
) -> None:
    """Open a fresh interface and run *verifier(iface)*, then close.

    Used after a CLI mutation to verify firmware state through the
    library. Always closes the interface so the next test starts clean.
    """
    iface = connect_iface(port, no_nodes=no_nodes)
    try:
        verifier(iface)
    finally:
        try:
            iface.close()
        except Exception:  # pylint: disable=broad-except
            pass
        time.sleep(PAUSE_AFTER_CLI)


def cli_then_verify(
    port: int,
    cli_args: List[str],
    verifier: Optional[Callable[[TCPInterface], None]],
    *,
    expect_rc: Optional[int] = 0,
    no_nodes: bool = False,
    cli_timeout: int = 60,
) -> str:
    """Run *cli_args* against *port*, optionally asserting *expect_rc*,
    then (if *verifier* is not None) open a fresh interface and run
    *verifier(iface)* against the just-mutated firmware state.

    Returns the CLI stdout.
    """
    rc, out = run_cli(port, *cli_args, timeout=cli_timeout)
    if expect_rc is not None:
        assert rc == expect_rc, f"CLI rc={rc} (expected {expect_rc}): {out}"
    time.sleep(PAUSE_AFTER_CLI)
    if verifier is not None:
        verify_state(port, verifier, no_nodes=no_nodes)
    return out


# ---------------------------------------------------------------------------
# Packet collectors (used by smokemesh receive-verification tests)
# ---------------------------------------------------------------------------

RECEIVE_TIMEOUT = 15.0


class PacketCollector:
    """Collect packets received on a specific interface via pubsub.

    ``Listener`` (pubsub 4.x) wraps handlers with a weak reference, so
    we keep a strong reference to ``handler`` on the instance to prevent
    garbage collection before the publishing thread gets to call it.
    """

    def __init__(self):
        self.packets: List[dict] = []
        self._handler: Optional[Callable] = None

    def on_receive(self, packet, interface):  # pylint: disable=unused-argument
        """Append a received packet to the internal list."""
        self.packets.append(packet)

    def wait_for(self, count: int, timeout: float = RECEIVE_TIMEOUT) -> bool:
        """Wait until *count* packets have been collected or *timeout* expires."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(self.packets) >= count:
                return True
            time.sleep(0.2)
        return len(self.packets) >= count

    @property
    def texts(self) -> List[str]:
        """Return text payloads from TEXT_MESSAGE_APP packets."""
        return [
            p.get("decoded", {}).get("text", "")
            for p in self.packets
            if p.get("decoded", {}).get("portnum") == "TEXT_MESSAGE_APP"
        ]

    @property
    def traceroutes(self) -> List[dict]:
        """Return TRACEROUTE_APP packets."""
        return [
            p for p in self.packets
            if p.get("decoded", {}).get("portnum") == "TRACEROUTE_APP"
        ]

    @property
    def telemetries(self) -> List[dict]:
        """Return TELEMETRY_APP packets."""
        return [
            p for p in self.packets
            if p.get("decoded", {}).get("portnum") == "TELEMETRY_APP"
        ]

    @property
    def positions(self) -> List[dict]:
        """Return POSITION_APP packets."""
        return [
            p for p in self.packets
            if p.get("decoded", {}).get("portnum") == "POSITION_APP"
        ]

    def reset(self) -> None:
        """Clear all collected packets."""
        self.packets.clear()


def _subscribe_topic(
    iface: TCPInterface, topic: str
) -> PacketCollector:
    """Internal: subscribe a fully-qualified *topic* and return a collector.

    Filters by *interface* so multi-node tests can subscribe several
    collectors concurrently without cross-talk.
    """
    collector = PacketCollector()

    def handler(packet, interface):
        if interface is iface:
            collector.on_receive(packet, interface)

    pub.subscribe(handler, topic)
    collector._handler = handler  # strong ref; see PacketCollector docstring
    return collector


def subscribe_texts(iface: TCPInterface) -> PacketCollector:
    """Subscribe to ``meshtastic.receive.text`` filtered to *iface*."""
    return _subscribe_topic(iface, "meshtastic.receive.text")


def subscribe_traceroutes(iface: TCPInterface) -> PacketCollector:
    """Subscribe to ``meshtastic.receive.traceroute`` filtered to *iface*."""
    return _subscribe_topic(iface, "meshtastic.receive.traceroute")


def subscribe_telemetries(iface: TCPInterface) -> PacketCollector:
    """Subscribe to ``meshtastic.receive.telemetry`` filtered to *iface*."""
    return _subscribe_topic(iface, "meshtastic.receive.telemetry")


def subscribe_positions(iface: TCPInterface) -> PacketCollector:
    """Subscribe to ``meshtastic.receive.position`` filtered to *iface*."""
    return _subscribe_topic(iface, "meshtastic.receive.position")


def unsubscribe_all(topic: str) -> None:
    """Drop every handler currently registered on *topic*.

    Tests use this in a ``finally`` block to keep pubsub clean across
    the function-scoped mesh fixtures.
    """
    try:
        pub.unsubAll(topic)
    except Exception:  # pylint: disable=broad-except
        pass


__all__ = [
    "PAUSE_AFTER_CLI",
    "PacketCollector",
    "RECEIVE_TIMEOUT",
    "cli_then_verify",
    "connect_iface",
    "resolve_cli",
    "run_cli",
    "subscribe_positions",
    "subscribe_telemetries",
    "subscribe_texts",
    "subscribe_traceroutes",
    "unsubscribe_all",
    "verify_state",
]
