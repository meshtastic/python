"""Bluetooth interface
"""
import asyncio
import atexit
import logging
import struct
import sys
import time
import io
from concurrent.futures import TimeoutError as FuturesTimeoutError
from threading import Thread
from typing import Any, List, Optional

import google.protobuf
from bleak import BleakClient, BleakScanner, BLEDevice
from bleak.exc import BleakDBusError, BleakError

from meshtastic.mesh_interface import MeshInterface
from meshtastic.verbosity import (
    cli_verbosity_debug_enabled,
    cli_verbosity_full_enabled,
    cli_verbosity_progress_enabled,
)

from .protobuf import mesh_pb2

SERVICE_UUID = "6ba1b218-15a8-461f-9fa8-5dcae273eafd"
TORADIO_UUID = "f75c76d2-129e-4dad-a1dd-7866124401e7"
FROMRADIO_UUID = "2c55e69e-4993-11ed-b878-0242ac120002"
FROMNUM_UUID = "ed9da18c-a800-4f66-a670-aa7547e34453"
LEGACY_LOGRADIO_UUID = "6c6fd238-78fa-436b-aacf-15c5be1ef2e2"
LOGRADIO_UUID = "5a3d6e49-06e6-4423-9944-e9de8cdf9547"
logger = logging.getLogger(__name__)


