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
