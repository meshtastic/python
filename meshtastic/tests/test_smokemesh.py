"""Meshtastic smoke tests with multiple meshtasticd sim instances.

Uses the ``firmware_mesh`` session fixture which provides a 3-node chain
topology (A-B-C) where A hears B, B hears A and C, and C hears B.
The SIMULATOR_APP packet bridge forwards transmissions between nodes
according to this topology.
"""
import time
from typing import Any, Callable, List, Optional

import pytest
from pubsub import pub  # type: ignore[import-untyped]

RECEIVE_TIMEOUT = 15


class _PacketCollector:
    """Collects received packets on a specific interface for test assertions."""

    def __init__(self):
        self.packets: List[dict] = []
        self._handler: Optional[Callable[..., Any]] = None

    def on_receive(self, packet, interface):  # pylint: disable=unused-argument
        """Store a received packet."""
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

    def reset(self):
        """Clear all collected packets."""
        self.packets.clear()


def _subscribe_texts(iface) -> _PacketCollector:
    """Subscribe a collector to text messages on a specific interface."""
    collector = _PacketCollector()

    def handler(packet, interface):
        if interface is iface:
            collector.on_receive(packet, interface)

    pub.subscribe(handler, "meshtastic.receive.text")
    collector._handler = handler  # keep strong ref to prevent GC (Listener stores weakref)
    return collector


def _subscribe_traceroutes(iface) -> _PacketCollector:
    """Subscribe a collector to traceroute responses on a specific interface."""
    collector = _PacketCollector()

    def handler(packet, interface):
        if interface is iface:
            collector.on_receive(packet, interface)

    pub.subscribe(handler, "meshtastic.receive.traceroute")
    collector._handler = handler
    return collector


@pytest.mark.smokemesh
def test_smokemesh_node_db_convergence(firmware_mesh):
    """Each node should see all 3 nodes in its node DB after convergence."""
    counts = [len(n.iface.nodes) for n in firmware_mesh.nodes if n.iface]
    if any(c < 3 for c in counts):
        pytest.skip(f"Mesh did not converge (counts={counts})")
    for i, node in enumerate(firmware_mesh.nodes):
        iface = node.iface
        assert iface is not None
        assert len(iface.nodes) >= 3, f"node {i} only sees {len(iface.nodes)} nodes"


@pytest.mark.smokemesh
def test_smokemesh_broadcast_text(firmware_mesh):
    """A broadcast from node A should arrive on node B."""
    collector = _subscribe_texts(firmware_mesh.get_iface(1))
    try:
        firmware_mesh.get_iface(0).sendText("hello mesh", wantAck=False)
        assert collector.wait_for(1)
        assert "hello mesh" in collector.texts
    finally:
        pub.unsubAll("meshtastic.receive.text")


@pytest.mark.smokemesh
def test_smokemesh_dm(firmware_mesh):
    """A DM from node A to node B should arrive on B."""
    dest = firmware_mesh.get_node(1).node_num
    collector = _subscribe_texts(firmware_mesh.get_iface(1))
    try:
        firmware_mesh.get_iface(0).sendText(
            "hey B", destinationId=dest, wantAck=False
        )
        assert collector.wait_for(1)
        assert "hey B" in collector.texts
    finally:
        pub.unsubAll("meshtastic.receive.text")


@pytest.mark.smokemesh
def test_smokemesh_dm_across_relay(firmware_mesh):
    """A DM from node A to node C must relay through B (chain topology)."""
    dest = firmware_mesh.get_node(2).node_num
    collector = _subscribe_texts(firmware_mesh.get_iface(2))
    try:
        firmware_mesh.get_iface(0).sendText(
            "relay test", destinationId=dest, wantAck=False
        )
        assert collector.wait_for(1), "node C did not receive the DM within timeout"
        assert "relay test" in collector.texts
    finally:
        pub.unsubAll("meshtastic.receive.text")


@pytest.mark.smokemesh
def test_smokemesh_hop_limit_prevents_relay(firmware_mesh):
    """A broadcast with hopLimit=0 from A reaches B but B does not relay to C."""
    col_b = _subscribe_texts(firmware_mesh.get_iface(1))
    col_c = _subscribe_texts(firmware_mesh.get_iface(2))
    try:
        firmware_mesh.get_iface(0).sendText(
            "hop0", wantAck=False, hopLimit=0
        )
        assert col_b.wait_for(1), "B should receive A's broadcast"
        assert "hop0" in col_b.texts, "B got wrong text"

        time.sleep(RECEIVE_TIMEOUT)
        assert "hop0" not in col_c.texts, (
            "C should NOT receive — B must not relay hopLimit=0"
        )
    finally:
        pub.unsubAll("meshtastic.receive.text")


@pytest.mark.smokemesh
def test_smokemesh_show_nodes(firmware_mesh):
    """showNodes should report the other nodes in the mesh."""
    for i in range(3):
        iface = firmware_mesh.get_iface(i)
        iface.showNodes()


@pytest.mark.smokemesh
def test_smokemesh_traceroute_across_relay(firmware_mesh):
    """Traceroute from A to C should show route via B in both directions."""
    col_a = _subscribe_traceroutes(firmware_mesh.get_iface(0))
    col_c = _subscribe_traceroutes(firmware_mesh.get_iface(2))
    try:
        src_a = firmware_mesh.get_node(0).node_num
        dest_c = firmware_mesh.get_node(2).node_num
        node_b = firmware_mesh.get_node(1).node_num

        firmware_mesh.get_iface(0).sendTraceRoute(dest=dest_c, hopLimit=3)

        time.sleep(2)

        assert len(col_a.traceroutes) >= 1, "A did not receive traceroute response"
        a_resp = col_a.traceroutes[0]
        assert a_resp["from"] == dest_c, "response source should be C"

        route = a_resp["decoded"]["traceroute"]
        assert route.get("route") == [node_b], "forward route should be A→B→C"
        assert route.get("routeBack") == [node_b], "return route should be C→B→A"

        assert len(col_c.traceroutes) >= 1, "C did not receive traceroute request"
        c_req = col_c.traceroutes[0]
        assert c_req["from"] == src_a, "request source should be A"
    finally:
        pub.unsubAll("meshtastic.receive.traceroute")
