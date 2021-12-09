"""Meshtastic unit tests for serial_interface.py"""

import re


from unittest.mock import patch
import pytest

from ..serial_interface import SerialInterface

@pytest.mark.unit
@patch('serial.Serial')
@patch('meshtastic.util.findPorts', return_value=['/dev/ttyUSBfake'])
def test_SerialInterface_single_port(mocked_findPorts, mocked_serial):
    """Test that we can instantiate a SerialInterface with a single port"""
    iface = SerialInterface(noProto=True)
    iface.showInfo()
    iface.localNode.showInfo()
    iface.close()
    mocked_findPorts.assert_called()
    mocked_serial.assert_called()


@pytest.mark.unit
@patch('meshtastic.util.findPorts', return_value=[])
def test_SerialInterface_no_ports(mocked_findPorts, capsys):
    """Test that we can instantiate a SerialInterface with no ports"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        SerialInterface(noProto=True)
    mocked_findPorts.assert_called()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.search(r'Warning: No Meshtastic devices detected', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@patch('meshtastic.util.findPorts', return_value=['/dev/ttyUSBfake1', '/dev/ttyUSBfake2'])
def test_SerialInterface_multiple_ports(mocked_findPorts, capsys):
    """Test that we can instantiate a SerialInterface with two ports"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        SerialInterface(noProto=True)
    mocked_findPorts.assert_called()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.search(r'Warning: Multiple serial ports were detected', out, re.MULTILINE)
    assert err == ''
