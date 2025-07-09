import asyncio
from abc import ABC, abstractmethod
from typing import *

from pubsub import pub

from meshtastic.protobuf.mesh_pb2 import FromRadio, ToRadio


class MeshConnection(ABC):
    """A client API connection to a meshtastic radio."""

    def __init__(self):
        self._on_disconnect: asyncio.Event = asyncio.Event()

    @abstractmethod
    async def _send_bytes(self, msg: buffer):
        """Send bytes to the mesh device."""
        pass

    @abstractmethod
    async def _recv_bytes(self) -> buffer:
        """Recieve bytes from the mesh device."""
        pass

    @abstractmethod
    def close(self):
        """Close the connection"""
        pass

    @staticmethod
    @abstractmethod
    async def get_available() -> AsyncGenerator[Any]:
        """Enumerate any mesh devices that can be connected to.

        Generates values that can be passed to the concrete connection class's
        constructor."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.close()

    async def send(self, message: ToRadio):
        """Send something to the connected device."""
        msg_str: str = message.SerializeToString()
        await self._send_bytes(bytes(msg_str))

    async def recv(self) -> FromRadio:
        """Recieve something from the connected device."""
        msg_bytes: buffer = await self._recv_bytes()
        return FromRadio.FromString(str(msg_bytes))

    async def listen(self) -> AsyncGenerator[FromRadio]:
        while True:
            yield await self.recv()
