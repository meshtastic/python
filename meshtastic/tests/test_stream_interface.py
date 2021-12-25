"""Meshtastic unit tests for stream_interface.py"""

import logging
import re

from unittest.mock import MagicMock
import pytest

from ..stream_interface import StreamInterface


@pytest.mark.unit
def test_StreamInterface():
    """Test that we cannot instantiate a StreamInterface based on noProto"""
    with pytest.raises(Exception) as pytest_wrapped_e:
        StreamInterface()
    assert pytest_wrapped_e.type == Exception


# Note: This takes a bit, so moving from unit to slow
@pytest.mark.unitslow
def test_StreamInterface_with_noProto(caplog, reset_globals):
    """Test that we can instantiate a StreamInterface based on nonProto
       and we can read/write bytes from a mocked stream
    """
    stream = MagicMock()
    test_data = b'hello'
    stream.read.return_value = test_data
    with caplog.at_level(logging.DEBUG):
        iface = StreamInterface(noProto=True)
        iface.stream = stream
        iface._writeBytes(test_data)
        data = iface._readBytes(len(test_data))
        assert data == test_data


# Note: This takes a bit, so moving from unit to slow
@pytest.mark.unitslow
def test_sendToRadioImpl(caplog, reset_globals):
    """Test _sendToRadioImpl()"""
    test_data = b'hello'
    stream = MagicMock()
    stream.read.return_value = test_data
    toRadio = MagicMock()
    toRadio.SerializeToString.return_value = test_data
    with caplog.at_level(logging.DEBUG):
        iface = StreamInterface(noProto=True, connectNow=False)
        iface.stream = stream
        iface.connect()
        iface._sendToRadioImpl(toRadio)
        assert re.search(r'Sending: ', caplog.text, re.MULTILINE)
        assert re.search(r'reading character', caplog.text, re.MULTILINE)
        assert re.search(r'In reader loop', caplog.text, re.MULTILINE)
