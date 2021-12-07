"""Meshtastic unit tests for node.py"""

import pytest

from meshtastic.mesh_interface import MeshInterface


@pytest.mark.unit
def test_MeshInterface():
    """Test that we instantiate a MeshInterface"""
    iface = MeshInterface(noProto=True)
    iface.showInfo()
    iface.localNode.showInfo()
    iface.close()
