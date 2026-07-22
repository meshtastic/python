"""Meshtastic unit tests for ble_interface.py"""

from unittest.mock import MagicMock, patch

import pytest
from bleak.exc import BleakError

from ..ble_interface import BLEInterface


@pytest.mark.unit
def test_ble_error_default_kind_unknown():
    """BLEError defaults to UNKNOWN kind."""
    error = BLEInterface.BLEError("test")
    assert error.kind == BLEInterface.BLEError.UNKNOWN


@pytest.mark.unit
def test_ble_find_device_not_found_sets_kind():
    """find_device emits DEVICE_NOT_FOUND for no scan results."""
    iface = object.__new__(BLEInterface)
    with patch("meshtastic.ble_interface.BLEInterface.scan", return_value=[]):
        with pytest.raises(BLEInterface.BLEError) as excinfo:
            iface.find_device("missing")
    assert excinfo.value.kind == BLEInterface.BLEError.DEVICE_NOT_FOUND


@pytest.mark.unit
def test_ble_find_device_multiple_sets_kind():
    """find_device emits MULTIPLE_DEVICES for ambiguous matches."""
    iface = object.__new__(BLEInterface)
    first = MagicMock()
    first.name = "dup"
    first.address = "AA:AA:AA:AA:AA:01"
    second = MagicMock()
    second.name = "dup"
    second.address = "AA:AA:AA:AA:AA:02"
    with patch(
        "meshtastic.ble_interface.BLEInterface.scan", return_value=[first, second]
    ):
        with pytest.raises(BLEInterface.BLEError) as excinfo:
            iface.find_device("dup")
    assert excinfo.value.kind == BLEInterface.BLEError.MULTIPLE_DEVICES


@pytest.mark.unit
def test_ble_send_to_radio_wraps_write_errors_with_kind():
    """_sendToRadioImpl wraps write failures with WRITE_ERROR."""
    iface = object.__new__(BLEInterface)
    iface.client = MagicMock()
    iface.client.write_gatt_char.side_effect = RuntimeError("boom")
    to_radio = MagicMock()
    to_radio.SerializeToString.return_value = b"\x01"
    with pytest.raises(BLEInterface.BLEError) as excinfo:
        iface._sendToRadioImpl(to_radio)
    assert excinfo.value.kind == BLEInterface.BLEError.WRITE_ERROR


@pytest.mark.unit
def test_ble_receive_wraps_unexpected_bleak_error_with_kind():
    """_receiveFromRadioImpl wraps unexpected BleakError with READ_ERROR."""
    iface = object.__new__(BLEInterface)
    iface.should_read = True
    iface._want_receive = True
    iface.client = MagicMock()
    iface.client.read_gatt_char.side_effect = BleakError("some other BLE failure")
    with pytest.raises(BLEInterface.BLEError) as excinfo:
        iface._receiveFromRadioImpl()
    assert excinfo.value.kind == BLEInterface.BLEError.READ_ERROR
