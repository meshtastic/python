"""Meshtastic unit tests for tunnel.py"""

import re
import sys
import logging

from unittest.mock import patch, MagicMock
import pytest

from ..tcp_interface import TCPInterface
from ..tunnel import Tunnel, onTunnelReceive
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
            Tunnel(iface)
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


@pytest.mark.unitslow
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
            tun = Tunnel(iface)
            assert tun == Globals.getInstance().get_tunnelInstance()
            iface.close()
    assert re.search(r'Not creating a TapDevice()', caplog.text, re.MULTILINE)
    assert re.search(r'Not starting TUN reader', caplog.text, re.MULTILINE)
    assert re.search(r'Not sending packet', caplog.text, re.MULTILINE)


@pytest.mark.unitslow
@patch('platform.system')
def test_onTunnelReceive_from_ourselves(mock_platform_system, caplog, reset_globals, iface_with_nodes):
    """Test onTunnelReceive"""
    iface = iface_with_nodes
    iface.myInfo.my_node_num = 2475227164
    sys.argv = ['']
    Globals.getInstance().set_args(sys.argv)
    packet = {'decoded': { 'payload': 'foo'}, 'from': 2475227164}
    a_mock = MagicMock()
    a_mock.return_value = 'Linux'
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.DEBUG):
        with patch('socket.socket'):
            tun = Tunnel(iface)
            Globals.getInstance().set_tunnelInstance(tun)
            onTunnelReceive(packet, iface)
    assert re.search(r'in onTunnelReceive', caplog.text, re.MULTILINE)
    assert re.search(r'Ignoring message we sent', caplog.text, re.MULTILINE)


@pytest.mark.unit
@patch('platform.system')
def test_onTunnelReceive_from_someone_else(mock_platform_system, caplog, reset_globals, iface_with_nodes):
    """Test onTunnelReceive"""
    iface = iface_with_nodes
    iface.myInfo.my_node_num = 2475227164
    sys.argv = ['']
    Globals.getInstance().set_args(sys.argv)
    packet = {'decoded': { 'payload': 'foo'}, 'from': 123}
    a_mock = MagicMock()
    a_mock.return_value = 'Linux'
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.DEBUG):
        with patch('socket.socket'):
            tun = Tunnel(iface)
            Globals.getInstance().set_tunnelInstance(tun)
            onTunnelReceive(packet, iface)
    assert re.search(r'in onTunnelReceive', caplog.text, re.MULTILINE)
