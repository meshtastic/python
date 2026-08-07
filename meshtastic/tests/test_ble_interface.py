"""Meshtastic unit tests for ble_interface.py"""

from concurrent.futures import TimeoutError as FutureTimeoutError
from unittest.mock import MagicMock, patch

import pytest
from bleak.exc import BleakDBusError, BleakError

from ..ble_interface import BLE_DISCONNECT_TIMEOUT, BLEClient, BLEInterface


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


@pytest.mark.unit
def test_ble_receive_disconnect_mid_read_unwinds_cleanly():
    """A disconnect mid-read (BleakDBusError) must stop the receive loop
    without raising UnboundLocalError on the `b` read buffer."""
    iface = object.__new__(BLEInterface)
    iface.should_read = True
    iface._want_receive = True
    iface.client = MagicMock()
    iface.client.read_gatt_char.side_effect = BleakDBusError(
        "org.bluez.Error.Failed", []
    )
    # Must return normally (no UnboundLocalError) and halt the loop.
    iface._receiveFromRadioImpl()
    assert iface._want_receive is False


@pytest.mark.unit
def test_ble_client_disconnect_swallows_stalled_teardown():
    """BLEClient.disconnect must bound the wait with BLE_DISCONNECT_TIMEOUT and
    not propagate a stalled-teardown timeout, so BLEInterface.close() can always
    finish."""
    client = object.__new__(BLEClient)
    client.bleak_client = MagicMock()
    with patch.object(
        BLEClient, "async_await", side_effect=FutureTimeoutError()
    ) as async_await:
        client.disconnect()  # must not raise
    # the wait must actually be bounded, not left unbounded
    assert async_await.call_args.kwargs["timeout"] == BLE_DISCONNECT_TIMEOUT
    with patch.object(BLEClient, "async_await", side_effect=BleakError("gone")):
        client.disconnect()  # must not raise


@pytest.mark.unit
def test_ble_client_close_bounds_event_thread_join():
    """BLEClient.close must bound the event-loop thread join so a stuck loop
    cannot block teardown forever."""
    client = object.__new__(BLEClient)
    client._eventThread = MagicMock()
    # Force a plain (non-async) mock for the coroutine method so we don't create
    # an un-awaited coroutine when close() calls it.
    with patch.object(BLEClient, "async_run") as async_run, patch.object(
        BLEClient, "_stop_event_loop", new=MagicMock()
    ):
        client.close()
    async_run.assert_called_once()
    client._eventThread.join.assert_called_once_with(timeout=BLE_DISCONNECT_TIMEOUT)


@pytest.mark.unit
def test_ble_client_async_await_cancels_future_on_timeout():
    """On timeout, async_await must cancel the pending future so a stalled
    coroutine is not left running on the event loop."""
    client = object.__new__(BLEClient)
    future = MagicMock()
    future.result.side_effect = FutureTimeoutError()
    with patch.object(BLEClient, "async_run", return_value=future):
        with pytest.raises(FutureTimeoutError):
            client.async_await("coro", timeout=BLE_DISCONNECT_TIMEOUT)
    future.cancel.assert_called_once()
