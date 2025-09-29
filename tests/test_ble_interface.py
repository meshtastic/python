"""Tests for the BLE interface module."""
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def mock_serial(monkeypatch):
    """Mock the serial module and its submodules."""
    serial_module = types.ModuleType("serial")

    # Create tools submodule
    tools_module = types.ModuleType("serial.tools")
    list_ports_module = types.ModuleType("serial.tools.list_ports")
    list_ports_module.comports = lambda *_args, **_kwargs: []
    tools_module.list_ports = list_ports_module
    serial_module.tools = tools_module

    # Add exception classes
    serial_module.SerialException = Exception
    serial_module.SerialTimeoutException = Exception

    # Mock the modules
    monkeypatch.setitem(sys.modules, "serial", serial_module)
    monkeypatch.setitem(sys.modules, "serial.tools", tools_module)
    monkeypatch.setitem(sys.modules, "serial.tools.list_ports", list_ports_module)

    return serial_module


@pytest.fixture(autouse=True)
def mock_pubsub(monkeypatch):
    """Mock the pubsub module."""
    pubsub_module = types.ModuleType("pubsub")
    pubsub_module.pub = SimpleNamespace(
        subscribe=lambda *_args, **_kwargs: None,
        sendMessage=lambda *_args, **_kwargs: None,
        AUTO_TOPIC=None,
    )

    monkeypatch.setitem(sys.modules, "pubsub", pubsub_module)
    return pubsub_module


@pytest.fixture(autouse=True)
def mock_tabulate(monkeypatch):
    """Mock the tabulate module."""
    tabulate_module = types.ModuleType("tabulate")
    tabulate_module.tabulate = lambda *_args, **_kwargs: ""

    monkeypatch.setitem(sys.modules, "tabulate", tabulate_module)
    return tabulate_module


@pytest.fixture(autouse=True)
def mock_bleak(monkeypatch):
    """Mock the bleak module."""
    bleak_module = types.ModuleType("bleak")

    class _StubBleakClient:
        def __init__(self, address=None, **_kwargs):
            self.address = address
            self.services = SimpleNamespace(get_characteristic=lambda _specifier: None)

        async def connect(self, **_kwargs):
            """Mock connect method."""
            return None

        async def disconnect(self, **_kwargs):
            """Mock disconnect method."""
            return None

        async def discover(self, **_kwargs):
            """Mock discover method."""
            return None

        async def start_notify(self, **_kwargs):
            """Mock start_notify method."""
            return None

        async def read_gatt_char(self, *_args, **_kwargs):
            """Mock read_gatt_char method."""
            return b""

        async def write_gatt_char(self, *_args, **_kwargs):
            """Mock write_gatt_char method."""
            return None

        def is_connected(self):
            """Mock is_connected method."""
            return False

    async def _stub_discover(**_kwargs):
        return {}

    class _StubBLEDevice:
        def __init__(self, address=None, name=None):
            self.address = address
            self.name = name

    bleak_module.BleakClient = _StubBleakClient
    bleak_module.BleakScanner = SimpleNamespace(discover=_stub_discover)
    bleak_module.BLEDevice = _StubBLEDevice

    monkeypatch.setitem(sys.modules, "bleak", bleak_module)
    return bleak_module


@pytest.fixture(autouse=True)
def mock_bleak_exc(monkeypatch, mock_bleak):
    """Mock the bleak.exc module."""
    bleak_exc_module = types.ModuleType("bleak.exc")

    class _StubBleakError(Exception):
        pass

    class _StubBleakDBusError(_StubBleakError):
        pass

    bleak_exc_module.BleakError = _StubBleakError
    bleak_exc_module.BleakDBusError = _StubBleakDBusError

    # Attach to parent module
    mock_bleak.exc = bleak_exc_module

    monkeypatch.setitem(sys.modules, "bleak.exc", bleak_exc_module)
    return bleak_exc_module


# Import will be done locally in test functions to avoid import-time dependencies