class BLEInterface(MeshInterface):
    """MeshInterface using BLE to connect to devices."""

    class BLEError(Exception):
        """An exception class for BLE errors."""

    def __init__( # pylint: disable=R0917
        self,
        address: Optional[str],
        noProto: bool = False,
        debugOut: Optional[io.TextIOWrapper]=None,
        noNodes: bool = False,
        timeout: int = 300,
    ) -> None:
        MeshInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, noNodes=noNodes, timeout=timeout
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
        self._exit_handler = atexit.register(self.client.disconnect)

    def __repr__(self):
        rep = f"BLEInterface(address={self.client.address if self.client else None!r}"
        if self.debugOut is not None:
            rep += f", debugOut={self.debugOut!r}"
        if self.noProto:
            rep += ", noProto=True"
        if self.noNodes:
            rep += ", noNodes=True"
        rep += ")"
        return rep

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
            scan_duration = 10
            verbose = cli_verbosity_full_enabled()
            debug = cli_verbosity_debug_enabled()
            normal_mode = not (debug or verbose)
            scan_message = "Scanning for BLE..."
            logger.debug(
                "Scanning for BLE devices (takes %s seconds)...", scan_duration
            )
            if normal_mode:
                sys.stdout.write(scan_message)
                sys.stdout.flush()
            else:
                logger.info(
                    "Scanning for BLE devices (takes %s seconds)...", scan_duration
                )

            devices: dict[str, tuple[BLEDevice, Any]] = {}
            elapsed = 0
            step = 1
            newline_emitted = False
            while elapsed < scan_duration:
                chunk = min(step, scan_duration - elapsed)
                response = client.discover(
                    timeout=chunk, return_adv=True, service_uuids=[SERVICE_UUID]
                )

                for entry in response.values():
                    device, adv = entry
                    if SERVICE_UUID not in adv.service_uuids:
                        continue
                    device_key = device.address or device.name or repr(device)
                    if device_key not in devices:
                        if verbose:
                            if not newline_emitted:
                                sys.stdout.write("\n")
                                sys.stdout.flush()
                                newline_emitted = True
                            display_name = device.name or device.address or device_key
                            address_suffix = (
                                f" ({device.address})" if device.address else ""
                            )
                            rssi = getattr(adv, "rssi", None)
                            rssi_suffix = f" rssi={rssi}" if rssi is not None else ""
                            print(
                                f'Found BLE device "{display_name}"{address_suffix}{rssi_suffix}'
                            )
                        logger.debug(
                            "Discovered BLE device name='%s' address='%s' rssi=%s",
                            device.name,
                            device.address,
                            getattr(adv, "rssi", "unknown"),
                        )
                    devices[device_key] = entry

                if normal_mode:
                    sys.stdout.write(".")
                    sys.stdout.flush()
                elapsed += chunk

            if normal_mode:
                sys.stdout.write("\n")
                sys.stdout.flush()

            logger.info("Scan complete. %s device(s) found.", len(devices))
            return [entry[0] for entry in devices.values()]

    def find_device(self, address: Optional[str]) -> BLEDevice:
        """Find a device by address."""

        addressed_devices = BLEInterface.scan()

        if address:
            addressed_devices = list(
                filter(
                    lambda x: address in (x.name, x.address),
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

    def _sanitize_address(self, address: Optional[str]) -> Optional[str]:  # pylint: disable=E0213
        "Standardize BLE address by removing extraneous characters and lowercasing."
        if address is None:
            return None
        else:
            return address.replace("-", "").replace("_", "").replace(":", "").lower()

    def connect(self, address: Optional[str] = None) -> "BLEClient":
        "Connect to a device by address."

        # Bleak docs recommend always doing a scan before connecting (even if we know addr)
        device = self.find_device(address)
        display_name = device.name or device.address or repr(device)
        if cli_verbosity_full_enabled():
            print(f'Connecting to BLE device "{display_name}"...', flush=True)
        elif cli_verbosity_progress_enabled():
            print("Connecting to BLE device...", flush=True)

        client = BLEClient(device.address, disconnected_callback=lambda _: self.close())
        client.connect()
        if cli_verbosity_full_enabled():
            print("Discovering BLE services...", flush=True)
        elif cli_verbosity_progress_enabled():
            print("Negotiating services...", flush=True)
        client.discover()
        return client

    def _receiveFromRadioImpl(self) -> None:
        while self._want_receive:
            if self.should_read:
                self.should_read = False
                retries: int = 0
                while self._want_receive:
                    if self.client is None:
                        logger.debug(f"BLE client is None, shutting down")
                        self._want_receive = False
                        continue
                    try:
                        b = bytes(self.client.read_gatt_char(FROMRADIO_UUID))
                    except BleakDBusError as e:
                        # Device disconnected probably, so end our read loop immediately
                        logger.debug(f"Device disconnected, shutting down {e}")
                        self._want_receive = False
                    except BleakError as e:
                        # We were definitely disconnected
                        if "Not connected" in str(e):
                            logger.debug(f"Device disconnected, shutting down {e}")
                            self._want_receive = False
                        else:
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
        if b and self.client:  # we silently ignore writes while we are shutting down
            logger.debug(f"TORADIO write: {b.hex()}")
            try:
                self.client.write_gatt_char(
                    TORADIO_UUID, b, response=True
                )  # FIXME: or False?
                # search Bleak src for org.bluez.Error.InProgress
            except Exception as e:
                raise BLEInterface.BLEError(
                    "Error writing BLE (are you in the 'bluetooth' user group? did you enter the pairing PIN on your computer?)"
                ) from e
            # Allow to propagate and then make sure we read
            time.sleep(0.01)
            self.should_read = True

    def close(self) -> None:
        try:
            MeshInterface.close(self)
        except Exception as e:
            logger.error(f"Error closing mesh interface: {e}")

        if self._want_receive:
            self._want_receive = False  # Tell the thread we want it to stop
            if self._receiveThread:
                self._receiveThread.join(
                    timeout=2
                )  # If bleak is hung, don't wait for the thread to exit (it is critical we disconnect)
                self._receiveThread = None

        disconnect_future = None
        if self.client:
            atexit.unregister(self._exit_handler)
            disconnect_future = self.client.disconnect(timeout=0)
            if disconnect_future is not None:
                # allow brief time for disconnect to complete without blocking
                try:
                    disconnect_future.result(timeout=0.1)
                except FuturesTimeoutError:
                    disconnect_future.cancel()
                except Exception as exc:  # pylint: disable=broad-except
                    logger.debug("Error completing BLE disconnect: %s", exc)
            self.client.close()
            self.client = None
        self._disconnected() # send the disconnected indicator up to clients


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

    def disconnect(self, *, timeout: Optional[float] = 5, **kwargs):  # pylint: disable=C0116
        if not self.bleak_client:
            return None
        future = self.async_run(self.bleak_client.disconnect(**kwargs))
        if timeout is None:
            try:
                future.result()
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("Error during BLE disconnect: %s", exc)
            return future
        if timeout <= 0:
            return future
        try:
            future.result(timeout=timeout)
        except FuturesTimeoutError:
            logger.warning("Timeout while disconnecting BLE client; proceeding with close.")
            future.cancel()
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("Error during BLE disconnect: %s", exc)
        return future

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
        return self.async_run(coro).result(timeout)

    def async_run(self, coro):  # pylint: disable=C0116
        return asyncio.run_coroutine_threadsafe(coro, self._eventLoop)

    def _run_event_loop(self):
        try:
            self._eventLoop.run_forever()
        finally:
            self._eventLoop.close()

    async def _stop_event_loop(self):
        self._eventLoop.stop()
