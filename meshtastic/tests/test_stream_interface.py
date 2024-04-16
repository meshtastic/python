"""Meshtastic unit tests for stream_interface.py"""

import logging
from unittest.mock import MagicMock

import pytest

from ..stream_interface import StreamInterface

# import re


@pytest.mark.unit
def test_StreamInterface():
    """Test that we cannot instantiate a StreamInterface based on noProto"""
    with pytest.raises(Exception) as pytest_wrapped_e:
        StreamInterface()
    assert pytest_wrapped_e.type == Exception


# Note: This takes a bit, so moving from unit to slow
@pytest.mark.unitslow
@pytest.mark.usefixtures("reset_mt_config")
def test_StreamInterface_with_noProto(caplog):
    """Test that we can instantiate a StreamInterface based on nonProto
    and we can read/write bytes from a mocked stream
    """
    stream = MagicMock()
    test_data = b"hello"
    stream.read.return_value = test_data
    with caplog.at_level(logging.DEBUG):
        iface = StreamInterface(noProto=True, connectNow=False)
        iface.stream = stream
        iface._writeBytes(test_data)
        data = iface._readBytes(len(test_data))
        assert data == test_data


# TODO
### Note: This takes a bit, so moving from unit to slow
### Tip: If you want to see the print output, run with '-s' flag:
###      pytest -s meshtastic/tests/test_stream_interface.py::test_sendToRadioImpl
# @pytest.mark.unitslow
# @pytest.mark.usefixtures("reset_mt_config")
# def test_sendToRadioImpl(caplog):
#    """Test _sendToRadioImpl()"""
#
##    def add_header(b):
##        """Add header stuffs for radio"""
##        bufLen = len(b)
##        header = bytes([START1, START2, (bufLen >> 8) & 0xff,  bufLen & 0xff])
##        return header + b
#
#    # captured raw bytes of a Heltec2.1 radio with 2 channels (primary and a secondary channel named "gpio")
#    raw_1_my_info = b'\x1a,\x08\xdc\x8c\xd5\xc5\x02\x18\r2\x0e1.2.49.5354c49P\x15]\xe1%\x17Eh\xe0\xa7\x12p\xe8\x9d\x01x\x08\x90\x01\x01'
#    raw_2_node_info = b'"9\x08\xdc\x8c\xd5\xc5\x02\x12(\n\t!28b5465c\x12\x0cUnknown 465c\x1a\x03?5C"\x06$o(\xb5F\\0\n\x1a\x02 1%M<\xc6a'
#    # pylint: disable=C0301
#    raw_3_node_info = b'"C\x08\xa4\x8c\xd5\xc5\x02\x12(\n\t!28b54624\x12\x0cUnknown 4624\x1a\x03?24"\x06$o(\xb5F$0\n\x1a\x07 5MH<\xc6a%G<\xc6a=\x00\x00\xc0@'
#    raw_4_complete = b'@\xcf\xe5\xd1\x8c\x0e'
#    # pylint: disable=C0301
#    raw_5_prefs = b'Z6\r\\F\xb5(\x15\\F\xb5("\x1c\x08\x06\x12\x13*\x11\n\x0f0\x84\x07P\xac\x02\x88\x01\x01\xb0\t#\xb8\t\x015]$\xddk5\xd5\x7f!b=M<\xc6aP\x03`F'
#    # pylint: disable=C0301
#    raw_6_channel0 = b'Z.\r\\F\xb5(\x15\\F\xb5("\x14\x08\x06\x12\x0b:\t\x12\x05\x18\x01"\x01\x01\x18\x015^$\xddk5\xd6\x7f!b=M<\xc6aP\x03`F'
#    # pylint: disable=C0301
#    raw_7_channel1 = b'ZS\r\\F\xb5(\x15\\F\xb5("9\x08\x06\x120:.\x08\x01\x12(" \xb4&\xb3\xc7\x06\xd8\xe39%\xba\xa5\xee\x8eH\x06\xf6\xf4H\xe8\xd5\xc1[ao\xb5Y\\\xb4"\xafmi*\x04gpio\x18\x025_$\xddk5\xd7\x7f!b=M<\xc6aP\x03`F'
#    raw_8_channel2 = b'Z)\r\\F\xb5(\x15\\F\xb5("\x0f\x08\x06\x12\x06:\x04\x08\x02\x12\x005`$\xddk5\xd8\x7f!b=M<\xc6aP\x03`F'
#    raw_blank = b''
#
#    test_data = b'hello'
#    stream = MagicMock()
#    #stream.read.return_value = add_header(test_data)
#    stream.read.side_effect = [ raw_1_my_info, raw_2_node_info, raw_3_node_info, raw_4_complete,
#                                raw_5_prefs, raw_6_channel0, raw_7_channel1, raw_8_channel2,
#                                raw_blank, raw_blank]
#    toRadio = MagicMock()
#    toRadio.SerializeToString.return_value = test_data
#    with caplog.at_level(logging.DEBUG):
#        iface = StreamInterface(noProto=True, connectNow=False)
#        iface.stream = stream
#        iface.connect()
#        iface._sendToRadioImpl(toRadio)
#        assert re.search(r'Sending: ', caplog.text, re.MULTILINE)
#        assert re.search(r'reading character', caplog.text, re.MULTILINE)
#        assert re.search(r'In reader loop', caplog.text, re.MULTILINE)
