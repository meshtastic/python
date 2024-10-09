"""Meshtastic unit tests for serial_interface.py"""

import re
from unittest.mock import mock_open, patch

import pytest

from ..serial_interface import SerialInterface
from ..protobuf import config_pb2


@pytest.mark.unit
@patch("time.sleep")
@patch("termios.tcsetattr")
@patch("termios.tcgetattr")
@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("serial.Serial")
@patch("meshtastic.util.findPorts", return_value=["/dev/ttyUSBfake"])
def test_SerialInterface_single_port(
    mocked_findPorts, mocked_serial, mocked_open, mock_get, mock_set, mock_sleep, capsys
):
    """Test that we can instantiate a SerialInterface with a single port"""
    iface = SerialInterface(noProto=True)
    iface.localNode.localConfig.lora.CopyFrom(config_pb2.Config.LoRaConfig())
    iface.showInfo()
    iface.localNode.showInfo()
    iface.close()
    mocked_findPorts.assert_called()
    mocked_serial.assert_called()
    mocked_open.assert_called()
    mock_get.assert_called()
    mock_set.assert_called()
    mock_sleep.assert_called()
    out, err = capsys.readouterr()
    assert re.search(r"Nodes in mesh", out, re.MULTILINE)
    assert re.search(r"Preferences", out, re.MULTILINE)
    assert re.search(r"Channels", out, re.MULTILINE)
    assert re.search(r"Primary channel", out, re.MULTILINE)
    assert err == ""


@pytest.mark.unit
@patch("meshtastic.util.findPorts", return_value=[])
def test_SerialInterface_no_ports(mocked_findPorts, capsys):
    """Test that we can instantiate a SerialInterface with no ports"""
    serialInterface = SerialInterface(noProto=True)
    mocked_findPorts.assert_called()
    assert serialInterface.devPath is None
    out, err = capsys.readouterr()
    assert re.search(r"No.*Meshtastic.*device.*detected", out, re.MULTILINE)
    assert err == ""


@pytest.mark.unit
@patch(
    "meshtastic.util.findPorts", return_value=["/dev/ttyUSBfake1", "/dev/ttyUSBfake2"]
)
def test_SerialInterface_multiple_ports(mocked_findPorts, capsys):
    """Test that we can instantiate a SerialInterface with two ports"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        SerialInterface(noProto=True)
    mocked_findPorts.assert_called()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.search(r"Warning: Multiple serial ports were detected", out, re.MULTILINE)
    assert err == ""
