"""Meshtastic unit tests for mesh_interface.py"""

import re
import logging

from unittest.mock import patch, MagicMock
import pytest

from ..mesh_interface import MeshInterface
from ..node import Node
from .. import mesh_pb2
from ..__init__ import LOCAL_ADDR


@pytest.mark.unit
def test_MeshInterface(capsys, reset_globals):
    """Test that we can instantiate a MeshInterface"""
    iface = MeshInterface(noProto=True)
    iface.showInfo()
    iface.localNode.showInfo()
    iface.showNodes()
    iface.sendText('hello')
    iface.close()
    out, err = capsys.readouterr()
    assert re.search(r'Owner: None \(None\)', out, re.MULTILINE)
    assert re.search(r'Nodes', out, re.MULTILINE)
    assert re.search(r'Preferences', out, re.MULTILINE)
    assert re.search(r'Channels', out, re.MULTILINE)
    assert re.search(r'Primary channel URL', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
def test_handlePacketFromRadio_no_from(capsys, reset_globals):
    """Test _handlePacketFromRadio with no 'from' in the mesh packet."""
    iface = MeshInterface(noProto=True)
    meshPacket = mesh_pb2.MeshPacket()
    iface._handlePacketFromRadio(meshPacket)
    out, err = capsys.readouterr()
    assert re.search(r'Device returned a packet we sent, ignoring', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
def test_handlePacketFromRadio_with_a_portnum(caplog, reset_globals):
    """Test _handlePacketFromRadio with a portnum
       Since we have an attribute called 'from', we cannot simply 'set' it.
       Had to implement a hack just to be able to test some code.
    """
    iface = MeshInterface(noProto=True)
    meshPacket = mesh_pb2.MeshPacket()
    meshPacket.decoded.payload = b''
    meshPacket.decoded.portnum = 1
    with caplog.at_level(logging.WARNING):
        iface._handlePacketFromRadio(meshPacket, hack=True)
    assert re.search(r'Not populating fromId', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_handlePacketFromRadio_no_portnum(caplog, reset_globals):
    """Test _handlePacketFromRadio without a portnum"""
    iface = MeshInterface(noProto=True)
    meshPacket = mesh_pb2.MeshPacket()
    meshPacket.decoded.payload = b''
    with caplog.at_level(logging.WARNING):
        iface._handlePacketFromRadio(meshPacket, hack=True)
    assert re.search(r'Not populating fromId', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_getNode_with_local(reset_globals):
    """Test getNode"""
    iface = MeshInterface(noProto=True)
    anode = iface.getNode(LOCAL_ADDR)
    assert anode == iface.localNode


@pytest.mark.unit
def test_getNode_not_local(reset_globals, caplog):
    """Test getNode not local"""
    iface = MeshInterface(noProto=True)
    anode = MagicMock(autospec=Node)
    with caplog.at_level(logging.DEBUG):
        with patch('meshtastic.node.Node', return_value=anode):
            another_node = iface.getNode('bar2')
            assert another_node != iface.localNode
    assert re.search(r'About to requestConfig', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_getNode_not_local_timeout(reset_globals, capsys):
    """Test getNode not local, simulate timeout"""
    iface = MeshInterface(noProto=True)
    anode = MagicMock(autospec=Node)
    anode.waitForConfig.return_value = False
    with patch('meshtastic.node.Node', return_value=anode):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            iface.getNode('bar2')
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.match(r'Error: Timed out waiting for node config', out)
        assert err == ''


@pytest.mark.unit
def test_sendPosition(reset_globals, caplog):
    """Test sendPosition"""
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface.sendPosition()
    iface.close()
    assert re.search(r'p.time:', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_handleFromRadio_empty_payload(reset_globals, caplog):
    """Test _handleFromRadio"""
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface._handleFromRadio(b'')
    iface.close()
    assert re.search(r'Unexpected FromRadio payload', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_handleFromRadio_with_my_info(reset_globals, caplog):
    """Test _handleFromRadio with my_info"""
    # Note: I captured the '--debug --info' for the bytes below.
    # It "translates" to this:
    # my_info {
    #  my_node_num: 682584012
    #  num_bands: 13
    #  firmware_version: "1.2.49.5354c49"
    #  reboot_count: 13
    #  bitrate: 17.088470458984375
    #  message_timeout_msec: 300000
    #  min_app_version: 20200
    #  max_channels: 8
    # }
    from_radio_bytes = b'\x1a,\x08\xcc\xcf\xbd\xc5\x02\x18\r2\x0e1.2.49.5354c49P\r]0\xb5\x88Ah\xe0\xa7\x12p\xe8\x9d\x01x\x08\x90\x01\x01'
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface._handleFromRadio(from_radio_bytes)
    iface.close()
    assert re.search(r'Received myinfo', caplog.text, re.MULTILINE)
    assert re.search(r'num_bands: 13', caplog.text, re.MULTILINE)
    assert re.search(r'max_channels: 8', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_handleFromRadio_with_node_info(reset_globals, caplog):
    """Test _handleFromRadio with node_info"""
    # Note: I captured the '--debug --info' for the bytes below.
    # It "translates" to this:
    # node_info {
    #  num: 682584012
    #  user {
    #    id: "!28af67cc"
    #    long_name: "Unknown 67cc"
    #    short_name: "?CC"
    #    macaddr: "$o(\257g\314"
    #    hw_model: HELTEC_V2_1
    #  }
    #  position {
    #    }
    #  }

    from_radio_bytes = b'"2\x08\xcc\xcf\xbd\xc5\x02\x12(\n\t!28af67cc\x12\x0cUnknown 67cc\x1a\x03?CC"\x06$o(\xafg\xcc0\n\x1a\x00'
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface._startConfig()
        iface._handleFromRadio(from_radio_bytes)
    iface.close()
    assert re.search(r'Received nodeinfo', caplog.text, re.MULTILINE)
    assert re.search(r'682584012', caplog.text, re.MULTILINE)
    assert re.search(r'HELTEC_V2_1', caplog.text, re.MULTILINE)
