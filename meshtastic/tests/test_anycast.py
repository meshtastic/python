"""Anycast groups: ids, keys, sending to a group and managing groups on a node."""

from unittest.mock import MagicMock

import pytest

from meshtastic import anycast
from meshtastic.mesh_interface import MeshInterface
from meshtastic.node import Node
from meshtastic.protobuf import localonly_pb2, packet_pb2


@pytest.mark.unit
def test_group_id_is_crc32_of_the_public_key():
    """The same vector the firmware's test_anycast pins."""
    assert anycast.group_id(bytes(range(32))) == 0x91267E8A


@pytest.mark.unit
def test_x25519_matches_rfc7748():
    """RFC 7748 section 5.2, first vector."""
    scalar = bytes.fromhex("a546e36bf0527c9d3b16154b82465edd62144c0ac1fc5a18506a2244ba449ac4")
    u = bytes.fromhex("e6db6867583030db3594c1a424b15f7c726624ec26b3353b10a903a6d0ab1c4c")
    expected = bytes.fromhex("c3da55379de9c6908e94ea4df28d084f32eccf03491c71f754b4075577a28552")
    assert anycast.x25519(scalar, u) == expected


@pytest.mark.unit
def test_generated_keys_agree_and_avoid_reserved_ids():
    priv_a, pub_a = anycast.generate_keypair()
    priv_b, pub_b = anycast.generate_keypair()
    assert anycast.public_key(priv_a) == pub_a
    assert anycast.x25519(priv_a, pub_b) == anycast.x25519(priv_b, pub_a)
    assert anycast.group_id(pub_a) not in anycast.RESERVED_IDS


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_send_to_a_group_sets_the_anycast_flag():
    iface = MeshInterface(noProto=True)
    p = iface.sendData(b"hello", 0x1234ABCD, portNum=1, anycast=True)
    assert p.flags & packet_pb2.MeshPacket.PACKET_ANYCAST
    assert p.id in iface.anycastRequests
    plain = iface.sendData(b"hello", 0x1234ABCD, portNum=1)
    assert not plain.flags & packet_pb2.MeshPacket.PACKET_ANYCAST
    iface.close()


def _localNode():
    iface = MagicMock(autospec=MeshInterface)
    node = Node(iface, 1234, noProto=True)
    iface.localNode = node
    node.localConfig = localonly_pb2.LocalConfig()
    node.writeConfig = MagicMock()
    return node


@pytest.mark.unit
def test_set_group_as_member_writes_group_then_key():
    node = _localNode()
    priv, pub = anycast.generate_keypair()
    node.setGroup("gw", pub, priv, uplink=True)
    assert [c.args[0] for c in node.writeConfig.call_args_list] == ["group", "security"]
    assert node.listGroups() == [{"name": "gw", "id": anycast.group_id(pub), "member": True, "uplink": True}]
    assert node.groupId("gw") == anycast.group_id(pub)


@pytest.mark.unit
def test_set_group_refuses_a_private_key_of_another_group():
    node = _localNode()
    priv, _ = anycast.generate_keypair()
    _, pub = anycast.generate_keypair()
    with pytest.raises(SystemExit):
        node.setGroup("gw", pub, priv)


@pytest.mark.unit
def test_delete_group_drops_its_key():
    node = _localNode()
    priv, pub = anycast.generate_keypair()
    node.setGroup("gw", pub, priv)
    node.deleteGroup("gw")
    assert node.listGroups() == []
    assert list(node.localConfig.security.group_private_key) == []
