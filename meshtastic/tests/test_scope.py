"""Scope codes: the code a node with a home region puts on its broadcasts, region name rules, and the decoded
options block on received packets."""

import pytest

from meshtastic import util
from meshtastic.__main__ import setPref
from meshtastic.mesh_interface import MeshInterface
from meshtastic.protobuf import localonly_pb2, packet_pb2, portnums_pb2, wire_pb2


@pytest.mark.unit
def test_scope_code_matches_the_worked_example():
    """SCHEMA.md section 8, pinned by firmware test_relay_policy and test_packet_signing too."""
    assert util.scope_code("eu-west", 0x5A, 0x12345678, 0xCAFEBABE) == 0xEB96
    assert util.scope_code("EU-West", 0x5A, 0x12345678, 0xCAFEBABE) == 0x9377  # why names are canonical


@pytest.mark.unit
def test_region_names_fold_to_lowercase_and_refuse_the_rest():
    assert util.canonical_region_name("EU-West") == "eu-west"
    assert util.canonical_region_name("", allow_empty=True) == ""
    for bad in ("eu west", "münchen", "eu_west", "a" * 16, ""):
        with pytest.raises(ValueError):
            util.canonical_region_name(bad)


@pytest.mark.unit
def test_set_relay_region_names_canonicalizes_before_writing():
    config = localonly_pb2.LocalConfig()
    assert setPref(config, "relay.home_region", "EU-West")
    assert config.relay.home_region == "eu-west"
    assert setPref(config, "relay.regions", "Alps")
    assert list(config.relay.regions) == ["alps"]
    assert not setPref(config, "relay.home_region", "eu west")
    assert config.relay.home_region == "eu-west"


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_received_packet_carries_the_decoded_options_block(monkeypatch):
    iface = MeshInterface(noProto=True)
    published = []
    monkeypatch.setattr("meshtastic.mesh_interface.publishingThread.queueWork", lambda work: work())
    monkeypatch.setattr("meshtastic.mesh_interface.pub.sendMessage", lambda topic, **kw: published.append(kw["packet"]))
    p = packet_pb2.MeshPacket()
    setattr(p, "from", 0x12345678)
    p.to = 0xFFFFFFFF
    p.id = 0xCAFEBABE
    p.decoded.portnum = portnums_pb2.PortNum.PRIVATE_APP
    p.header_options = wire_pb2.HeaderOptions(scope_code=0xEB96).SerializeToString()
    iface._handlePacketFromRadio(p, hack=True)
    assert published[0]["headerOptions"]["scopeCode"] == 0xEB96
    iface.close()
