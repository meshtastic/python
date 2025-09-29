"""Bluetooth interface
"""
import asyncio
import atexit
import contextlib
import io
import logging
import struct
import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from queue import Empty
from threading import Event, Lock, Thread
from typing import List, Optional

import google.protobuf
from bleak import BleakClient, BleakScanner, BLEDevice
from bleak.exc import BleakDBusError, BleakError

from meshtastic import publishingThread
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
RECEIVE_THREAD_JOIN_TIMEOUT = 2.0

# BLE timeout and retry constants
BLE_SCAN_TIMEOUT = 10.0
RECEIVE_WAIT_TIMEOUT = 0.5
EMPTY_READ_RETRY_DELAY = 0.1
EMPTY_READ_MAX_RETRIES = 5
SEND_PROPAGATION_DELAY = 0.01
CONNECTION_TIMEOUT = 60.0

# Error message constants
ERROR_READING_BLE = "Error reading BLE"
ERROR_NO_PERIPHERAL_FOUND = "No Meshtastic BLE peripheral with identifier or address '{0}' found. Try --ble-scan to find it."
ERROR_MULTIPLE_PERIPHERALS_FOUND = (
    "More than one Meshtastic BLE peripheral with identifier or address '{0}' found."
)
ERROR_WRITING_BLE = (
    "Error writing BLE. This is often caused by missing Bluetooth "
    "permissions (e.g. not being in the 'bluetooth' group) or pairing issues."
)
ERROR_CONNECTION_FAILED = "Connection failed: {0}"
ERROR_ASYNC_TIMEOUT = "Async operation timed out"


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
        *,
        auto_reconnect: bool = True,
    ) -> None:
        """Constructor, opens a connection to a specified BLE device.

        Keyword Arguments:
        -----------------
            address {str} -- The BLE address of the device to connect to. If None,
                           will connect to any available Meshtastic BLE device.
            noProto {bool} -- If True, don't try to initialize the protobuf protocol
                             (default: {False})
            debugOut {stream} -- If a stream is provided, any debug output will be
                                emitted to that stream (default: {None})
            noNodes {bool} -- If True, don't try to read the node list from the device
                              (default: {False})
            auto_reconnect {bool} -- If True, the interface will not close itself upon
                                   disconnection. Instead, it will notify listeners
                                   via a connection status event, allowing the
                                   application to implement its own reconnection logic
                                   (e.g., by creating a new interface instance).
                                   If False, the interface will close completely
                                   on disconnect (default: {True})
        """
        self._closing_lock: Lock = Lock()
        self._client_lock: Lock = Lock()
        self._closing: bool = False
        self._exit_handler = None
        self.address = address
        self.auto_reconnect = auto_reconnect
        self._disconnect_notified = False
        self._read_trigger: Event = Event()
        self._malformed_notification_count = 0

        MeshInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, noNodes=noNodes
        )

        logger.debug("Threads starting")
        self._want_receive = True
        self._receiveThread: Optional[Thread] = Thread(
            target=self._receiveFromRadioImpl, name="BLEReceive", daemon=True
        )
        self._receiveThread.start()
        logger.debug("Threads running")

        self.client: Optional[BLEClient] = None
        try:
            logger.debug(f"BLE connecting to: {address if address else 'any'}")
            client = self.connect(address)
            with self._client_lock:
                self.client = client
            logger.debug("BLE connected")
        except BLEInterface.BLEError as e:
            self.close()
            raise BLEInterface.BLEError(ERROR_CONNECTION_FAILED.format(e)) from e

        logger.debug("Mesh configure starting")
        self._startConfig()
        if not self.noProto:
            self._waitConnected(timeout=CONNECTION_TIMEOUT)
            self.waitForConfig()

        # FROMNUM notification is set in _register_notifications

        # We MUST run atexit (if we can) because otherwise (at least on linux) the BLE device is not disconnected
        # and future connection attempts will fail.  (BlueZ kinda sucks)
        # Note: the on disconnected callback will call our self.close which will make us nicely wait for threads to exit
        self._exit_handler = atexit.register(self.close)

    def __repr__(self):
        rep = f"BLEInterface(address={self.address!r}"
        if self.debugOut is not None:
            rep += f", debugOut={self.debugOut!r}"
        if self.noProto:
            rep += ", noProto=True"
        if self.noNodes:
            rep += ", noNodes=True"
        if not self.auto_reconnect:
            rep += ", auto_reconnect=False"
        rep += ")"
        return rep

    def _on_ble_disconnect(self, client) -> None:
        """Disconnected callback from Bleak."""
        if self._closing:
            logger.debug(
                "Ignoring disconnect callback because a shutdown is already in progress."
            )
            return

        address = getattr(client, "address", repr(client))
        logger.debug(f"BLE client {address} disconnected.")
        if self.auto_reconnect:
            previous_client = None
            notify = False
            with self._client_lock:
                if self._disconnect_notified:
                    logger.debug("Ignoring duplicate disconnect callback.")
                    return

                current_client = self.client
                if (
                    current_client
                    and getattr(current_client, "bleak_client", None) is not client
                ):
                    logger.debug(
                        "Ignoring disconnect from a stale BLE client instance."
                    )
                    return
                previous_client = current_client
                self.client = None
                self._disconnect_notified = True
                notify = True

            if previous_client:
                Thread(
                    target=self._safe_close_client,
                    args=(previous_client,),
                    name="BLEClientClose",
                    daemon=True,
                ).start()
            if notify:
                self._disconnected()
            self._read_trigger.set()  # ensure receive loop wakes
        else:
            Thread(target=self.close, name="BLEClose", daemon=True).start()

    def from_num_handler(self, _, b: bytes) -> None:  # pylint: disable=C0116
        """Handle callbacks for fromnum notify.
        Note: this method does not need to be async because it is just setting an event.
        """
        try:
            if len(b) < 4:
                logger.debug("FROMNUM notify too short; ignoring")
                return
            from_num = struct.unpack("<I", bytes(b))[0]
            logger.debug(f"FROMNUM notify: {from_num}")
        except (struct.error, ValueError):
            self._malformed_notification_count += 1
            logger.debug("Malformed FROMNUM notify; ignoring", exc_info=True)
            if self._malformed_notification_count >= 10:
                logger.warning(
                    f"Received {self._malformed_notification_count} malformed FROMNUM notifications. "
                    "Check BLE connection stability."
                )
                self._malformed_notification_count = 0  # Reset counter after warning
            return
        finally:
            self._read_trigger.set()

    def _register_notifications(self, client: "BLEClient") -> None:
        """Register characteristic notifications for BLE client."""
        try:
            if client.has_characteristic(LEGACY_LOGRADIO_UUID):
                client.start_notify(LEGACY_LOGRADIO_UUID, self.legacy_log_radio_handler)
            if client.has_characteristic(LOGRADIO_UUID):
                client.start_notify(LOGRADIO_UUID, self.log_radio_handler)
            client.start_notify(FROMNUM_UUID, self.from_num_handler)
        except BleakError:
            logger.debug("Failed to start one or more notifications", exc_info=True)

    async def log_radio_handler(self, _, b):  # pylint: disable=C0116
        log_record = mesh_pb2.LogRecord()
        try:
            log_record.ParseFromString(bytes(b))

            message = (
                f"[{log_record.source}] {log_record.message}"
                if log_record.source
                else log_record.message
            )
            self._handleLogLine(message)
        except google.protobuf.message.DecodeError:
            logger.warning("Malformed LogRecord received. Skipping.")

    async def legacy_log_radio_handler(self, _, b):  # pylint: disable=C0116
        log_radio = b.decode("utf-8").replace("\n", "")
        self._handleLogLine(log_radio)

    @staticmethod
    def scan() -> List[BLEDevice]:
        """Scan for available BLE devices."""
        with BLEClient() as client:
            logger.info("Scanning for BLE devices (takes %.0f seconds)...", BLE_SCAN_TIMEOUT)
            response = client.discover(
                timeout=BLE_SCAN_TIMEOUT, return_adv=True, service_uuids=[SERVICE_UUID]
            )

            devices: List[BLEDevice] = []
            if isinstance(response, dict):
                for key, value in response.items():
                    if isinstance(value, tuple):
                        device, adv = value
                    else:
                        device, adv = key, value
                    suuids = getattr(adv, "service_uuids", None)
                    if suuids and SERVICE_UUID in suuids:
                        devices.append(device)
            else:  # list of BLEDevice
                for device in response:
                    adv = getattr(device, "advertisement_data", None)
                    suuids = getattr(adv, "service_uuids", None)
                    if suuids and SERVICE_UUID in suuids:
                        devices.append(device)
            return devices

    def find_device(self, address: Optional[str]) -> BLEDevice:
        """Find a device by address."""

        addressed_devices = BLEInterface.scan()

        if address:
            sanitized_address = self._sanitize_address(address)
            addressed_devices = list(
                filter(
                    lambda x: address in (x.name, x.address)
                    or (
                        sanitized_address
                        and self._sanitize_address(x.address) == sanitized_address
                    ),
                    addressed_devices,
                )
            )

        if len(addressed_devices) == 0:
            raise BLEInterface.BLEError(ERROR_NO_PERIPHERAL_FOUND.format(address))
        if len(addressed_devices) > 1:
            raise BLEInterface.BLEError(
                ERROR_MULTIPLE_PERIPHERALS_FOUND.format(address)
            )
        return addressed_devices[0]

    @staticmethod
    def _sanitize_address(address: Optional[str]) -> Optional[str]:
        "Standardize BLE address by removing extraneous characters and lowercasing."
        if address is None:
            return None
        else:
            return (
                address.strip()
                .replace("-", "")
                .replace("_", "")
                .replace(":", "")
                .lower()
            )

    def connect(self, address: Optional[str] = None) -> "BLEClient":
        "Connect to a device by address."

        # Bleak docs recommend always doing a scan before connecting (even if we know addr)
        device = self.find_device(address)
        client = BLEClient(
            device.address, disconnected_callback=self._on_ble_disconnect
        )
        client.connect()
        services = getattr(client.bleak_client, "services", None)
        if not services or not getattr(services, "get_characteristic", None):
            logger.debug(
                "BLE services not available immediately after connect; performing discover()"
            )
            client.get_services()
        # Ensure notifications are always active for this client (reconnect-safe)
        self._register_notifications(client)
        # Reset disconnect notification flag on new connection
        self._disconnect_notified = False
        return client

    def _handle_read_loop_disconnect(
        self, error_message: str, previous_client: Optional["BLEClient"]
    ) -> bool:
        """Handle disconnection in the read loop.

        Returns
        -------
            bool: True if the loop should continue (for auto-reconnect), False if it should break
        """
        logger.debug(f"Device disconnected: {error_message}")
        if self.auto_reconnect:
            notify_disconnect = False
            should_close = False
            with self._client_lock:
                current = self.client
                if previous_client and current is previous_client:
                    self.client = None
                    should_close = True
                if not self._disconnect_notified:
                    self._disconnect_notified = True
                    notify_disconnect = True
            if notify_disconnect:
                self._disconnected()
            if should_close and previous_client:
                Thread(
                    target=self._safe_close_client,
                    args=(previous_client,),
                    name="BLEClientClose",
                    daemon=True,
                ).start()
            self._read_trigger.clear()
            return True
        # End our read loop immediately
        self._want_receive = False
        return False

    def _safe_close_client(self, c: "BLEClient") -> None:
        """Safely close a BLEClient wrapper with exception handling."""
        try:
            c.close()
        except BleakError:
            logger.debug("BLE-specific error during client close", exc_info=True)
        except RuntimeError:
            logger.debug(
                "Runtime error during client close (possible threading issue)",
                exc_info=True,
            )
        except OSError:
            logger.debug(
                "OS error during client close (possible resource or permission issue)",
                exc_info=True,
            )

    def _receiveFromRadioImpl(self) -> None:
        try:
            while self._want_receive:
                if not self._read_trigger.wait(timeout=RECEIVE_WAIT_TIMEOUT):
                    continue
                self._read_trigger.clear()
                retries: int = 0
                while self._want_receive:
                    with self._client_lock:
                        client = self.client
                    if client is None:
                        if self.auto_reconnect:
                            logger.debug(
                                "BLE client is None; waiting for application-managed reconnect"
                            )
                            break
                        logger.debug("BLE client is None, shutting down")
                        self._want_receive = False
                        break
                    try:
                        b = bytes(client.read_gatt_char(FROMRADIO_UUID))
                        if not b:
                            if retries < EMPTY_READ_MAX_RETRIES:
                                time.sleep(EMPTY_READ_RETRY_DELAY)
                                retries += 1
                                continue
                            break
                        logger.debug(f"FROMRADIO read: {b.hex()}")
                        self._handleFromRadio(b)
                        retries = 0
                    except BleakDBusError as e:
                        if self._handle_read_loop_disconnect(str(e), client):
                            break
                        return
                    except BleakError as e:
                        if client and not client.is_connected():
                            if self._handle_read_loop_disconnect(str(e), client):
                                break
                            return
                        logger.debug("Error reading BLE", exc_info=True)
                        raise BLEInterface.BLEError(ERROR_READING_BLE) from e
        except (
            BLEInterface.BLEError,
            RuntimeError,
            OSError,
            google.protobuf.message.DecodeError,
        ):
            logger.exception("Fatal error in BLE receive thread, closing interface.")
            if not self._closing:
                # Use a thread to avoid deadlocks if close() waits for this thread
                Thread(target=self.close, name="BLECloseOnError", daemon=True).start()

    def _sendToRadioImpl(self, toRadio) -> None:
        b: bytes = toRadio.SerializeToString()
        with self._client_lock:
            client = self.client
        if b and client:  # we silently ignore writes while we are shutting down
            logger.debug(f"TORADIO write: {b.hex()}")
            try:
                # Use write-with-response to ensure delivery is acknowledged by the peripheral.
                client.write_gatt_char(TORADIO_UUID, b, response=True)
            except BleakError as e:
                logger.debug("BLE-specific error during write operation", exc_info=True)
                raise BLEInterface.BLEError(ERROR_WRITING_BLE) from e
            except RuntimeError as e:
                logger.debug(
                    "Runtime error during write operation (possible threading issue)",
                    exc_info=True,
                )
                raise BLEInterface.BLEError(ERROR_WRITING_BLE) from e
            except OSError as e:
                logger.debug(
                    "OS error during write operation (possible resource or permission issue)",
                    exc_info=True,
                )
                raise BLEInterface.BLEError(ERROR_WRITING_BLE) from e
            # Allow to propagate and then prompt the reader
            time.sleep(SEND_PROPAGATION_DELAY)
            self._read_trigger.set()

    def close(self) -> None:
        with self._closing_lock:
            if self._closing:
                logger.debug(
                    "BLEInterface.close called while another shutdown is in progress; ignoring"
                )
                return
            self._closing = True

        try:
            MeshInterface.close(self)
        except (
            MeshInterface.MeshInterfaceError,
            RuntimeError,
            BLEInterface.BLEError,
            OSError,
        ):
            logger.exception("Error closing mesh interface")

        if self._want_receive:
            self._want_receive = False  # Tell the thread we want it to stop
            self._read_trigger.set()  # Wake up the receive thread if it's waiting
            if self._receiveThread:
                self._receiveThread.join(timeout=RECEIVE_THREAD_JOIN_TIMEOUT)
                if self._receiveThread.is_alive():
                    logger.warning(
                        "BLE receive thread did not exit within %.1fs",
                        RECEIVE_THREAD_JOIN_TIMEOUT,
                    )
                self._receiveThread = None

        if self._exit_handler:
            with contextlib.suppress(ValueError):
                atexit.unregister(self._exit_handler)
            self._exit_handler = None

        with self._client_lock:
            client = self.client
            self.client = None
        if client:
            try:
                client.disconnect(timeout=DISCONNECT_TIMEOUT_SECONDS)
            except BLEInterface.BLEError:
                logger.warning("Timed out waiting for BLE disconnect; forcing shutdown")
            except BleakError:
                logger.debug(
                    "BLE-specific error during disconnect operation", exc_info=True
                )
            except (RuntimeError, OSError):  # pragma: no cover - defensive logging
                logger.debug(
                    "OS/Runtime error during disconnect (possible resource or threading issue)",
                    exc_info=True,
                )
            finally:
                try:
                    client.close()
                except BleakError:  # pragma: no cover - defensive logging
                    logger.debug(
                        "BLE-specific error during client close", exc_info=True
                    )
                except (RuntimeError, OSError):  # pragma: no cover - defensive logging
                    logger.debug(
                        "OS/Runtime error during client close (possible resource or threading issue)",
                        exc_info=True,
                    )

        # Send disconnected indicator if not already notified
        notify = False
        with self._client_lock:
            if not self._disconnect_notified:
                self._disconnect_notified = True
                notify = True

        if notify:
            self._disconnected()  # send the disconnected indicator up to clients
            self._wait_for_disconnect_notifications()

    def _wait_for_disconnect_notifications(
        self, timeout: float = DISCONNECT_TIMEOUT_SECONDS
    ) -> None:
        """Wait briefly for queued pubsub notifications to flush before returning."""
        flush_event = Event()
        try:
            publishingThread.queueWork(flush_event.set)
            if not flush_event.wait(timeout=timeout):
                thread = getattr(publishingThread, "thread", None)
                if thread is not None and thread.is_alive():
                    logger.debug("Timed out waiting for publish queue flush")
                else:
                    self._drain_publish_queue(flush_event)
        except RuntimeError:  # pragma: no cover - defensive logging
            logger.debug(
                "Runtime error during disconnect notification flush (possible threading issue)",
                exc_info=True,
            )
        except ValueError:  # pragma: no cover - defensive logging
            logger.debug(
                "Value error during disconnect notification flush (possible invalid event state)",
                exc_info=True,
            )

    def _drain_publish_queue(self, flush_event: Event) -> None:
        """Drain queued publish runnables during close.

        Note: This executes queued runnables inline on the caller's thread,
        which may run user callbacks in an unexpected context during close.
        All runnables are wrapped in try/except for error handling.
        """
        queue = getattr(publishingThread, "queue", None)
        if queue is None:
            return
        while not flush_event.is_set():
            try:
                runnable = queue.get_nowait()
            except Empty:
                break
            try:
                runnable()
            except RuntimeError as exc:  # pragma: no cover - defensive logging
                logger.debug(
                    "Runtime error in deferred publish callback (possible threading issue): %s",
                    exc,
                    exc_info=True,
                )
            except ValueError as exc:  # pragma: no cover - defensive logging
                logger.debug(
                    "Value error in deferred publish callback (possible invalid callback state): %s",
                    exc,
                    exc_info=True,
                )


