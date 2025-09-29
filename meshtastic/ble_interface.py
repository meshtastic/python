"""Bluetooth interface
"""
import asyncio
import atexit
import contextlib
import io
import logging
import struct
import sys
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
            address {str} -- The BLE address of the device to connect to. If None, 
                           will connect to any available Meshtastic BLE device.
            noProto {bool} -- If True, don't try to initialize the protobuf protocol 
                             (default: {False})
            debugOut {stream} -- If a stream is provided, any debug output will be 
                                emitted to that stream (default: {None})
            noNodes {bool} -- If True, don't try to read the node list from the device 
                              (default: {False})
            auto_reconnect {bool} -- If True, the interface will attempt to reconnect 
                                   automatically when disconnected. If False, the 
                                   interface will close completely on disconnect. 
                                   When True, disconnection events are sent via the 
                                   connection status callback, allowing applications 
                                   to handle reconnection logic (default: {True})
        """
        self._closing_lock: Lock = Lock()
        self._closing: bool = False
        self._exit_handler = None
        self.address = address
        self.auto_reconnect = auto_reconnect
        self._disconnect_notified = False
        self._reconnected_event = Event()

        MeshInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, noNodes=noNodes
        )

        self.should_read = False

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
            self.client = self.connect(address)
            logger.debug("BLE connected")
        except BLEInterface.BLEError as e:
            self.close()
            raise e

        if self.client.has_characteristic(LEGACY_LOGRADIO_UUID):
            self.client.start_notify(
                LEGACY_LOGRADIO_UUID, self.legacy_log_radio_handler
            )

        if self.client.has_characteristic(LOGRADIO_UUID):
            self.client.start_notify(LOGRADIO_UUID, self.log_radio_handler)

        logger.debug("Mesh configure starting")
        self._startConfig()
        if not self.noProto:
            self._waitConnected(timeout=60.0)
            self.waitForConfig()

        logger.debug("Register FROMNUM notify callback")
        self.client.start_notify(FROMNUM_UUID, self.from_num_handler)

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
            current_client = self.client
            if (
                current_client
                and getattr(current_client, "bleak_client", None) is not client
            ):
                logger.debug("Ignoring disconnect from a stale BLE client instance.")
                return
            previous_client = current_client
            self.client = None
            if previous_client:
                def _safe_close(c):
                    try:
                        c.close()
                    except Exception:  # pragma: no cover - defensive log
                        logger.debug("Error in BLEClientClose", exc_info=True)
                Thread(
                    target=_safe_close, args=(previous_client,), name="BLEClientClose", daemon=True
                ).start()
            self._disconnected()
            self._disconnect_notified = True
            self._reconnected_event.clear()
        else:
            Thread(target=self.close, name="BLEClose", daemon=True).start()

    def from_num_handler(self, _, b: bytes) -> None:  # pylint: disable=C0116
        """Handle callbacks for fromnum notify.
        Note: this method does not need to be async because it is just setting a bool.
        """
        from_num = struct.unpack("<I", bytes(b))[0]
        logger.debug(f"FROMNUM notify: {from_num}")
        self.should_read = True

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
            logger.info("Scanning for BLE devices (takes 10 seconds)...")
            response = client.discover(
                timeout=10, return_adv=True, service_uuids=[SERVICE_UUID]
            )

            devices = response.values()

            # bleak sometimes returns devices we didn't ask for, so filter the response
            # to only return true meshtastic devices
            # d[0] is the device. d[1] is the advertisement data
            devices = list(
                filter(lambda d: SERVICE_UUID in d[1].service_uuids, devices)
            )
            return list(map(lambda d: d[0], devices))

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
            raise BLEInterface.BLEError(
                f"No Meshtastic BLE peripheral with identifier or address '{address}' found. Try --ble-scan to find it."
            )
        if len(addressed_devices) > 1:
            raise BLEInterface.BLEError(
                f"More than one Meshtastic BLE peripheral with identifier or address '{address}' found."
            )
        return addressed_devices[0]

    @staticmethod
    def _sanitize_address(address: Optional[str]) -> Optional[str]:
        "Standardize BLE address by removing extraneous characters and lowercasing."
        if address is None:
            return None
        else:
            return address.replace("-", "").replace("_", "").replace(":", "").lower()

    def connect(self, address: Optional[str] = None) -> "BLEClient":
        "Connect to a device by address."

        # Bleak docs recommend always doing a scan before connecting (even if we know addr)
        device = self.find_device(address)
        client = BLEClient(
            device.address, disconnected_callback=self._on_ble_disconnect
        )
        client.connect()
        client.discover()
        # Reset disconnect notification flag on new connection
        self._disconnect_notified = False
        # Signal that reconnection has occurred
        self._reconnected_event.set()
        return client

    def _handle_read_loop_disconnect(self, error_message: str) -> bool:
        """Handle disconnection in the read loop.

        Returns
        -------
            bool: True if the loop should continue (for auto-reconnect), False if it should break
        """
        logger.debug(f"Device disconnected: {error_message}")
        if self.auto_reconnect:
            # Clear client to trigger reconnection logic
            self.client = None
            self._reconnected_event.clear()
            return True
        # End our read loop immediately
        self._want_receive = False
        return False

    def _receiveFromRadioImpl(self) -> None:
        while self._want_receive:
            if self.should_read:
                self.should_read = False
                retries: int = 0
                while self._want_receive:
                    client = self.client
                    if client is None:
                        if self.auto_reconnect:
                            logger.debug(
                                "BLE client is None, waiting for reconnection..."
                            )
                            # Wait for reconnection, but with a timeout to allow clean shutdown
                            self._reconnected_event.wait(timeout=1.0)
                            continue
                        logger.debug("BLE client is None, shutting down")
                        self._want_receive = False
                        continue
                    try:
                        b = bytes(client.read_gatt_char(FROMRADIO_UUID))
                    except BleakDBusError as e:
                        # Device disconnected probably
                        if self._handle_read_loop_disconnect(str(e)):
                            continue
                        break
                    except BleakError as e:
                        # Treat disconnected clients as a normal disconnect path without
                        # relying on error message contents from bleak.
                        if client and not client.is_connected():
                            if self._handle_read_loop_disconnect(str(e)):
                                continue
                            break
                        raise BLEInterface.BLEError("Error reading BLE") from e
                    if not b:
                        if retries < 5:
                            time.sleep(0.1)
                            retries += 1
                            continue
                        break
                    logger.debug(f"FROMRADIO read: {b.hex()}")
                    self._handleFromRadio(b)
            else:
                time.sleep(0.01)

    def _sendToRadioImpl(self, toRadio) -> None:
        b: bytes = toRadio.SerializeToString()
        client = self.client
        if b and client:  # we silently ignore writes while we are shutting down
            logger.debug(f"TORADIO write: {b.hex()}")
            try:
                client.write_gatt_char(
                    TORADIO_UUID, b, response=True
                )  # FIXME: or False?
                # search Bleak src for org.bluez.Error.InProgress
            except (BleakError, RuntimeError, OSError) as e:
                raise BLEInterface.BLEError("Error writing BLE") from e
            # Allow to propagate and then make sure we read
            time.sleep(0.01)
            self.should_read = True

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
        except Exception:
            logger.exception("Error closing mesh interface")

        if self._want_receive:
            self._want_receive = False  # Tell the thread we want it to stop
            if self._receiveThread:
                self._receiveThread.join(timeout=RECEIVE_THREAD_JOIN_TIMEOUT)
                self._receiveThread = None

        client = self.client
        if client:
            if self._exit_handler:
                with contextlib.suppress(ValueError):
                    atexit.unregister(self._exit_handler)
                self._exit_handler = None

            try:
                client.disconnect(timeout=DISCONNECT_TIMEOUT_SECONDS)
            except TimeoutError:
                logger.warning("Timed out waiting for BLE disconnect; forcing shutdown")
            except BleakError:
                logger.debug("BLE disconnect raised a BleakError", exc_info=True)
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Unexpected error during BLE disconnect")
            finally:
                try:
                    client.close()
                except Exception:  # pragma: no cover - defensive logging
                    logger.debug("Error closing BLE client", exc_info=True)
                self.client = None

        # Send disconnected indicator if not already notified
        if not self._disconnect_notified:
            self._ensure_pubsub_binding()
            self._disconnected()  # send the disconnected indicator up to clients
            self._disconnect_notified = True
            self._wait_for_disconnect_notifications()

    def _wait_for_disconnect_notifications(self, timeout: float = 0.5) -> None:
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
        except Exception:  # pragma: no cover - defensive logging
            logger.debug("Unable to flush disconnect notifications", exc_info=True)

    def _drain_publish_queue(self, flush_event: Event) -> None:
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
            except Exception:  # pragma: no cover - defensive logging
                logger.debug("Error running deferred publish", exc_info=True)

    def _ensure_pubsub_binding(self) -> None:
        try:
            pubsub_module = sys.modules.get("pubsub")
            if pubsub_module is None:
                return
            pub_instance = getattr(pubsub_module, "pub", None)
            if pub_instance is None:
                return
            import meshtastic.mesh_interface as mesh_module

            mesh_module.pub = pub_instance
        except Exception:  # pragma: no cover - defensive logging
            logger.debug("Unable to refresh pubsub binding", exc_info=True)


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
        except Exception:  # pragma: no cover - defensive logging
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

    def has_characteristic(self, specifier):
        """Check if the connected node supports a specified characteristic."""
        return bool(self.bleak_client.services.get_characteristic(specifier))

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
            raise TimeoutError from e

    def async_run(self, coro):  # pylint: disable=C0116
        return asyncio.run_coroutine_threadsafe(coro, self._eventLoop)

    def _run_event_loop(self):
        try:
            self._eventLoop.run_forever()
        finally:
            self._eventLoop.close()

    async def _stop_event_loop(self):
        self._eventLoop.stop()
