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
