import asyncio
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
            return None

        async def disconnect(self, **_kwargs):
            return None

        async def discover(self, **_kwargs):
            return None

        async def start_notify(self, **_kwargs):
            return None

        async def read_gatt_char(self, *_args, **_kwargs):
            return b""

        async def write_gatt_char(self, *_args, **_kwargs):
            return None

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
    def __init__(self, disconnect_exception: Optional[Exception] = None) -> None:
        self.disconnect_calls = 0
        self.close_calls = 0
        self.address = "dummy"
        self.disconnect_exception = disconnect_exception
        self.services = SimpleNamespace(get_characteristic=lambda _specifier: None)

    def has_characteristic(self, _specifier):
        return False

    def start_notify(self, *_args, **_kwargs):
        return None

    def disconnect(self, *_args, **_kwargs):
        self.disconnect_calls += 1
        if self.disconnect_exception:
            raise self.disconnect_exception

    def close(self):
        self.close_calls += 1


@pytest.fixture(autouse=True)
def stub_atexit(monkeypatch):
    registered = []

    def fake_register(func):
        registered.append(func)
        return func

    def fake_unregister(func):
        registered[:] = [f for f in registered if f is not func]

    monkeypatch.setattr("meshtastic.ble_interface.atexit.register", fake_register)
    monkeypatch.setattr("meshtastic.ble_interface.atexit.unregister", fake_unregister)
    yield
    # run any registered functions manually to avoid surprising global state
    for func in registered:
        func()


def _build_interface(monkeypatch, client):
    from meshtastic.ble_interface import BLEInterface
    
    monkeypatch.setattr(BLEInterface, "connect", lambda self, address=None: client)
    monkeypatch.setattr(BLEInterface, "_receiveFromRadioImpl", lambda self: None)
    monkeypatch.setattr(BLEInterface, "_startConfig", lambda self: None)
    iface = BLEInterface(address="dummy", noProto=True)
    return iface


def test_close_idempotent(monkeypatch):
    client = DummyClient()
    iface = _build_interface(monkeypatch, client)

    iface.close()
    iface.close()

    assert client.disconnect_calls == 1
    assert client.close_calls == 1


def test_close_handles_bleak_error(monkeypatch):
    from meshtastic.ble_interface import BleakError
    
    client = DummyClient(disconnect_exception=BleakError("Not connected"))
    iface = _build_interface(monkeypatch, client)

    iface.close()

    assert client.disconnect_calls == 1
    assert client.close_calls == 1
