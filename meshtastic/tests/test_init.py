"""Meshtastic unit tests for __init__.py"""

import logging
import re
from unittest.mock import MagicMock

import pytest

from meshtastic import _onNodeInfoReceive, _onPositionReceive, _onTextReceive, mt_config

from ..serial_interface import SerialInterface


@pytest.mark.unit
def test_init_onTextReceive_with_exception(caplog):
    """Test _onTextReceive"""
    args = MagicMock()
    mt_config.args = args
    iface = MagicMock(autospec=SerialInterface)
    packet = {}
    with caplog.at_level(logging.DEBUG):
        _onTextReceive(iface, packet)
    assert re.search(r"in _onTextReceive", caplog.text, re.MULTILINE)
    assert re.search(r"Malformatted", caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_init_onPositionReceive(caplog):
    """Test _onPositionReceive"""
    args = MagicMock()
    mt_config.args = args
    iface = MagicMock(autospec=SerialInterface)
    packet = {"from": "foo", "decoded": {"position": {}}}
    with caplog.at_level(logging.DEBUG):
        _onPositionReceive(iface, packet)
    assert re.search(r"in _onPositionReceive", caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_init_onNodeInfoReceive(caplog, iface_with_nodes):
    """Test _onNodeInfoReceive"""
    args = MagicMock()
    mt_config.args = args
    iface = iface_with_nodes
    iface.myInfo.my_node_num = 2475227164
    packet = {
        "from": 4808675309,
        "decoded": {
            "user": {
                "id": "bar",
            },
        },
    }
    with caplog.at_level(logging.DEBUG):
        _onNodeInfoReceive(iface, packet)
    assert re.search(r"in _onNodeInfoReceive", caplog.text, re.MULTILINE)
