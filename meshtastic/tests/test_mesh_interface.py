"""Meshtastic unit tests for mesh_interface.py"""

import re

import pytest

from ..mesh_interface import MeshInterface
from .. import mesh_pb2
#from ..mesh_pb2 import MeshPacket


@pytest.mark.unit
def test_MeshInterface(capsys):
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
def test_handlePacketFromRadio_no_from(capsys):
    """Test _handlePacketFromRadio no 'from'"""
    iface = MeshInterface(noProto=True)
    meshPacket = mesh_pb2.MeshPacket()
    iface._handlePacketFromRadio(meshPacket)
    out, err = capsys.readouterr()
    assert re.search(r'Device returned a packet we sent, ignoring', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
def test_MeshPacket_set_from(capsys):
    """Test setting 'from' MeshPacket """
    iface = MeshInterface(noProto=True)
    meshPacket = mesh_pb2.MeshPacket()
    meshPacket.decoded.payload = b''
    meshPacket.decoded.portnum = 1
    iface._handlePacketFromRadio(meshPacket, hack=True)
    out, err = capsys.readouterr()
    assert re.search(r'', out, re.MULTILINE)
    assert err == ''
