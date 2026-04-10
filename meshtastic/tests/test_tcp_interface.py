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
