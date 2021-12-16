"""Meshtastic unit tests for node.py"""

import re

from unittest.mock import patch, MagicMock
import pytest

from ..node import Node
from ..serial_interface import SerialInterface
from ..admin_pb2 import AdminMessage


@pytest.mark.unit
def test_node(capsys):
    """Test that we can instantiate a Node"""
    anode = Node('foo', 'bar')
    anode.showChannels()
    anode.showInfo()
    out, err = capsys.readouterr()
    assert re.search(r'Preferences', out)
    assert re.search(r'Channels', out)
    assert re.search(r'Primary channel URL', out)
    assert err == ''


@pytest.mark.unit
def test_node_reqquestConfig():
    """Test run requestConfig"""
    iface = MagicMock(autospec=SerialInterface)
    amesg = MagicMock(autospec=AdminMessage)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with patch('meshtastic.admin_pb2.AdminMessage', return_value=amesg):
            anode = Node(mo, 'bar')
            anode.requestConfig()