class BLEClient:
    """Client for managing connection to a BLE device"""

    def __init__(self, address=None, **kwargs) -> None:
        self._eventLoop = asyncio.new_event_loop()
        self._eventThread = Thread(
            target=self._run_event_loop, name="BLEClient", daemon=True
        )
        self._eventThread.start()

        if not address:
            logger.debug("No address provided - only discover method will work.")
            return

        self.bleak_client = BleakClient(address, **kwargs)

    def discover(self, **kwargs):  # pylint: disable=C0116
        return self.async_await(BleakScanner.discover(**kwargs))

    def pair(self, **kwargs):  # pylint: disable=C0116
        return self.async_await(self.bleak_client.pair(**kwargs))

    def connect(self, **kwargs):  # pylint: disable=C0116
        return self.async_await(self.bleak_client.connect(**kwargs))

    def is_connected(self) -> bool:
        """Return the bleak client's connection state when available."""
        bleak_client = getattr(self, "bleak_client", None)
        if bleak_client is None:
            return False
        try:
            connected = getattr(bleak_client, "is_connected", False)
            if callable(connected):
                connected = connected()
            return bool(connected)
        except (
            AttributeError,
            TypeError,
            RuntimeError,
        ):  # pragma: no cover - defensive logging
            logger.debug("Unable to read bleak connection state", exc_info=True)
            return False

    def disconnect(
        self, timeout: Optional[float] = None, **kwargs
    ):  # pylint: disable=C0116
        self.async_await(self.bleak_client.disconnect(**kwargs), timeout=timeout)

    def read_gatt_char(self, *args, **kwargs):  # pylint: disable=C0116
        return self.async_await(self.bleak_client.read_gatt_char(*args, **kwargs))

    def write_gatt_char(self, *args, **kwargs):  # pylint: disable=C0116
        self.async_await(self.bleak_client.write_gatt_char(*args, **kwargs))

    def get_services(self):
        """Get services from the BLE client."""
        return self.async_await(self.bleak_client.get_services())

    def has_characteristic(self, specifier):
        """Check if the connected node supports a specified characteristic."""
        services = getattr(self.bleak_client, "services", None)
        if not services or not getattr(services, "get_characteristic", None):
            try:
                self.get_services()
                services = getattr(self.bleak_client, "services", None)
            except (TimeoutError, BleakError):  # pragma: no cover - defensive
                logger.debug("Unable to populate services before has_characteristic", exc_info=True)
        return bool(services and services.get_characteristic(specifier))

    def start_notify(self, *args, **kwargs):  # pylint: disable=C0116
        self.async_await(self.bleak_client.start_notify(*args, **kwargs))

    def close(self):  # pylint: disable=C0116
        self.async_run(self._stop_event_loop())
        self._eventThread.join()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()

    def async_await(self, coro, timeout=None):  # pylint: disable=C0116
        future = self.async_run(coro)
        try:
            return future.result(timeout)
        except FutureTimeoutError as e:
            future.cancel()
            raise BLEInterface.BLEError(ERROR_ASYNC_TIMEOUT) from e

    def async_run(self, coro):  # pylint: disable=C0116
        return asyncio.run_coroutine_threadsafe(coro, self._eventLoop)

    def _run_event_loop(self):
        try:
            self._eventLoop.run_forever()
        finally:
            self._eventLoop.close()

    async def _stop_event_loop(self):
        self._eventLoop.stop()
