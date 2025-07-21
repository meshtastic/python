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


# magic number used in streaming client headers
HEADER_MAGIC: bytes = b"\x94\xc3"


class ConnectionError(Exception):
    """Base class for MeshConnection-related errors."""


class BadPayloadError(ConnectionError):
    def __init__(self, payload, reason: str):
        self.payload = payload
        super().__init__(reason)


class MeshConnection(ABC):
    """A client API connection to a meshtastic radio."""

    def __init__(self, name: str):
        self.name: str = name
        self.on_disconnect: asyncio.Event = asyncio.Event()
        self._is_ready: bool = False
        self._send_lock: asyncio.Lock = asyncio.Lock()
        self._recv_lock: asyncio.Lock = asyncio.Lock()
        self._init_task: asyncio.Task = asyncio.create_task(self._initialize())
        self._init_task.add_done_callback(self._after_initialize)

    @abstractmethod
    async def _initialize(self):
        """Perform any connection initialization that must be performed async
        (and therefore not from the constructor)."""

    @abstractmethod
    async def _send_bytes(self, msg: buffer):
        """Send bytes to the mesh device."""
        pass

    @abstractmethod
    async def _recv_bytes(self) -> buffer:
        """Recieve bytes from the mesh device."""
        pass

    @staticmethod
    @abstractmethod
    async def get_available() -> AsyncGenerator[Any]:
        """Enumerate any mesh devices that can be connected to.

        Generates values that can be passed to the concrete connection class's
        constructor."""
        pass

    def ready(self):
        return self._is_ready

    def _after_initialize(self):
        self._is_ready = True
        del self._init_task

    async def send(self, message: ToRadio):
        """Send something to the connected device."""
        async with self._send_lock:
            msg_str: str = message.SerializeToString()
            await self._send_bytes(bytes(msg_str))

    async def recv(self) -> FromRadio:
        """Recieve something from the connected device."""
        async with self._recv_lock:
            msg_bytes: buffer = await self._recv_bytes()
            return FromRadio.FromString(str(msg_bytes, errors="ignore"))

    async def listen(self) -> AsyncGenerator[FromRadio]:
        while not self.on_disconnect.is_set():
            yield await self.recv()

    def close(self):
        """Close the connection.
        Overloaders should remember to call supermethod"""
        if not self.ready():
            self._init_task.cancel()

        self.on_disconnect.set()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.close()


class StreamConnection(MeshConnection):
    """Base class for connections using the aio stream API"""
    def __init__(self, name: str):
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self.stream_debug_out: io.StringIO = io.StringIO()
        super().__init__(name)

    def _handle_debug(self, debug_out: bytes):
        self.stream_debug_out.write(str(debug_out))
        self.stream_debug_out.flush()

    async def _send_bytes(self, msg: buffer):
        length: int = len(msg)
        if length > 512:
            raise BadPayloadError(msg, "Cannot send client API messages over 512 bytes")

        self._writer.write(HEADER_MAGIC)
        self._writer.write(length.to_bytes(2, "big"))
        self._writer.write(msg)
        await self._writer.drain()

    async def _find_stream_header(self):
        """Consumes and logs debug out bytes until a valid header is detected"""
        try:
            while True:
                from_stream: bytes = await self._reader.readuntil((b'\n', HEADER_MAGIC))
                if from_stream.endswith(HEADER_MAGIC):
                    self._handle_debug(from_stream[:-2])
                    return
                else:
                    self._handle_debug(from_stream)

        except asyncio.IncompleteReadError as err:
            if len(err.partial) > 0:
                self._handle_debug(err.partial)
            raise

    async def _recv_bytes(self) -> buffer:
        try:
            while True:
                await self._find_stream_header()
                size_bytes: bytes = await self._reader.readexactly(2)
                size: int = int.from_bytes(size_bytes, "big")
                if 0 < size <= 512:
                    return await self._reader.readexactly(size)

                self._handle_debug(size_bytes)

        except asyncio.LimitOverrunError as err:
            raise ConnectionError(
                "Read buffer overrun while reading stream") from err

        except asyncio.IncompleteReadError:
            logging.error(f"Connection to {self.name} terminated: stream EOF reached")
            self.close()

    def close(self):
        super().close()
        self._writer.close()
        self.stream_debug_out.close()
        asyncio.as_completed((self._writer.wait_closed(),))


class SerialConnection(StreamConnection):
    def __init__(self, portaddr: str, baudrate: int=115200):
        self.port: str = portaddr
        self.baudrate: int = baudrate
        super().__init__(portaddr)

    async def _initialize(self):
        self._reader, self._writer = await serial_asyncio.open_serial_connectio(
            port=self._port, baudrate=self._baudrate,
        )

    @staticmethod
    async def get_available() -> AsyncGenerator[str]:
        for port in serial.tools.list_ports.comports():
            if port.hwid != "n/a":
                yield port.device
