# Copilot Instructions for Meshtastic Python

## Project Overview

This is the Meshtastic Python library and CLI - a Python API for interacting with Meshtastic mesh radio devices. It supports communication via Serial, TCP, and BLE interfaces.

## Technology Stack

- **Language**: Python 3.9 - 3.14
- **Package Manager**: Poetry
- **Testing**: pytest with hypothesis for property-based testing
- **Linting**: pylint
- **Type Checking**: mypy (working toward strict mode)
- **Documentation**: pdoc3
- **License**: GPL-3.0

## Project Structure

```
meshtastic/           # Main library package
├── __init__.py       # Core interface classes and pub/sub topics
├── __main__.py       # CLI entry point
├── mesh_interface.py # Base interface class for all connection types
├── serial_interface.py
├── tcp_interface.py
├── ble_interface.py
├── node.py           # Node representation and configuration
├── protobuf/         # Generated Protocol Buffer files (*_pb2.py, *_pb2.pyi)
├── tests/            # Unit and integration tests
├── powermon/         # Power monitoring tools
└── analysis/         # Data analysis tools
examples/             # Usage examples
protobufs/            # Protocol Buffer source definitions
```

## Coding Standards

### Style Guidelines

- Follow PEP 8 style conventions
- Use type hints for function parameters and return values
- Document public functions and classes with docstrings
- Prefer explicit imports over wildcard imports
- Use `logging` module instead of print statements for debug output

### Type Annotations

- Add type hints to all new code
- Use `Optional[T]` for nullable types
- Use `Dict`, `List`, `Tuple` from `typing` module for Python 3.9 compatibility
- Protobuf types are in `meshtastic.protobuf.*_pb2` modules

### Naming Conventions

- Classes: `PascalCase` (e.g., `MeshInterface`, `SerialInterface`)
- Functions/methods: `camelCase` for public API (e.g., `sendText`, `sendData`)
- Internal functions: `snake_case` with leading underscore (e.g., `_send_packet`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `BROADCAST_ADDR`, `LOCAL_ADDR`)

### Error Handling

- Use custom exception classes when appropriate (e.g., `MeshInterface.MeshInterfaceError`)
- Provide meaningful error messages
- Use `our_exit()` from `meshtastic.util` for CLI exits with error codes

## Testing

### Test Organization

Tests are in `meshtastic/tests/` and use pytest markers:

- `@pytest.mark.unit` - Fast unit tests (default)
- `@pytest.mark.unitslow` - Slower unit tests
- `@pytest.mark.int` - Integration tests
- `@pytest.mark.smoke1` - Single device smoke tests
- `@pytest.mark.smoke2` - Two device smoke tests
- `@pytest.mark.smokevirt` - Virtual device smoke tests
- `@pytest.mark.examples` - Example validation tests

### Running Tests

```bash
# Run unit tests only (default)
make test
# or
pytest -m unit

# Run all tests
pytest

# Run with coverage
make cov
```

### Writing Tests

- Use `pytest` fixtures from `conftest.py`
- Use `hypothesis` for property-based testing where appropriate
- Mock external dependencies (serial ports, network connections)
- Test file naming: `test_<module_name>.py`

## Pub/Sub Events

The library uses pypubsub for event handling. Key topics:

- `meshtastic.connection.established` - Connection successful
- `meshtastic.connection.lost` - Connection lost
- `meshtastic.receive.text(packet)` - Text message received
- `meshtastic.receive.position(packet)` - Position update received
- `meshtastic.receive.data.portnum(packet)` - Data packet by port number
- `meshtastic.node.updated(node)` - Node database changed
- `meshtastic.log.line(line)` - Raw log line from device

## Protocol Buffers

- Protobuf definitions are in `protobufs/meshtastic/`
- Generated Python files are in `meshtastic/protobuf/`
- Never edit `*_pb2.py` or `*_pb2.pyi` files directly
- Regenerate with: `make protobufs` or `./bin/regen-protobufs.sh`

## Common Patterns

### Creating an Interface

```python
import meshtastic.serial_interface

# Auto-detect device
iface = meshtastic.serial_interface.SerialInterface()

# Specific device
iface = meshtastic.serial_interface.SerialInterface(devPath="/dev/ttyUSB0")

# Always close when done
iface.close()

# Or use context manager
with meshtastic.serial_interface.SerialInterface() as iface:
    iface.sendText("Hello mesh")
```

### Sending Messages

```python
# Text message (broadcast)
iface.sendText("Hello")

# Text message to specific node
iface.sendText("Hello", destinationId="!abcd1234")

# Binary data
iface.sendData(data, portNum=portnums_pb2.PRIVATE_APP)
```

### Subscribing to Events

```python
from pubsub import pub

def on_receive(packet, interface):
    print(f"Received: {packet}")

pub.subscribe(on_receive, "meshtastic.receive")
```

## Development Workflow

1. Install dependencies: `poetry install --all-extras --with dev`
2. Make changes
3. Run linting: `poetry run pylint meshtastic examples/`
4. Run type checking: `poetry run mypy meshtastic/`
5. Run tests: `poetry run pytest -m unit`
6. Update documentation if needed

## CLI Development

The CLI is in `meshtastic/__main__.py`. When adding new CLI commands:

- Use argparse for argument parsing
- Support `--dest` for specifying target node
- Provide `--help` documentation
- Handle errors gracefully with meaningful messages

## Dependencies

### Required
- `pyserial` - Serial port communication
- `protobuf` - Protocol Buffers
- `pypubsub` - Pub/sub messaging
- `bleak` - BLE communication
- `tabulate` - Table formatting
- `pyyaml` - YAML config support
- `requests` - HTTP requests

### Optional (extras)
- `cli` extra: `pyqrcode`, `print-color`, `dotmap`, `argcomplete`
- `tunnel` extra: `pytap2`
- `analysis` extra: `dash`, `pandas`

## Important Notes

- Always test with actual Meshtastic hardware when possible
- Be mindful of radio regulations in your region
- The nodedb (`interface.nodes`) is read-only
- Packet IDs are random 32-bit integers
- Default timeout is 300 seconds for operations