class DummyClient:
    """Dummy client for testing BLE interface functionality."""

    def __init__(self, disconnect_exception: Optional[Exception] = None) -> None:
        """Initialize dummy client with optional disconnect exception."""
        self.disconnect_calls = 0
        self.close_calls = 0
        self.address = "dummy"
        self.disconnect_exception = disconnect_exception
        self.services = SimpleNamespace(get_characteristic=lambda _specifier: None)

    def has_characteristic(self, _specifier):
        """Mock has_characteristic method."""
        return False

    def start_notify(self, *_args, **_kwargs):
        """Mock start_notify method."""
        return None

    def disconnect(self, *_args, **_kwargs):
        """Mock disconnect method that tracks calls and can raise exceptions."""
        self.disconnect_calls += 1
        if self.disconnect_exception:
            raise self.disconnect_exception

    def close(self):
        """Mock close method that tracks calls."""
        self.close_calls += 1


@pytest.fixture(autouse=True)
def stub_atexit(
    monkeypatch,
    mock_serial,
    mock_pubsub,
    mock_tabulate,
    mock_bleak,
    mock_bleak_exc,
):
    """Stub atexit to prevent actual registration during tests."""
    registered = []
    # Consume fixture arguments to document ordering intent and silence Ruff (ARG001).
    _ = (mock_serial, mock_pubsub, mock_tabulate, mock_bleak, mock_bleak_exc)

    def fake_register(func):
        registered.append(func)
        return func

    def fake_unregister(func):
        registered[:] = [f for f in registered if f is not func]

    import meshtastic.ble_interface as ble_mod

    monkeypatch.setattr(ble_mod.atexit, "register", fake_register, raising=True)
    monkeypatch.setattr(ble_mod.atexit, "unregister", fake_unregister, raising=True)
    yield
    # run any registered functions manually to avoid surprising global state
    for func in registered:
        func()


def _build_interface(monkeypatch, client):
    from meshtastic.ble_interface import BLEInterface

    def _stub_connect(_self, _address=None):
        return client

    def _stub_start_config(_self):
        return None

    monkeypatch.setattr(BLEInterface, "connect", _stub_connect)
    monkeypatch.setattr(BLEInterface, "_startConfig", _stub_start_config)
    iface = BLEInterface(address="dummy", noProto=True)
    return iface


def test_close_idempotent(monkeypatch):
    """Test that close() is idempotent and only calls disconnect once."""
    client = DummyClient()
    iface = _build_interface(monkeypatch, client)

    iface.close()
    iface.close()

    assert client.disconnect_calls == 1
    assert client.close_calls == 1


def test_close_handles_bleak_error(monkeypatch):
    """Test that close() handles BleakError gracefully."""
    from meshtastic.ble_interface import BleakError
    from meshtastic.mesh_interface import pub
    calls = []
    def _capture(topic, **kwargs):
        calls.append((topic, kwargs))
    monkeypatch.setattr(pub, "sendMessage", _capture)

    client = DummyClient(disconnect_exception=BleakError("Not connected"))
    iface = _build_interface(monkeypatch, client)

    iface.close()

    assert client.disconnect_calls == 1
    assert client.close_calls == 1
    # exactly one disconnect status
    assert (
        sum(
            1
            for topic, kw in calls
            if topic == "meshtastic.connection.status" and kw.get("connected") is False
        )
        == 1
    )


def test_close_handles_runtime_error(monkeypatch):
    """Test that close() handles RuntimeError gracefully."""
    from meshtastic.mesh_interface import pub
    calls = []
    def _capture(topic, **kwargs):
        calls.append((topic, kwargs))
    monkeypatch.setattr(pub, "sendMessage", _capture)

    client = DummyClient(disconnect_exception=RuntimeError("Threading issue"))
    iface = _build_interface(monkeypatch, client)

    iface.close()

    assert client.disconnect_calls == 1
    assert client.close_calls == 1
    # exactly one disconnect status
    assert (
        sum(
            1
            for topic, kw in calls
            if topic == "meshtastic.connection.status" and kw.get("connected") is False
        )
        == 1
    )


def test_close_handles_os_error(monkeypatch):
    """Test that close() handles OSError gracefully."""
    from meshtastic.mesh_interface import pub
    calls = []
    def _capture(topic, **kwargs):
        calls.append((topic, kwargs))
    monkeypatch.setattr(pub, "sendMessage", _capture)

    client = DummyClient(disconnect_exception=OSError("Permission denied"))
    iface = _build_interface(monkeypatch, client)

    iface.close()

    assert client.disconnect_calls == 1
    assert client.close_calls == 1
    # exactly one disconnect status
    assert (
        sum(
            1
            for topic, kw in calls
            if topic == "meshtastic.connection.status" and kw.get("connected") is False
        )
        == 1
    )


