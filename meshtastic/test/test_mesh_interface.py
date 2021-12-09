"""Meshtastic unit tests for mesh_interface.py"""

import re

import pytest

from meshtastic.mesh_interface import MeshInterface


@pytest.mark.unit
def test_MeshInterface(capsys):
    """Test that we can instantiate a MeshInterface"""
    iface = MeshInterface(noProto=True)
    iface.showInfo()
    iface.localNode.showInfo()
    out, err = capsys.readouterr()
    assert re.search(r'Owner: None \(None\)', out, re.MULTILINE)
    assert re.search(r'Nodes', out, re.MULTILINE)
    assert re.search(r'Preferences', out, re.MULTILINE)
    assert re.search(r'Channels', out, re.MULTILINE)
    assert re.search(r'Primary channel URL', out, re.MULTILINE)
    assert err == ''
    iface.close()
