"""Tests for the BLEInterface class."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from threading import Thread, Lock

# Import the class to be tested
from meshtastic.ble_interface import BLEInterface, MeshInterface
# Import the original classes for spec'ing, and the exception
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

@pytest.fixture
def mock_bleak_scanner(monkeypatch):
    """Fixture to mock BleakScanner."""
    scanner_class_mock = MagicMock(spec=BleakScanner)
    mock_device = MagicMock()
    mock_device.address = "some-mock-address"
    scanner_class_mock.find_device_by_address = AsyncMock(return_value=mock_device)
    monkeypatch.setattr('meshtastic.ble_interface.BleakScanner', scanner_class_mock)
    return scanner_class_mock

@pytest.fixture
def mock_bleak_client(monkeypatch):
    """Fixture to mock BleakClient."""
    client_instance_mock = AsyncMock(spec=BleakClient)
    client_instance_mock.is_connected = True
    client_instance_mock.address = "some-mock-address"
    client_instance_mock.start_notify = AsyncMock()

    async_context_manager_mock = AsyncMock()
    async_context_manager_mock.__aenter__.return_value = client_instance_mock

    def client_constructor(device, disconnected_callback, **kwargs):
        # Capture the callback so the test can invoke it
        client_instance_mock.captured_disconnected_callback = disconnected_callback
        return async_context_manager_mock

    client_class_mock = MagicMock(side_effect=client_constructor)
    monkeypatch.setattr('meshtastic.ble_interface.BleakClient', client_class_mock)
    return client_instance_mock

@pytest.fixture
def iface(monkeypatch):
    """
    A fixture that creates a BLEInterface instance but replaces its __init__
    with a mock version that only sets up the necessary attributes without
    any blocking or async logic.
    """
    # This mock __init__ does the bare minimum to create the object.
    # It avoids threading and the real asyncio event loop setup.
    def mock_init(self, address, noProto=True, **kwargs):
        self._closing_lock = Lock()
        self._closing = False
        self.address = address
        self.noProto = noProto
        self.auto_reconnect = True
        self.client = None
        self._connection_monitor_task = None
        self._event_loop = None # This will be set by the test
        self._disconnect_event = asyncio.Event()
        self._initial_connect_event = asyncio.Event()
        monkeypatch.setattr(MeshInterface, "__init__", MagicMock())

    monkeypatch.setattr(BLEInterface, "__init__", mock_init)
    iface_instance = BLEInterface(address="some-address")

    yield iface_instance

    # Cleanup after the test
    iface_instance._closing = True
    if iface_instance._connection_monitor_task:
        iface_instance._connection_monitor_task.cancel()

@pytest.mark.asyncio
async def test_connection_and_reconnect(iface, mock_bleak_scanner, monkeypatch):
    """Test the full connection, disconnect, and reconnect cycle."""
    # Manually set the event loop to the one provided by pytest-asyncio
    iface._event_loop = asyncio.get_running_loop()

    mock_sleep = AsyncMock()
    monkeypatch.setattr('meshtastic.ble_interface.asyncio.sleep', mock_sleep)

    # Manually start the monitor task in the test's event loop
    iface._connection_monitor_task = asyncio.create_task(iface._connection_monitor())

    # Yield control to allow the monitor to run the first connection
    await asyncio.sleep(0)

    # It should have connected
    mock_bleak_scanner.find_device_by_address.assert_called_once()
    assert iface._initial_connect_event.is_set()
    assert iface.client is not None

    # Trigger a disconnect
    iface._disconnect_event.set()
    await asyncio.sleep(0) # Yield to let the monitor process the disconnect

    # The monitor should call sleep(1) for backoff, then try to reconnect
    mock_sleep.assert_called_once_with(1)
    await asyncio.sleep(0) # Yield again to let the second connection attempt happen
    assert mock_bleak_scanner.find_device_by_address.call_count == 2

@pytest.mark.asyncio
async def test_no_reconnect_when_disabled(iface, mock_bleak_scanner, monkeypatch):
    """Test that reconnection does not happen when auto_reconnect is False."""
    # Manually set the event loop and disable reconnect
    iface._event_loop = asyncio.get_running_loop()
    iface.auto_reconnect = False

    mock_sleep = AsyncMock()
    monkeypatch.setattr('meshtastic.ble_interface.asyncio.sleep', mock_sleep)

    # Manually start the monitor task
    iface._connection_monitor_task = asyncio.create_task(iface._connection_monitor())

    # Yield control to allow the monitor to run the first connection
    await asyncio.sleep(0)
    mock_bleak_scanner.find_device_by_address.assert_called_once()
    assert iface._initial_connect_event.is_set()

    # Trigger a disconnect
    iface._disconnect_event.set()
    await asyncio.sleep(0)

    # Assert that sleep was never called and no reconnection attempt was made
    mock_sleep.assert_not_called()
    mock_bleak_scanner.find_device_by_address.assert_called_once()