def test_receive_thread_specific_exceptions(monkeypatch, caplog):
    """Test that receive thread handles specific exceptions correctly."""
    import google.protobuf.message
    import logging
    import threading
    import time
    from meshtastic.ble_interface import BLEInterface
    
    # Set logging level to DEBUG to capture debug messages
    caplog.set_level(logging.DEBUG)
    
    # The exceptions that should be caught and handled
    handled_exceptions = [
        RuntimeError,
        OSError,
        google.protobuf.message.DecodeError,
    ]
    
    for exc_type in handled_exceptions:
        # Clear caplog for each test
        caplog.clear()
        
        # Create a mock client that raises the specific exception
        class ExceptionClient(DummyClient):
            def __init__(self, exception_type):
                super().__init__()
                self.exception_type = exception_type
                
            def read_gatt_char(self, *_args, **_kwargs):
                raise self.exception_type("Test exception")
        
        client = ExceptionClient(exc_type)
        iface = _build_interface(monkeypatch, client)
        
        # Mock the close method to track if it's called
        original_close = iface.close
        close_called = threading.Event()
        
        def mock_close():
            close_called.set()
            return original_close()
        
        monkeypatch.setattr(iface, "close", mock_close)
        
        # Start the receive thread
        iface._want_receive = True
        
        # Set up the client
        with iface._client_lock:
            iface.client = client
        
        # Trigger the receive loop
        iface._read_trigger.set()
        
        # Wait for the exception to be handled and close to be called
        # Use a reasonable timeout to avoid hanging the test
        close_called.wait(timeout=5.0)
        
        # Check that appropriate logging occurred
        assert "Fatal error in BLE receive thread" in caplog.text
        assert close_called.is_set(), f"Expected close() to be called for {exc_type.__name__}"
        
        # Clean up
        iface._want_receive = False
        try:
            iface.close()
        except Exception:
            pass  # Interface might already be closed


def test_send_to_radio_specific_exceptions(monkeypatch, caplog):
    """Test that sendToRadio handles specific exceptions correctly."""
    import logging
    from meshtastic.ble_interface import BLEInterface, BleakError
    
    # Set logging level to DEBUG to capture debug messages
    caplog.set_level(logging.DEBUG)
    
    class ExceptionClient(DummyClient):
        def __init__(self, exception_type):
            super().__init__()
            self.exception_type = exception_type
            
        def write_gatt_char(self, *_args, **_kwargs):
            raise self.exception_type("Test write exception")
    
    # Test BleakError specifically
    client = ExceptionClient(BleakError)
    iface = _build_interface(monkeypatch, client)
    
    # Create a mock ToRadio message with actual data to ensure it's not empty
    from meshtastic.protobuf import mesh_pb2
    to_radio = mesh_pb2.ToRadio()
    to_radio.packet.decoded.payload = b"test_data"
    
    # This should raise BLEInterface.BLEError
    with pytest.raises(BLEInterface.BLEError) as exc_info:
        iface._sendToRadioImpl(to_radio)
    
    assert "Error writing BLE" in str(exc_info.value)
    assert "BLE-specific error during write operation" in caplog.text
    
    # Clear caplog for next test
    caplog.clear()
    iface.close()
    
    # Test RuntimeError
    client2 = ExceptionClient(RuntimeError)
    iface2 = _build_interface(monkeypatch, client2)
    
    with pytest.raises(BLEInterface.BLEError) as exc_info:
        iface2._sendToRadioImpl(to_radio)
    
    assert "Error writing BLE" in str(exc_info.value)
    assert "Runtime error during write operation" in caplog.text
    
    # Clear caplog for next test
    caplog.clear()
    iface2.close()
    
    # Test OSError
    client3 = ExceptionClient(OSError)
    iface3 = _build_interface(monkeypatch, client3)
    
    with pytest.raises(BLEInterface.BLEError) as exc_info:
        iface3._sendToRadioImpl(to_radio)
    
    assert "Error writing BLE" in str(exc_info.value)
    assert "OS error during write operation" in caplog.text
    
    iface3.close()


