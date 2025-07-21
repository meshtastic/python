"""
low-level radio connection API
"""
import asyncio
import io
import logging
from abc import ABC, abstractmethod
from typing import *

import serial
import serial_asyncio

from meshtastic.protobuf.mesh_pb2 import FromRadio, ToRadio


STREAM_HEADER_MAGIC: bytes = b"\x94\xc3"  # magic number used in streaming client headers
DEFAULT_BAUDRATE: int = 115200


class RadioConnectionError(Exception):
    """Base class for RadioConnection-related errors."""


class BadPayloadError(RadioConnectionError):
    """Error indicating invalid payload over connection"""
    def __init__(self, payload, reason: str):
        self.payload = payload
        super().__init__(reason)


class ConnectionTerminatedError(RadioConnectionError):
    """Error indicating the connection was terminated."""


class RadioConnection(ABC):
    """A client API connection to a meshtastic radio."""

    def __init__(self, name: str):
        self.name: str = name
        self.on_ready: asyncio.Event = asyncio.Event()
        self.on_disconnect: asyncio.Event = asyncio.Event()
        self._send_lock: asyncio.Lock = asyncio.Lock()
        self._recv_lock: asyncio.Lock = asyncio.Lock()
        self._listen_lock: asyncio.Lock = asyncio.Lock()

    @abstractmethod
    async def _initialize(self):
        """Perform any connection initialization that must be performed async
        (and therefore not from the constructor)."""

    @abstractmethod
    async def _send_bytes(self, msg: bytes):
        """Send bytes to the mesh device."""

    @abstractmethod
    async def _recv_bytes(self) -> bytes:
        """Recieve bytes from the mesh device."""

    @staticmethod
    @abstractmethod
    async def get_available() -> AsyncGenerator[Any]:
        """Enumerate any mesh devices that can be connected to.

        Generates values that can be passed to the concrete connection class's
        constructor."""

    def ready(self):
        """Returns if the connection is ready for tx/rx"""
        return self.on_ready.is_set()

    async def open(self):
        """Start the connection"""
        await self._initialize()
        self.on_ready.set()

    def _ensure_ready(self):
        """Raise an exception if the connection is not ready for tx/rx"""
        if not self.ready():
            raise RadioConnectionError("Connection used before it was ready")

    async def send(self, message: ToRadio):
        """Send something to the connected device."""
        self._ensure_ready()
        async with self._send_lock:
            msg_str: str = message.SerializeToString()
            await self._send_bytes(bytes(msg_str))

    async def recv(self) -> FromRadio:
        """Recieve something from the connected device."""
        self._ensure_ready()
        async with self._recv_lock:
            msg_bytes: bytes = await self._recv_bytes()
            return FromRadio.FromString(str(msg_bytes, errors="ignore"))

    async def listen(self) -> AsyncGenerator[FromRadio]:
        """Yields new messages from the radio so long as the connection is active."""
        self._ensure_ready()
        async with self._listen_lock:
            while not self.on_disconnect.is_set():
                yield await self.recv()

    async def close(self):
        """Close the connection.
        Overloaders should remember to call supermethod"""
        self.on_ready.unset()
        self.on_disconnect.set()

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, trace):
        await self.close()

    #def __enter__(self):
    #    self.open()
    #    asyncio.run(self._init_task)
    #    return self

    #def __exit__(self, exc_type, exc_value, trace):
    #    self.close()


class StreamConnection(RadioConnection):
    """Base class for connections using the aio stream API"""
    def __init__(self, name: str):
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self.stream_debug_out: io.StringIO = io.StringIO()
        super().__init__(name)

    def _handle_debug(self, debug_out: bytes):
        self.stream_debug_out.write(str(debug_out))
        self.stream_debug_out.flush()

    async def _send_bytes(self, msg: bytes):
        length: int = len(msg)
        if length > 512:
            raise BadPayloadError(msg, "Cannot send client API messages over 512 bytes")

        self._writer.write(STREAM_HEADER_MAGIC)
        self._writer.write(length.to_bytes(2, "big"))
        self._writer.write(msg)
        await self._writer.drain()

    async def _find_stream_header(self):
        """Consumes and logs debug out bytes until a valid header is detected"""
        try:
            while True:
                from_stream: bytes = await self._reader.readuntil((b'\n', STREAM_HEADER_MAGIC))
                if from_stream.endswith(STREAM_HEADER_MAGIC):
                    self._handle_debug(from_stream[:-2])
                    return
                else:
                    self._handle_debug(from_stream)

        except asyncio.IncompleteReadError as err:
            if len(err.partial) > 0:
                self._handle_debug(err.partial)
            raise

    async def _recv_bytes(self) -> bytes:
        try:
            while True:
                await self._find_stream_header()
                size_bytes: bytes = await self._reader.readexactly(2)
                size: int = int.from_bytes(size_bytes, "big")
                if 0 < size <= 512:
                    return await self._reader.readexactly(size)

                self._handle_debug(size_bytes)

        except asyncio.LimitOverrunError as err:
            raise RadioConnectionError("Read buffer overrun while reading stream") from err

        except asyncio.IncompleteReadError:
            self._reader.feed_eof()
            logging.error(f"Connection to {self.name} terminated: stream EOF reached")
            raise ConnectionTerminatedError from None

    async def close(self):
        await super().close()
        if self._writer.can_write_eof():
            self._writer.write_eof()

        self._writer.close()
        self.stream_debug_out.close()
        await self._writer.wait_closed()


class SerialConnection(StreamConnection):
    """Connection to a mesh radio over serial port"""
    def __init__(self, portaddr: str, baudrate: int=DEFAULT_BAUDRATE):
        self.port: str = portaddr
        self.baudrate: int = baudrate
        super().__init__(portaddr)

    async def _initialize(self):
        self._reader, self._writer = await serial_asyncio.open_serial_connection(
            port=self._port, baudrate=self._baudrate)

    @staticmethod
    async def get_available() -> AsyncGenerator[str]:
        for port in serial.tools.list_ports.comports():
            # filtering for hwid gets rid of linux VT serials (e.g, /dev/ttyS0 and friends)
            # FIXME: this may not be cross-platform or non-USB serial friendly
            if port.hwid != "n/a":
                yield port.device
