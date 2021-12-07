"""Meshtastic unit tests for node.py"""
import re
import subprocess
import platform

import pytest

from meshtastic.__init__ import MeshInterface


@pytest.mark.unit
def test_MeshInterface():
    """Test that we instantiate a MeshInterface"""
    iface = MeshInterface(noProto=True)
    iface.showInfo()
    iface.localNode.showInfo()
    iface.close()
