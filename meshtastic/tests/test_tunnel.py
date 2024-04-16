"""Meshtastic unit tests for tunnel.py"""
import logging
import re
import sys
from unittest.mock import MagicMock, patch

import pytest

from meshtastic import mt_config

from ..tcp_interface import TCPInterface
from ..tunnel import Tunnel, onTunnelReceive


@pytest.mark.unit
@patch("platform.system")
def test_Tunnel_on_non_linux_system(mock_platform_system):
    """Test that we cannot instantiate a Tunnel on a non Linux system"""
    a_mock = MagicMock()
    a_mock.return_value = "notLinux"
    mock_platform_system.side_effect = a_mock
    with patch("socket.socket") as mock_socket:
        with pytest.raises(Tunnel.TunnelError) as pytest_wrapped_e:
            iface = TCPInterface(hostname="localhost", noProto=True)
            Tunnel(iface)
        assert pytest_wrapped_e.type == Tunnel.TunnelError
        assert mock_socket.called


@pytest.mark.unit
@patch("platform.system")
def test_Tunnel_without_interface(mock_platform_system):
    """Test that we can not instantiate a Tunnel without a valid interface"""
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    with pytest.raises(Tunnel.TunnelError) as pytest_wrapped_e:
        Tunnel(None)
    assert pytest_wrapped_e.type == Tunnel.TunnelError


@pytest.mark.unitslow
@patch("platform.system")
def test_Tunnel_with_interface(mock_platform_system, caplog, iface_with_nodes):
    """Test that we can not instantiate a Tunnel without a valid interface"""
    iface = iface_with_nodes
    iface.myInfo.my_node_num = 2475227164
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.WARNING):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            assert tun == mt_config.tunnelInstance
            iface.close()
    assert re.search(r"Not creating a TapDevice()", caplog.text, re.MULTILINE)
    assert re.search(r"Not starting TUN reader", caplog.text, re.MULTILINE)
    assert re.search(r"Not sending packet", caplog.text, re.MULTILINE)


@pytest.mark.unitslow
@patch("platform.system")
def test_onTunnelReceive_from_ourselves(mock_platform_system, caplog, iface_with_nodes):
    """Test onTunnelReceive"""
    iface = iface_with_nodes
    iface.myInfo.my_node_num = 2475227164
    sys.argv = [""]
    mt_config.args = sys.argv
    packet = {"decoded": {"payload": "foo"}, "from": 2475227164}
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.DEBUG):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            mt_config.tunnelInstance = tun
            onTunnelReceive(packet, iface)
    assert re.search(r"in onTunnelReceive", caplog.text, re.MULTILINE)
    assert re.search(r"Ignoring message we sent", caplog.text, re.MULTILINE)


@pytest.mark.unit
@patch("platform.system")
def test_onTunnelReceive_from_someone_else(
    mock_platform_system, caplog, iface_with_nodes
):
    """Test onTunnelReceive"""
    iface = iface_with_nodes
    iface.myInfo.my_node_num = 2475227164
    sys.argv = [""]
    mt_config.args = sys.argv
    packet = {"decoded": {"payload": "foo"}, "from": 123}
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.DEBUG):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            mt_config.tunnelInstance = tun
            onTunnelReceive(packet, iface)
    assert re.search(r"in onTunnelReceive", caplog.text, re.MULTILINE)


@pytest.mark.unitslow
@patch("platform.system")
def test_shouldFilterPacket_random(mock_platform_system, caplog, iface_with_nodes):
    """Test _shouldFilterPacket()"""
    iface = iface_with_nodes
    iface.noProto = True
    # random packet
    packet = b"1234567890123456789012345678901234567890"
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.DEBUG):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            ignore = tun._shouldFilterPacket(packet)
            assert not ignore


@pytest.mark.unitslow
@patch("platform.system")
def test_shouldFilterPacket_in_blacklist(
    mock_platform_system, caplog, iface_with_nodes
):
    """Test _shouldFilterPacket()"""
    iface = iface_with_nodes
    iface.noProto = True
    # faked IGMP
    packet = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.DEBUG):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            ignore = tun._shouldFilterPacket(packet)
            assert ignore


@pytest.mark.unitslow
@patch("platform.system")
def test_shouldFilterPacket_icmp(mock_platform_system, caplog, iface_with_nodes):
    """Test _shouldFilterPacket()"""
    iface = iface_with_nodes
    iface.noProto = True
    # faked ICMP
    packet = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.DEBUG):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            ignore = tun._shouldFilterPacket(packet)
            assert re.search(r"forwarding ICMP message", caplog.text, re.MULTILINE)
            assert not ignore


@pytest.mark.unit
@patch("platform.system")
def test_shouldFilterPacket_udp(mock_platform_system, caplog, iface_with_nodes):
    """Test _shouldFilterPacket()"""
    iface = iface_with_nodes
    iface.noProto = True
    # faked UDP
    packet = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x11\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.DEBUG):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            ignore = tun._shouldFilterPacket(packet)
            assert re.search(r"forwarding udp", caplog.text, re.MULTILINE)
            assert not ignore


@pytest.mark.unitslow
@patch("platform.system")
def test_shouldFilterPacket_udp_blacklisted(
    mock_platform_system, caplog, iface_with_nodes
):
    """Test _shouldFilterPacket()"""
    iface = iface_with_nodes
    iface.noProto = True
    # faked UDP
    packet = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x11\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x07\x6c\x07\x6c\x00\x00\x00"
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    # Note: custom logging level
    LOG_TRACE = 5
    with caplog.at_level(LOG_TRACE):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            ignore = tun._shouldFilterPacket(packet)
            assert re.search(r"ignoring blacklisted UDP", caplog.text, re.MULTILINE)
            assert ignore


@pytest.mark.unit
@patch("platform.system")
def test_shouldFilterPacket_tcp(mock_platform_system, caplog, iface_with_nodes):
    """Test _shouldFilterPacket()"""
    iface = iface_with_nodes
    iface.noProto = True
    # faked TCP
    packet = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.DEBUG):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            ignore = tun._shouldFilterPacket(packet)
            assert re.search(r"forwarding tcp", caplog.text, re.MULTILINE)
            assert not ignore


@pytest.mark.unitslow
@patch("platform.system")
def test_shouldFilterPacket_tcp_blacklisted(
    mock_platform_system, caplog, iface_with_nodes
):
    """Test _shouldFilterPacket()"""
    iface = iface_with_nodes
    iface.noProto = True
    # faked TCP
    packet = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x17\x0c\x17\x0c\x00\x00\x00"
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    # Note: custom logging level
    LOG_TRACE = 5
    with caplog.at_level(LOG_TRACE):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            ignore = tun._shouldFilterPacket(packet)
            assert re.search(r"ignoring blacklisted TCP", caplog.text, re.MULTILINE)
            assert ignore


@pytest.mark.unitslow
@patch("platform.system")
def test_ipToNodeId_none(mock_platform_system, caplog, iface_with_nodes):
    """Test _ipToNodeId()"""
    iface = iface_with_nodes
    iface.noProto = True
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.DEBUG):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            nodeid = tun._ipToNodeId("something not useful")
            assert nodeid is None


@pytest.mark.unitslow
@patch("platform.system")
def test_ipToNodeId_all(mock_platform_system, caplog, iface_with_nodes):
    """Test _ipToNodeId()"""
    iface = iface_with_nodes
    iface.noProto = True
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    with caplog.at_level(logging.DEBUG):
        with patch("socket.socket"):
            tun = Tunnel(iface)
            nodeid = tun._ipToNodeId(b"\x00\x00\xff\xff")
            assert nodeid == "^all"
