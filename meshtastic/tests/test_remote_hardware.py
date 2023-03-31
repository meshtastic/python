"""Meshtastic unit tests for remote_hardware.py"""

import logging
import re
from unittest.mock import MagicMock, patch

import pytest

from ..remote_hardware import RemoteHardwareClient, onGPIOreceive
from ..serial_interface import SerialInterface


@pytest.mark.unit
def test_RemoteHardwareClient():
    """Test that we can instantiate a RemoteHardwareClient instance"""
    iface = MagicMock(autospec=SerialInterface)
    rhw = RemoteHardwareClient(iface)
    assert rhw.iface == iface
    iface.close()


@pytest.mark.unit
def test_onGPIOreceive(capsys):
    """Test onGPIOreceive"""
    iface = MagicMock(autospec=SerialInterface)
    packet = {"decoded": {"remotehw": {"type": "foo", "gpioValue": "4096"}}}
    onGPIOreceive(packet, iface)
    out, err = capsys.readouterr()
    assert re.search(r"Received RemoteHardware", out)
    assert err == ""


@pytest.mark.unit
def test_RemoteHardwareClient_no_gpio_channel(capsys):
    """Test that we can instantiate a RemoteHardwareClient instance but there is no channel named channel 'gpio'"""
    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        mo.localNode.getChannelByName.return_value = None
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            RemoteHardwareClient(mo)
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"Warning: No channel named", out)
        assert err == ""


@pytest.mark.unit
def test_readGPIOs(caplog):
    """Test readGPIOs"""
    iface = MagicMock(autospec=SerialInterface)
    rhw = RemoteHardwareClient(iface)
    with caplog.at_level(logging.DEBUG):
        rhw.readGPIOs("0x10", 123)
    assert re.search(r"readGPIOs", caplog.text, re.MULTILINE)
    iface.close()


@pytest.mark.unit
def test_writeGPIOs(caplog):
    """Test writeGPIOs"""
    iface = MagicMock(autospec=SerialInterface)
    rhw = RemoteHardwareClient(iface)
    with caplog.at_level(logging.DEBUG):
        rhw.writeGPIOs("0x10", 123, 1)
    assert re.search(r"writeGPIOs", caplog.text, re.MULTILINE)
    iface.close()


@pytest.mark.unit
def test_watchGPIOs(caplog):
    """Test watchGPIOs"""
    iface = MagicMock(autospec=SerialInterface)
    rhw = RemoteHardwareClient(iface)
    with caplog.at_level(logging.DEBUG):
        rhw.watchGPIOs("0x10", 123)
    assert re.search(r"watchGPIOs", caplog.text, re.MULTILINE)
    iface.close()


@pytest.mark.unit
def test_sendHardware_no_nodeid(capsys):
    """Test sending no nodeid to _sendHardware()"""
    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            rhw = RemoteHardwareClient(mo)
            rhw._sendHardware(None, None)
        assert pytest_wrapped_e.type == SystemExit
    out, err = capsys.readouterr()
    assert re.search(r"Warning: Must use a destination node ID", out)
    assert err == ""
