"""Meshtastic unit tests for serial_interface.py"""

from unittest.mock import patch
import pytest

from ..serial_interface import SerialInterface

@pytest.mark.unit
@patch('serial.Serial')
@patch('meshtastic.util.findPorts', return_value=['/dev/ttyUSBfake'])
def test_SerialInterface(mocked_findPorts, mocked_serial):
    """Test that we can instantiate a SerialInterface"""
    iface = SerialInterface(noProto=True)
    iface.showInfo()
    iface.localNode.showInfo()
    iface.close()
    mocked_findPorts.assert_called()
    mocked_serial.assert_called()
