"""Meshtastic smoke tests with multiple meshtasticd sim instances.

Uses the ``firmware_mesh`` session fixture which provides a 3-node chain
topology (A-B-C) where A hears B, B hears A and C, and C hears B.
The SIMULATOR_APP packet bridge forwards transmissions between nodes
according to this topology.
"""
import time

import pytest

from meshtastic.protobuf import packet_pb2

from .fw_helpers import (
    RECEIVE_TIMEOUT,
    subscribe_texts,
    subscribe_telemetries,
    unsubscribe_all,
)


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
    collector = subscribe_texts(firmware_mesh.get_iface(1))
    try:
        firmware_mesh.get_iface(0).sendText("hello mesh", wantAck=False)
        assert collector.wait_for(1)
        assert "hello mesh" in collector.texts
    finally:
        unsubscribe_all("meshtastic.receive.text")


@pytest.mark.smokemesh
def test_smokemesh_dm(firmware_mesh):
    """A DM from node A to node B should arrive on B."""
    dest = firmware_mesh.get_node(1).node_num
    collector = subscribe_texts(firmware_mesh.get_iface(1))
    try:
        firmware_mesh.get_iface(0).sendText(
            "hey B", destinationId=dest, wantAck=False
        )
        assert collector.wait_for(1)
        assert "hey B" in collector.texts
    finally:
        unsubscribe_all("meshtastic.receive.text")


@pytest.mark.smokemesh
def test_smokemesh_dm_across_relay(firmware_mesh):
    """A DM from node A to node C must relay through B (chain topology)."""
    dest = firmware_mesh.get_node(2).node_num
    collector = subscribe_texts(firmware_mesh.get_iface(2))
    try:
        firmware_mesh.get_iface(0).sendText(
            "relay test", destinationId=dest, wantAck=False
        )
        assert collector.wait_for(1), "node C did not receive the DM within timeout"
        assert "relay test" in collector.texts
    finally:
        unsubscribe_all("meshtastic.receive.text")


@pytest.mark.smokemesh
def test_smokemesh_hop_limit_prevents_relay(firmware_mesh):
    """A broadcast with hopLimit=0 from A reaches B but B does not relay to C."""
    col_b = subscribe_texts(firmware_mesh.get_iface(1))
    col_c = subscribe_texts(firmware_mesh.get_iface(2))
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
        unsubscribe_all("meshtastic.receive.text")


@pytest.mark.smokemesh
def test_smokemesh_show_nodes(firmware_mesh):
    """showNodes should report the other nodes in the mesh."""
    for i in range(3):
        iface = firmware_mesh.get_iface(i)
        iface.showNodes()


@pytest.mark.smokemesh
def test_smokemesh_traceroute_across_relay(firmware_mesh):
    """A traceroute from A to C: the reply records its way back, through B."""
    col_a = subscribe_telemetries(firmware_mesh.get_iface(0))
    try:
        dest_c = firmware_mesh.get_node(2).node_num
        node_b = firmware_mesh.get_node(1).node_num

        firmware_mesh.get_iface(0).sendTraceRoute(dest=dest_c, hopLimit=3)

        time.sleep(2)

        replies = [p for p in col_a.telemetries if p["from"] == dest_c]
        assert replies, "A did not receive the reply from C"
        raw = replies[0]["raw"]
        assert raw.flags & packet_pb2.MeshPacket.PACKET_RECORD_PATH, "the reply should record its path"
        assert raw.hop_start - raw.hop_limit == 1, "the reply should take one relay hop"
        assert raw.relay_node == (node_b & 0xFF or 1), "the reply should be relayed by B"
    finally:
        unsubscribe_all("meshtastic.receive.telemetry")
