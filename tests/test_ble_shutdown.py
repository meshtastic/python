import sys
import pytest
import atexit
from unittest.mock import MagicMock, patch

# Mock the bleak library before it's imported by other modules.
sys.modules['bleak'] = MagicMock()
sys.modules['bleak.exc'] = MagicMock()

# Define a mock BleakError class that inherits from Exception for type checking
class MockBleakError(Exception):
    pass

sys.modules['bleak.exc'].BleakError = MockBleakError

# Now we can import the code to be tested
from meshtastic.ble_interface import BLEInterface, BLEClient, DISCONNECT_TIMEOUT_SECONDS
from bleak.exc import BleakError

@pytest.fixture
def iface(monkeypatch):
    """A fixture that returns a mocked BLEInterface for shutdown testing."""
    # Mock the real connection process in __init__
    monkeypatch.setattr(BLEInterface, "connect", MagicMock())

    # Mock methods from MeshInterface that are called during __init__
    monkeypatch.setattr(BLEInterface, "_startConfig", MagicMock())
    monkeypatch.setattr(BLEInterface, "_waitConnected", MagicMock())
    monkeypatch.setattr(BLEInterface, "waitForConfig", MagicMock())

    # Mock atexit.register to avoid polluting the global atexit registry
    mock_atexit_register = MagicMock()
    monkeypatch.setattr(atexit, "register", mock_atexit_register)

    # Instantiate the interface
    interface = BLEInterface(address="some-address", noProto=True)

    # Provide a mock client and attach the mock register for inspection
    interface.client = MagicMock(spec=BLEClient)
    interface.mock_atexit_register = mock_atexit_register

    return interface

def test_close_is_idempotent(iface):
    """Test that calling close() multiple times only triggers disconnect once."""
    mock_client = iface.client  # Capture client before it's set to None

    iface.close()
    iface.close()
    iface.close()

    # Assert that disconnect was called exactly once
    mock_client.disconnect.assert_called_once_with(timeout=DISCONNECT_TIMEOUT_SECONDS)
    mock_client.close.assert_called_once()

def test_close_unregisters_atexit_handler(iface, monkeypatch):
    """Test that close() unregisters the correct atexit handler."""
    # Mock atexit.unregister to spy on its calls
    mock_unregister = MagicMock()
    monkeypatch.setattr(atexit, "unregister", mock_unregister)

    # Capture the handler that was registered
    exit_handler = iface._exit_handler

    iface.close()

    # Assert that unregister was called with the handler from registration
    mock_unregister.assert_called_once_with(exit_handler)

def test_close_handles_bleakerror_gracefully(iface):
    """Test that a BleakError during disconnect is caught and handled."""
    mock_client = iface.client  # Capture client
    mock_client.disconnect.side_effect = BleakError("A test BleakError occurred")

    try:
        iface.close()
    except BleakError:
        pytest.fail("BleakError should have been handled within the close method.")

    # The client should still be closed in the `finally` block
    mock_client.close.assert_called_once()

def test_close_handles_timeouterror_gracefully(iface):
    """Test that a TimeoutError during disconnect is caught and handled."""
    mock_client = iface.client  # Capture client
    mock_client.disconnect.side_effect = TimeoutError("A test TimeoutError occurred")

    try:
        iface.close()
    except TimeoutError:
        pytest.fail("TimeoutError should have been handled within the close method.")

    # The client should still be closed in the `finally` block
    mock_client.close.assert_called_once()