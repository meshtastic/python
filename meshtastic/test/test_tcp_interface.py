"""Meshtastic unit tests for tcp_interface.py"""

import re

from unittest.mock import patch
import pytest

from meshtastic.tcp_interface import TCPInterface


@pytest.mark.unit
def test_TCPInterface(capsys):
    """Test that we can instantiate a TCPInterface"""
    with patch('socket.socket') as mock_socket:
        iface = TCPInterface(hostname='localhost', noProto=True)
        iface.showInfo()
        iface.localNode.showInfo()
        out, err = capsys.readouterr()
        assert re.search(r'Owner: None \(None\)', out, re.MULTILINE)
        assert re.search(r'Nodes', out, re.MULTILINE)
        assert re.search(r'Preferences', out, re.MULTILINE)
        assert re.search(r'Channels', out, re.MULTILINE)
        assert re.search(r'Primary channel URL', out, re.MULTILINE)
        assert err == ''
        assert mock_socket.called
        iface.close()
