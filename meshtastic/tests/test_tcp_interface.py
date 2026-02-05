"""Meshtastic unit tests for tcp_interface.py"""

import re
from unittest.mock import patch

import pytest

from ..protobuf import config_pb2
from ..tcp_interface import TCPInterface


@pytest.mark.unit
def test_TCPInterface(capsys):
    """Test that we can instantiate a TCPInterface"""
    with patch("socket.socket") as mock_socket:
        iface = TCPInterface(hostname="localhost", noProto=True)
        iface.localNode.localConfig.lora.CopyFrom(config_pb2.Config.LoRaConfig())
        iface.myConnect()
        iface.showInfo()
        iface.localNode.showInfo()
        out, err = capsys.readouterr()
        assert re.search(r"Owner: None \(None\)", out, re.MULTILINE)
        assert re.search(r"Nodes", out, re.MULTILINE)
        assert re.search(r"Preferences", out, re.MULTILINE)
        assert re.search(r"Channels", out, re.MULTILINE)
        assert re.search(r"Primary channel URL", out, re.MULTILINE)
        assert err == ""
        assert mock_socket.called
        iface.close()


@pytest.mark.unit
def test_TCPInterface_exception():
    """Test that we can instantiate a TCPInterface"""

    def throw_an_exception():
        raise ValueError("Fake exception.")

    with patch(
        "meshtastic.tcp_interface.TCPInterface._socket_shutdown"
    ) as mock_shutdown:
        mock_shutdown.side_effect = throw_an_exception
        with patch("socket.socket") as mock_socket:
            iface = TCPInterface(hostname="localhost", noProto=True)
            iface.myConnect()
            iface.close()
            assert mock_socket.called
            assert mock_shutdown.called


@pytest.mark.unit
def test_TCPInterface_without_connecting():
    """Test that we can instantiate a TCPInterface with connectNow as false"""
    with patch("socket.socket"):
        iface = TCPInterface(hostname="localhost", noProto=True, connectNow=False)
        assert iface.socket is None


@pytest.mark.unit
def test_TCPInterface_reconnect():
    """Test that _reconnect correctly reconnects"""
    with patch("socket.socket") as mock_socket:
        with patch("time.sleep"):
            iface = TCPInterface(hostname="localhost", noProto=True)
            old_socket = iface.socket
            assert old_socket is not None
            
            iface._reconnect()
            
            assert old_socket.close.called
            # We expect socket class to be instantiated at least twice (init + reconnect)
            assert mock_socket.call_count >= 2


@pytest.mark.unit
def test_TCPInterface_writeBytes_reconnects():
    """Test that _writeBytes calls _reconnect on OSError"""
    with patch("socket.socket"):
        iface = TCPInterface(hostname="localhost", noProto=True)
        iface.socket.sendall.side_effect = OSError("Broken pipe")
        
        with patch.object(iface, '_reconnect') as mock_reconnect:
            iface._writeBytes(b"some data")
            mock_reconnect.assert_called_once()


@pytest.mark.unit
def test_TCPInterface_readBytes_reconnects():
    """Test that _readBytes calls _reconnect on empty bytes"""
    with patch("socket.socket"):
        iface = TCPInterface(hostname="localhost", noProto=True)
        # Mock the socket instance on the interface
        iface.socket.recv.return_value = b''
        
        with patch.object(iface, '_reconnect') as mock_reconnect:
            iface._readBytes(10)
            mock_reconnect.assert_called_once()
