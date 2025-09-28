"""Bluetooth interface for Meshtastic."""
import asyncio
import atexit
import contextlib
import logging
import struct
import time
import io
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from threading import Lock, Thread
from typing import List, Optional

import google.protobuf
from bleak import BleakClient, BleakScanner, BLEDevice
from bleak.exc import BleakDBusError, BleakError

from meshtastic.mesh_interface import MeshInterface
from .protobuf import mesh_pb2

SERVICE_UUID = "6ba1b218-15a8-461f-9fa8-5dcae273eafd"
TORADIO_UUID = "f75c76d2-129e-4dad-a1dd-7866124401e7"
FROMRADIO_UUID = "2c55e69e-4993-11ed-b878-0242ac120002"
FROMNUM_UUID = "ed9da18c-a800-4f66-a670-aa7547e34453"
LEGACY_LOGRADIO_UUID = "6c6fd238-78fa-436b-aacf-15c5be1ef2e2"
LOGRADIO_UUID = "5a3d6e49-06e6-4423-9944-e9de8cdf9547"
logger = logging.getLogger(__name__)

DISCONNECT_TIMEOUT_SECONDS = 5.0

class BLEInterface(MeshInterface):
    """MeshInterface using BLE to connect to devices."""

    class BLEError(Exception):
        """An exception class for BLE errors."""

    def __init__(
        self,
        address: Optional[str],
        noProto: bool = False,
        debugOut: Optional[io.TextIOWrapper] = None,
        noNodes: bool = False,
        auto_reconnect: bool = True,
    ) -> None:
        self._closing_lock = Lock()
        self._closing = False
        self.address = address
        self.auto_reconnect = auto_reconnect
        self._exit_handler = None

        self.client: Optional[BleakClient] = None
        self._connection_monitor_task: Optional[asyncio.Task] = None

        self._event_loop = asyncio.new_event_loop()
        self._disconnect_event = asyncio.Event()
        self._initial_connect_event = asyncio.Event()

        self._event_thread = Thread(target=self._run_event_loop, name="BLEEventLoop", daemon=True)
        self._event_thread.start()

        MeshInterface.__init__(self, debugOut=debugOut, noProto=noProto, noNodes=noNodes)

        self.should_read = False
        self._want_receive = True
        self._receiveThread = Thread(target=self._receiveFromRadioImpl, name="BLEReceive", daemon=True)
        self._receiveThread.start()

        self._connection_monitor_task = self.async_run(self._connection_monitor())

        logger.debug("Waiting for initial BLE connection...")
        try:
            self.async_await(self._initial_connect_event.wait(), timeout=30)
        except TimeoutError as e:
            self.close()
            raise BLEInterface.BLEError("Failed to connect to BLE device in time.") from e

        if not self.client or not self.client.is_connected:
            self.close()
            raise BLEInterface.BLEError("Failed to connect to BLE device.")

        logger.debug("Initial BLE connection established.")
        self._exit_handler = atexit.register(self.close)

    def _on_ble_disconnect(self, client: BleakClient) -> None:
        """Disconnected callback from Bleak."""
        logger.debug(f"BLE client {client.address} disconnected.")
        if not self._closing:
            self._disconnect_event.set()

    async def _connection_monitor(self):
        """A background task that manages the BLE connection and reconnection."""
        retry_delay = 1
        while not self._closing:
            try:
                logger.debug(f"Scanning for {self.address}...")
                device = await BleakScanner.find_device_by_address(self.address, timeout=20.0)
                if not device:
                    raise BLEInterface.BLEError(f"Device with address {self.address} not found.")

                self._disconnect_event.clear()
                async with BleakClient(device, disconnected_callback=self._on_ble_disconnect) as client:
                    logger.info(f"Successfully connected to device {client.address}.")
                    self.client = client

                    await client.start_notify(FROMNUM_UUID, self.from_num_handler)
                    if self.client.is_connected:
                         if not self.noProto:
                             self._startConfig()
                             self.waitForConfig()

                    if not self._initial_connect_event.is_set():
                        self._initial_connect_event.set()

                    retry_delay = 1
                    await self._disconnect_event.wait()

                self.client = None
                logger.info("Device disconnected.")

            except Exception as e:
                if not self._initial_connect_event.is_set():
                     self._initial_connect_event.set()
                if isinstance(e, asyncio.CancelledError):
                    logger.debug("Connection monitor cancelled.")
                    break
                logger.warning(f"Connection failed: {e}")

            if self._closing or not self.auto_reconnect:
                break

            logger.info(f"Will try to reconnect in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)

    def close(self) -> None:
        with self._closing_lock:
            if self._closing:
                return
            logger.debug("Closing BLE interface.")
            self._closing = True

        if self._disconnect_event:
            self._disconnect_event.set()

        if self._connection_monitor_task:
            self._connection_monitor_task.cancel()

        if self._exit_handler:
            with contextlib.suppress(ValueError):
                atexit.unregister(self._exit_handler)
            self._exit_handler = None

        if self._want_receive:
            self._want_receive = False
            if self._receiveThread and self._receiveThread.is_alive():
                self._receiveThread.join(timeout=2)

        if self._event_loop.is_running():
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
        if self._event_thread and self._event_thread.is_alive():
            self._event_thread.join()

        MeshInterface.close(self)
        self._disconnected()

    def _receiveFromRadioImpl(self) -> None:
        while self._want_receive:
            if self.should_read and self.client and self.client.is_connected:
                self.should_read = False
                try:
                    read_future = self.async_run(self.client.read_gatt_char(FROMRADIO_UUID))
                    b = read_future.result(timeout=2.0)
                    if b:
                        logger.debug(f"FROMRADIO read: {b.hex()}")
                        self._handleFromRadio(b)
                except Exception as e:
                    logger.debug(f"Could not read from radio: {e}")
            else:
                time.sleep(0.01)

    def _sendToRadioImpl(self, toRadio) -> None:
        b: bytes = toRadio.SerializeToString()
        if b and self.client and self.client.is_connected:
            logger.debug(f"TORADIO write: {b.hex()}")
            try:
                write_future = self.async_run(
                    self.client.write_gatt_char(TORADIO_UUID, b, response=True)
                )
                write_future.result(timeout=5.0)
                time.sleep(0.01)
                self.should_read = True
            except Exception as e:
                raise BLEInterface.BLEError("Error writing to BLE") from e

    def async_await(self, coro, timeout=None):
        future = asyncio.run_coroutine_threadsafe(coro, self._event_loop)
        try:
            return future.result(timeout)
        except FutureTimeoutError as e:
            future.cancel()
            raise TimeoutError("Timed out awaiting BLE operation") from e

    def async_run(self, coro) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self._event_loop)

    def _run_event_loop(self):
        try:
            self._event_loop.run_forever()
        finally:
            self._event_loop.close()

    @staticmethod
    def scan() -> List[BLEDevice]:
        """Scan for available BLE devices."""
        return asyncio.run(BleakScanner.discover(timeout=10, service_uuids=[SERVICE_UUID]))

    def from_num_handler(self, _, b: bytes) -> None:
        from_num = struct.unpack("<I", bytes(b))[0]
        logger.debug(f"FROMNUM notify: {from_num}")
        self.should_read = True