"""Per-portnum fragmentation (protobufs SCHEMA.md section 8, "Fragmentation").

A payload larger than one frame travels as up to eight ordinary packets, each carrying
HeaderOptions.fragment = msg_id << 6 | index << 3 | total, where total is the count minus
one. The owner of a port splits and joins it: a client owns the ports below, so this module
splits what the client sends and joins what it receives. The node never joins them for us.
"""

import time
from typing import Dict, List, Optional, Tuple

from meshtastic.protobuf import packet_pb2, portnums_pb2, wire_pb2

# Ports a client splits and joins, with their fragment cap.
CLIENT_PORTS = {
    portnums_pb2.PortNum.ATAK_FORWARDER: 4,
    portnums_pb2.PortNum.LORAWAN_BRIDGE: 2,
}

# Payload bytes per fragment, below the per-shape room (SCHEMA.md section 8) so a two-byte
# portnum and HOP_STORE still fit: a broadcast fragment keeps room for its signature, a
# direct message fragment pays the PKI overhead instead.
BROADCAST_SLICE = 160
UNICAST_SLICE = 210

REASSEMBLY_TIMEOUT_S = 300


def pack(msg_id: int, index: int, total: int) -> int:
    """HeaderOptions.fragment for fragment `index` of a message of `total + 1`."""
    return (msg_id & 0xFF) << 6 | (index & 7) << 3 | (total & 7)


def unpack(value: int) -> Optional[Tuple[int, int, int]]:
    """(msg_id, index, total), or None for a value no sender may produce."""
    if value >> 14:
        return None
    msg_id, index, total = value >> 6, (value >> 3) & 7, value & 7
    if total == 0 or index > total:
        return None
    return msg_id, index, total


def split(data: bytes, broadcast: bool) -> List[bytes]:
    """`data` in slices that each fit one frame of this shape."""
    size = BROADCAST_SLICE if broadcast else UNICAST_SLICE
    return [data[i : i + size] for i in range(0, len(data), size)]


def field_of(meshPacket: packet_pb2.MeshPacket) -> Optional[Tuple[int, int, int]]:
    """The fragment field of a received packet, or None for an ordinary one."""
    if not meshPacket.header_options:
        return None
    opts = wire_pb2.HeaderOptions()
    try:
        opts.ParseFromString(meshPacket.header_options)
    except Exception:  # pylint: disable=W0703
        return None
    return unpack(opts.fragment) if opts.fragment else None


class Reassembler:
    """Joins fragments keyed on (from, portnum, msg_id)."""

    def __init__(self, timeout_s: float = REASSEMBLY_TIMEOUT_S):
        self.timeout_s = timeout_s
        self.pending: Dict[Tuple[int, int, int], dict] = {}

    def add(self, meshPacket: packet_pb2.MeshPacket, now: Optional[float] = None) -> Optional[packet_pb2.MeshPacket]:
        """Store one fragment. Returns the whole message, as fragment 0 carrying the joined
        payload, once every fragment has arrived; None until then or for an invalid one."""
        field = field_of(meshPacket)
        if field is None:
            return None
        now = time.monotonic() if now is None else now
        self.pending = {k: v for k, v in self.pending.items() if now - v["last"] < self.timeout_s}
        msg_id, index, total = field
        key = (getattr(meshPacket, "from"), meshPacket.decoded.portnum, msg_id)
        entry = self.pending.setdefault(key, {"total": total, "parts": {}, "last": now})
        if entry["total"] != total:
            del self.pending[key]
            return None
        entry["parts"][index] = meshPacket
        entry["last"] = now
        if len(entry["parts"]) <= total:
            return None
        del self.pending[key]
        whole = packet_pb2.MeshPacket()
        whole.CopyFrom(entry["parts"][0])
        whole.decoded.payload = b"".join(entry["parts"][i].decoded.payload for i in range(total + 1))
        whole.ClearField("header_options")
        return whole
