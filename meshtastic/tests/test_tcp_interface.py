"""Meshtastic unit tests for tcp_interface.py"""

import re
import socket
from unittest.mock import MagicMock, patch

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
        ifData = iface.getInfo()
        nodeData = iface.localNode.getInfo()

        assert mock_socket.called
        iface.close()

        # test interface data
        assert 'Owner' in ifData.keys()
        assert len(ifData.get('Owner', [])) == 2
        assert ifData['Owner'][0] is None
        assert ifData['Owner'][1] is None
        assert 'MyInfo' in ifData.keys()
        assert 'Metadata' in ifData.keys()
        assert 'Nodes' in ifData.keys()

        # test node data
        assert 'Preferences' in nodeData.keys()
        assert 'ModulePreferences' in nodeData.keys()
        assert 'Channels' in nodeData.keys()
        assert 'publicURL' in nodeData.keys()
        assert 'adminURL' in nodeData.keys()


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
def test_TCPInterface_close_shutdowns_socket_before_super_close():
    """Close should unblock socket reads before waiting on StreamInterface.close()."""
    iface = TCPInterface(hostname="localhost", noProto=True, connectNow=False)
    sock = MagicMock()
    iface.socket = sock
    call_order = []

    with patch.object(TCPInterface, "_socket_shutdown", autospec=True) as mock_shutdown:
        with patch(
            "meshtastic.stream_interface.StreamInterface.close", autospec=True
        ) as mock_super_close:
            mock_shutdown.side_effect = lambda _self: call_order.append("shutdown")
            mock_super_close.side_effect = lambda _self: call_order.append("super_close")

            iface.close()

    assert call_order == ["shutdown", "super_close"]
    sock.close.assert_called_once()
    assert iface.socket is None


@pytest.mark.unit
def test_TCPInterface_close_half_closes_before_shutdown():
    """Close should send FIN and let the device drain before forcing the link down.

    Going straight to shutdown(SHUT_RDWR)/close() with data still unread makes the
    stack send RST, and Winsock then discards data the device had received but not
    yet read, silently losing writes such as `--set`.
    """
    iface = TCPInterface(hostname="localhost", noProto=True, connectNow=False)
    sock = MagicMock()
    iface.socket = sock
    call_order = []

    with patch.object(TCPInterface, "_socket_shutdown", autospec=True) as mock_shutdown:
        with patch.object(
            TCPInterface, "_wait_for_reader_exit", autospec=True
        ) as mock_wait:
            with patch(
                "meshtastic.stream_interface.StreamInterface.close", autospec=True
            ) as mock_super_close:
                sock.shutdown.side_effect = lambda how: call_order.append(f"shutdown_{how}")
                mock_wait.side_effect = lambda _self, _t: call_order.append("wait")
                mock_shutdown.side_effect = lambda _self: call_order.append("full_shutdown")
                mock_super_close.side_effect = lambda _self: call_order.append("super_close")

                iface.close()

    assert call_order == [
        f"shutdown_{socket.SHUT_WR}",
        "wait",
        "full_shutdown",
        "super_close",
    ]


@pytest.mark.unit
def test_TCPInterface_close_survives_half_close_failure():
    """A peer that already vanished must not break close()."""
    iface = TCPInterface(hostname="localhost", noProto=True, connectNow=False)
    sock = MagicMock()
    sock.shutdown.side_effect = OSError("already gone")
    iface.socket = sock

    with patch("meshtastic.stream_interface.StreamInterface.close", autospec=True):
        iface.close()  # must not raise

    sock.close.assert_called_once()
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
    """Test that _writeBytes reconnects and re-raises on OSError."""
    with patch("socket.socket"):
        iface = TCPInterface(hostname="localhost", noProto=True)
        iface.socket.sendall.side_effect = OSError("Broken pipe")

        with patch.object(iface, "_reconnect") as mock_reconnect:
            with pytest.raises(OSError, match="Broken pipe"):
                iface._writeBytes(b"some data")
            mock_reconnect.assert_called_once()


@pytest.mark.unit
def test_TCPInterface_readBytes_reconnects():
    """Test that _readBytes calls _reconnect on empty bytes"""
    iface = TCPInterface(hostname="localhost", noProto=True, connectNow=False)
    iface.socket = MagicMock()
    iface.socket.recv.return_value = b""

    with patch.object(iface, "_reconnect") as mock_reconnect:
        iface._readBytes(10)
        mock_reconnect.assert_called_once()
