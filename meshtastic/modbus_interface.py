"""Modbus interface class, for meshtastic devices reached through the Modbus-RTU API tunnel on an RS485 bus

A node with its serial module in MODBUS mode can answer as a Modbus slave (address 240 by default)
and carry the normal client API byte stream in two user-defined function codes:

    write: addr, 0x41, seq, len, data[len], crc  ->  addr, 0x41, seq, accepted, crc
    read:  addr, 0x42, seq, crc                  ->  addr, 0x42, seq, len, data[len], crc

A request repeated with the same seq and function code is a retry: the node resends its previous
answer and does not apply the data twice.
"""
# pylint: disable=R0917
import logging
import os
import threading
import time
from typing import Optional, Tuple

import serial  # type: ignore[import-untyped]

from meshtastic.mesh_interface import MeshInterface
from meshtastic.stream_interface import StreamInterface

DEFAULT_MODBUS_ADDRESS = 240
DEFAULT_MODBUS_BAUDRATE = 9600

FC_WRITE = 0x41
FC_READ = 0x42
MAX_DATA = 240
RETRIES = 3
RETRY_SPACING = 0.2  # seconds between the start of two attempts
POLL_INTERVAL = 0.1  # seconds between reads while the node has nothing to send

logger = logging.getLogger(__name__)


def crc16(data: bytes) -> int:
    """CRC-16/Modbus (poly 0xA001 reflected, init 0xFFFF)"""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def withCrc(frame: bytes) -> bytes:
    """Append the Modbus CRC, low byte first"""
    crc = crc16(frame)
    return bytes(frame) + bytes((crc & 0xFF, crc >> 8))


def parseModbusSpec(spec: str) -> Tuple[str, int, int]:
    """Split a DEVICE[:ADDR[:BAUD]] connection spec"""
    parts = spec.split(":")
    if len(parts) > 3 or not parts[0]:
        raise ValueError(f"Invalid Modbus connection '{spec}', expected DEVICE[:ADDR[:BAUD]]")
    address = int(parts[1]) if len(parts) > 1 and parts[1] else DEFAULT_MODBUS_ADDRESS
    baudrate = int(parts[2]) if len(parts) > 2 and parts[2] else DEFAULT_MODBUS_BAUDRATE
    if not 1 <= address <= 247:
        raise ValueError(f"Invalid Modbus address {address}, expected 1..247")
    return parts[0], address, baudrate


class ModbusInterface(StreamInterface):
    """Interface class for meshtastic devices over the Modbus-RTU API tunnel"""

    def __init__(
        self,
        devPath: str,
        address: int = DEFAULT_MODBUS_ADDRESS,
        baudrate: int = DEFAULT_MODBUS_BAUDRATE,
        debugOut=None,
        noProto: bool = False,
        connectNow: bool = True,
        noNodes: bool = False,
        timeout: int = 300,
    ) -> None:
        """Constructor, opens the RS485 adapter and connects to the node's API tunnel

        Keyword Arguments:
            devPath {string} -- The USB-RS485 adapter, i.e. COM5 or /dev/ttyUSB0
            address {int} -- The node's tunnel slave address (default: 240)
            baudrate {int} -- The bus baud rate, 8N1 (default: 9600)
            timeout -- How long to wait for replies (default: 300 seconds)
        """
        self.devPath: str = devPath
        self.address: int = address
        self.baudrate: int = baudrate
        self._busLock = threading.Lock()
        self._pending = b""  # read from the node, not yet consumed by the reader thread
        self._nextPoll = 0.0
        self._seq = os.urandom(1)[0]  # a fresh start must not look like a retry to the node

        super().__init__(debugOut=debugOut, noProto=noProto, connectNow=connectNow, noNodes=noNodes, timeout=timeout)

    def __repr__(self):
        rep = f"ModbusInterface(devPath={self.devPath!r}"
        if self.address != DEFAULT_MODBUS_ADDRESS:
            rep += f", address={self.address!r}"
        if self.baudrate != DEFAULT_MODBUS_BAUDRATE:
            rep += f", baudrate={self.baudrate!r}"
        if self.debugOut is not None:
            rep += f", debugOut={self.debugOut!r}"
        if self.noProto:
            rep += ", noProto=True"
        if self.noNodes:
            rep += ", noNodes=True"
        rep += ")"
        return rep

    def connect(self) -> None:
        """Open the RS485 adapter and start the interface"""
        logger.debug(f"Connecting to Modbus address {self.address} on {self.devPath}")
        # A read must cover the node's service loop plus a full answer on the wire.
        replyTimeout = 0.15 + (6 + MAX_DATA) * 11 / self.baudrate
        self.stream = serial.Serial(self.devPath, self.baudrate, timeout=replyTimeout)
        super().connect()

    def _transact(self, fc: int, data: bytes = b"") -> bytes:
        """Send one tunnel request and return the payload of its answer, retrying on silence"""
        with self._busLock:
            if self.stream is None:
                raise MeshInterface.MeshInterfaceError("Modbus port is closed")
            self._seq = (self._seq + 1) & 0xFF
            req = bytes((self.address, fc, self._seq))
            if fc == FC_WRITE:
                req += bytes((len(data),)) + data
            req = withCrc(req)
            for _ in range(1 + RETRIES):
                started = time.monotonic()
                self.stream.reset_input_buffer()
                self.stream.write(req)
                self.stream.flush()
                answer = self._readAnswer(fc)
                if answer is not None:
                    return answer
                time.sleep(max(0.0, RETRY_SPACING - (time.monotonic() - started)))
            raise MeshInterface.MeshInterfaceError(f"No answer from Modbus address {self.address} on {self.devPath}")

    def _readAnswer(self, fc: int) -> Optional[bytes]:
        """Read the answer to the request just sent; None if it is missing or damaged"""
        assert self.stream is not None
        head = self.stream.read(5)  # every answer, the exception included, is at least 5 bytes
        if len(head) < 5 or head[0] != self.address:
            return None
        if head[1] == fc | 0x80:
            if crc16(head[:3]) == head[3] | head[4] << 8:
                raise MeshInterface.MeshInterfaceError(
                    f"Modbus address {self.address} rejected function 0x{fc:02x} (exception {head[2]})"
                )
            return None
        if head[1] != fc or head[2] != self._seq:
            return None
        rest = self.stream.read(1 + (head[3] if fc == FC_READ else 0))
        frame = head + rest
        if len(frame) != 6 + (head[3] if fc == FC_READ else 0) or crc16(frame[:-2]) != frame[-2] | frame[-1] << 8:
            return None
        return frame[4:-2] if fc == FC_READ else bytes((head[3],))

    def _writeBytes(self, b: bytes) -> None:
        """Send API bytes to the node in tunnel writes"""
        while b and self.stream is not None:
            accepted = self._transact(FC_WRITE, b[:MAX_DATA])[0]
            if not accepted:
                raise MeshInterface.MeshInterfaceError(f"Modbus address {self.address} accepted no data")
            b = b[accepted:]

    def _readBytes(self, length) -> Optional[bytes]:
        """Hand API bytes to the reader thread, polling the node with tunnel reads"""
        if self.stream is None:
            self._wantExit = True
            return None
        if not self._pending:
            wait = self._nextPoll - time.monotonic()
            if wait > 0:
                time.sleep(wait)
                return b""
            self._pending = self._transact(FC_READ)
            # A full read means more is waiting, so poll again straight away.
            self._nextPoll = time.monotonic() + (0 if len(self._pending) == MAX_DATA else POLL_INTERVAL)
        out, self._pending = self._pending[:length], self._pending[length:]
        return out