def test_ble_client_is_connected_exception_handling(monkeypatch, caplog):
    """Test that BLEClient.is_connected handles exceptions gracefully."""
    import logging
    from meshtastic.ble_interface import BLEClient
    
    # Set logging level to DEBUG to capture debug messages
    caplog.set_level(logging.DEBUG)
    
    class ExceptionBleakClient:
        def __init__(self, exception_type):
            self.exception_type = exception_type
            
        def is_connected(self):
            raise self.exception_type("Connection check failed")
    
    # Create BLEClient with a mock bleak client that raises exceptions
    ble_client = BLEClient.__new__(BLEClient)
    ble_client.bleak_client = ExceptionBleakClient(AttributeError)
    
    # Should return False and log debug message when AttributeError occurs
    result = ble_client.is_connected()
    assert result is False
    assert "Unable to read bleak connection state" in caplog.text
    
    # Clear caplog
    caplog.clear()
    
    # Test TypeError
    ble_client.bleak_client = ExceptionBleakClient(TypeError)
    result = ble_client.is_connected()
    assert result is False
    assert "Unable to read bleak connection state" in caplog.text
    
    # Clear caplog
    caplog.clear()
    
    # Test RuntimeError
    ble_client.bleak_client = ExceptionBleakClient(RuntimeError)
    result = ble_client.is_connected()
    assert result is False
    assert "Unable to read bleak connection state" in caplog.text


def test_wait_for_disconnect_notifications_exceptions(monkeypatch, caplog):
    """Test that _wait_for_disconnect_notifications handles exceptions gracefully."""
    import logging
    from meshtastic.ble_interface import BLEInterface
    
    # Set logging level to DEBUG to capture debug messages
    caplog.set_level(logging.DEBUG)
    
    # Also ensure the logger is configured to capture the actual module logger
    logger = logging.getLogger('meshtastic.ble_interface')
    logger.setLevel(logging.DEBUG)
    
    client = DummyClient()
    iface = _build_interface(monkeypatch, client)
    
    # Mock publishingThread to raise RuntimeError
    import meshtastic.ble_interface as ble_mod
    class MockPublishingThread:
        def queueWork(self, callback):
            raise RuntimeError("Threading error in queueWork")
    
    monkeypatch.setattr(ble_mod, "publishingThread", MockPublishingThread())
    
    # Should handle RuntimeError gracefully
    iface._wait_for_disconnect_notifications()
    assert "Runtime error during disconnect notification flush" in caplog.text
    
    # Clear caplog
    caplog.clear()
    
    # Mock publishingThread to raise ValueError
    class MockPublishingThread2:
        def queueWork(self, callback):
            raise ValueError("Invalid event state")
    
    monkeypatch.setattr(ble_mod, "publishingThread", MockPublishingThread2())
    
    # Should handle ValueError gracefully
    iface._wait_for_disconnect_notifications()
    assert "Value error during disconnect notification flush" in caplog.text
    
    iface.close()


def test_drain_publish_queue_exceptions(monkeypatch, caplog):
    """Test that _drain_publish_queue handles exceptions gracefully."""
    import logging
    from meshtastic.ble_interface import BLEInterface
    from queue import Queue, Empty
    import threading
    
    # Set logging level to DEBUG to capture debug messages
    caplog.set_level(logging.DEBUG)
    
    client = DummyClient()
    iface = _build_interface(monkeypatch, client)
    
    # Create a mock queue with a runnable that raises exceptions
    class ExceptionRunnable:
        def __call__(self):
            raise ValueError("Callback execution failed")
    
    mock_queue = Queue()
    mock_queue.put(ExceptionRunnable())
    
    # Mock publishingThread with the queue
    import meshtastic.ble_interface as ble_mod
    class MockPublishingThread:
        def __init__(self):
            self.queue = mock_queue
        def queueWork(self, callback):
            pass  # Not used in this test but needed for teardown
    
    monkeypatch.setattr(ble_mod, "publishingThread", MockPublishingThread())
    
    # Should handle ValueError gracefully
    flush_event = threading.Event()
    iface._drain_publish_queue(flush_event)
    assert "Value error in deferred publish callback" in caplog.text
    
    iface.close()
