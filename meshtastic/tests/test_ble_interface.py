"""Meshtastic unit tests for ble_interface.py"""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.exc import BleakError

from ..ble_interface import BLEClient, BLEInterface


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
def test_ble_client_serializes_gatt_operations() -> None:
    """async_await from several threads must not run two GATT operations at once.

    On macOS, an operation started while another is in flight (e.g. the BLEReceive thread's
    heartbeat write at config-complete racing the caller's start_notify) may never complete,
    blocking that thread forever."""
    client = BLEClient()  # no address: event loop only, no BleakClient
    active = 0
    peak = 0
    finished = []

    async def gatt_op() -> None:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1

    def run_op() -> None:
        client.async_await(gatt_op())
        finished.append(True)

    try:
        threads = [threading.Thread(target=run_op, daemon=True) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
    finally:
        client.close()

    assert len(finished) == 4, f"only {len(finished)} of 4 operations completed"
    assert peak == 1, f"{peak} GATT operations ran concurrently"


@pytest.mark.unit
def test_ble_client_disconnect_does_not_wait_for_a_hung_operation() -> None:
    """disconnect() is the way out of an operation that never completes, so it must not queue behind it."""
    client = BLEClient()
    client.bleak_client = MagicMock()
    client.bleak_client.disconnect = AsyncMock()
    done = threading.Event()

    def disconnect() -> None:
        client.disconnect()
        done.set()

    try:
        with client._gatt_lock:  # an operation in flight that never completes
            threading.Thread(target=disconnect, daemon=True).start()
            assert done.wait(timeout=5), "disconnect() waited for the in-flight operation"
    finally:
        client.close()
    client.bleak_client.disconnect.assert_awaited_once()


@pytest.mark.unit
def test_ble_client_timeout_covers_lock_wait_and_operation() -> None:
    """timeout is one budget: time spent waiting for the lock comes out of the operation's wait."""
    client = BLEClient()

    async def hung_op() -> None:
        await asyncio.sleep(60)  # never completes within the test

    def hold_lock() -> None:
        with client._gatt_lock:
            time.sleep(0.4)

    try:
        holder = threading.Thread(target=hold_lock, daemon=True)
        holder.start()
        time.sleep(0.05)  # let the holder take the lock
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            client.async_await(hung_op(), timeout=0.5)
        elapsed = time.monotonic() - start
        holder.join(timeout=5)
    finally:
        client.close()
    assert elapsed < 0.8, f"lock wait and operation each got the full timeout ({elapsed:.2f}s)"


@pytest.mark.unit
def test_ble_close_reaches_disconnect_while_an_operation_hangs() -> None:
    """With another GATT operation stuck holding the lock, close() must still get to the transport
    disconnect: the disconnect message write gives up after CLOSE_WRITE_TIMEOUT instead of waiting."""
    iface = object.__new__(BLEInterface)
    iface._closing = False
    iface._want_receive = False
    iface._receiveThread = None
    iface._exit_handler = None
    client = BLEClient()
    client.bleak_client = MagicMock()
    client.bleak_client.write_gatt_char = AsyncMock()
    client.bleak_client.disconnect = AsyncMock()
    iface.client = client
    iface.heartbeatTimer = None
    done = threading.Event()
    sent = []

    def send_disconnect(self) -> None:
        sent.append(True)
        self._sendToRadioImpl(MagicMock(SerializeToString=lambda: b"\x01"))

    def close() -> None:
        iface.close()
        done.set()

    try:
        with patch("meshtastic.ble_interface.CLOSE_WRITE_TIMEOUT", 0.2), \
             patch.object(iface, "_disconnected"), \
             patch.object(client, "close"), \
             patch("meshtastic.mesh_interface.MeshInterface._sendDisconnect", send_disconnect):
            with client._gatt_lock:  # an operation in flight that never completes
                threading.Thread(target=close, daemon=True).start()
                assert done.wait(timeout=5), "close() waited for the in-flight operation"
    finally:
        BLEClient.close(client)
    assert sent, "the disconnect message was never attempted"
    client.bleak_client.disconnect.assert_awaited_once()
    client.bleak_client.write_gatt_char.assert_not_awaited()
    assert iface.client is None
