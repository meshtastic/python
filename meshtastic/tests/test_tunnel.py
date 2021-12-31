"""Meshtastic unit tests for tunnel.py"""

import re
import logging

from unittest.mock import patch, MagicMock
import pytest

from ..tcp_interface import TCPInterface
from ..tunnel import Tunnel
from ..globals import Globals


@pytest.mark.unit
@patch('platform.system')
def test_Tunnel_on_non_linux_system(mock_platform_system, reset_globals):
    """Test that we cannot instantiate a Tunnel on a non Linux system"""
    a_mock = MagicMock()
    a_mock.return_value = 'notLinux'
    mock_platform_system.side_effect = a_mock
    with patch('socket.socket') as mock_socket:
        with pytest.raises(Exception) as pytest_wrapped_e:
            iface = TCPInterface(hostname='localhost', noProto=True)
            tun = Tunnel(iface)
            assert tun == Globals.getInstance().get_tunnelInstance()
        assert pytest_wrapped_e.type == Exception
        assert mock_socket.called


@pytest.mark.unit
@patch('platform.system')
def test_Tunnel_without_interface(mock_platform_system, reset_globals):
    """Test that we can not instantiate a Tunnel without a valid interface"""
    a_mock = MagicMock()
    a_mock.return_value = 'Linux'
    mock_platform_system.side_effect = a_mock
    with pytest.raises(Exception) as pytest_wrapped_e:
        Tunnel(None)
    assert pytest_wrapped_e.type == Exception


@pytest.mark.unit
@patch('platform.system')
def test_Tunnel_with_interface(mock_platform_system, caplog, reset_globals, iface_with_nodes):
    """Test that we can not instantiate a Tunnel without a valid interface"""
    iface = iface_with_nodes
    iface.myInfo.my_node_num = 2475227164
    a_mock = MagicMock()
    a_mock.return_value = 'Linux'
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.WARNING):
        with patch('socket.socket'):
            Tunnel(iface)
            iface.close()
    assert re.search(r'Not creating a TapDevice()', caplog.text, re.MULTILINE)
    assert re.search(r'Not starting TUN reader', caplog.text, re.MULTILINE)
    assert re.search(r'Not sending packet', caplog.text, re.MULTILINE)
