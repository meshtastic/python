"""Meshtastic unit tests for ble_interface.py"""

import threading
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


@pytest.mark.unit
def test_ble_close_reentrant_does_not_deadlock() -> None:
    """close() must not deadlock when disconnect callback re-enters close()."""
    iface = object.__new__(BLEInterface)
    iface._closing = False
    iface._want_receive = False
    iface._receiveThread = None

    disconnect_count = 0

    def fake_disconnect():
        nonlocal disconnect_count
        disconnect_count += 1
        iface.close()  # re-entrant call — should return immediately

    mock_client = MagicMock()
    mock_client.disconnect.side_effect = fake_disconnect
    iface.client = mock_client
    iface._exit_handler = lambda: None

    with patch("meshtastic.mesh_interface.MeshInterface.close"), \
         patch.object(iface, "_disconnected"):
        iface.close()
        iface.close()  # A completed close must also remain idempotent.

    assert disconnect_count == 1, "disconnect() should be called exactly once"
    assert iface.client is None, "client should be cleaned up"


@pytest.mark.unit
@pytest.mark.parametrize("failure", ["join", "disconnect", "close", "notification"])
def test_ble_close_can_retry_after_cleanup_failure(failure) -> None:
    """A failed cleanup must not permanently disable close()."""
    iface = object.__new__(BLEInterface)
    iface._closing = False
    iface._want_receive = True
    receive_thread = MagicMock()
    iface._receiveThread = receive_thread
    client = MagicMock()
    iface.client = client
    iface._exit_handler = lambda: None
    notification = MagicMock()
    iface._disconnected = notification # type: ignore[method-assign]
    failing_step = {
        "join": receive_thread.join,
        "disconnect": client.disconnect,
        "close": client.close,
        "notification": notification,
    }[failure]
    failing_step.side_effect = RuntimeError("cleanup failed")

    with patch("meshtastic.mesh_interface.MeshInterface.close"), \
         patch("meshtastic.ble_interface.atexit.unregister") as unregister:
        with pytest.raises(RuntimeError, match="cleanup failed"):
            iface.close()

        assert iface._closing is False
        if failure != "notification":
            assert iface.client is client
            unregister.assert_not_called()

        failing_step.side_effect = None
        iface.close()
        iface.close()

    assert iface._closing is True
    assert iface.client is None
    assert iface._receiveThread is None
    assert iface._want_receive is False
    assert failing_step.call_count == 2
    unregister.assert_called_once_with(iface._exit_handler)
    client.close.assert_called()
    notification.assert_called()


@pytest.mark.unit
def test_ble_disconnected_callback_closes_off_the_event_loop() -> None:
    """bleak runs the disconnected callback on BLEClient's event loop; close() waits on that loop,
    so the callback must hand close() to another thread instead of calling it inline."""
    iface = object.__new__(BLEInterface)
    caller = threading.current_thread()
    closed_on = []
    done = threading.Event()

    def fake_close() -> None:
        closed_on.append(threading.current_thread())
        done.set()

    with patch.object(iface, "close", side_effect=fake_close):
        iface._on_disconnected(MagicMock())
        assert done.wait(timeout=5), "close() was never called"

    assert closed_on[0] is not caller, "close() ran on the callback's (event loop) thread"


@pytest.mark.unit
def test_ble_connect_registers_disconnected_callback() -> None:
    """connect() must hand bleak _on_disconnected, not a callback that closes inline on the event loop."""
    iface = object.__new__(BLEInterface)
    device = MagicMock()
    with patch.object(iface, "find_device", return_value=device), \
         patch("meshtastic.ble_interface.BLEClient") as client_cls:
        iface.connect("node")
    callback = client_cls.call_args.kwargs["disconnected_callback"]
    assert callback.__func__ is BLEInterface._on_disconnected and callback.__self__ is iface


@pytest.mark.unit
def test_ble_receive_stops_quietly_when_device_dropped_link() -> None:
    """A read in flight when the device drops the link (any BleakError wording) ends the reader, not raises."""
    iface = object.__new__(BLEInterface)
    iface.should_read = True
    iface._want_receive = True
    iface.client = MagicMock()
    iface.client.bleak_client.is_connected = False
    iface.client.read_gatt_char.side_effect = BleakError("Peripheral disconnected")
    iface._receiveFromRadioImpl()
    assert iface._want_receive is False


@pytest.mark.unit
def test_ble_close_before_atexit_handler_registered() -> None:
    """The device can drop the link mid-__init__, after self.client is set but before the atexit
    handler is registered; close() must still clean up."""
    iface = object.__new__(BLEInterface)
    iface._closing = False
    iface._want_receive = False
    iface._receiveThread = None
    client = MagicMock()
    iface.client = client
    with patch("meshtastic.mesh_interface.MeshInterface.close"), \
         patch.object(iface, "_disconnected") as notification:
        iface.close()
    client.disconnect.assert_called_once()
    assert iface.client is None
    notification.assert_called_once()
