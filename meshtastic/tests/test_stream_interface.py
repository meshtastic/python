"""Meshtastic unit tests for stream_interface.py"""


import pytest

from ..stream_interface import StreamInterface


@pytest.mark.unit
def test_StreamInterface():
    """Test that we cannot instantiate a StreamInterface"""
    with pytest.raises(Exception) as pytest_wrapped_e:
        StreamInterface(noProto=True)
    assert pytest_wrapped_e.type == Exception
