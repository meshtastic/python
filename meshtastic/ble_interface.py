"""Bluetooth interface
"""
import asyncio
import atexit
import logging
import struct
import time
from threading import Thread
from typing import List, Optional
import print_color  # type: ignore[import-untyped]

from bleak import BleakClient, BleakScanner, BLEDevice
from bleak.exc import BleakDBusError, BleakError

import google.protobuf

from meshtastic.mesh_interface import MeshInterface

from .protobuf import (
    mesh_pb2,
)
SERVICE_UUID = "6ba1b218-15a8-461f-9fa8-5dcae273eafd"
TORADIO_UUID = "f75c76d2-129e-4dad-a1dd-7866124401e7"
FROMRADIO_UUID = "2c55e69e-4993-11ed-b878-0242ac120002"
FROMNUM_UUID = "ed9da18c-a800-4f66-a670-aa7547e34453"
LEGACY_LOGRADIO_UUID = "6c6fd238-78fa-436b-aacf-15c5be1ef2e2"
LOGRADIO_UUID = "5a3d6e49-06e6-4423-9944-e9de8cdf9547"


class BLEInterface(MeshInterface):
    """MeshInterface using BLE to connect to devices."""

    class BLEError(Exception):
        """An exception class for BLE errors."""

    def __init__(
        self,
        address: Optional[str],
        noProto: bool = False,
        debugOut=None,
        noNodes: bool = False,
    ):
        MeshInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, noNodes=noNodes
        )

        self.should_read = False

        logging.debug("Threads starting")
        self._want_receive = True
        self._receiveThread: Optional[Thread] = Thread(
            target=self._receiveFromRadioImpl, name="BLEReceive", daemon=True
        )
        self._receiveThread.start()
        logging.debug("Threads running")

        try:
            logging.debug(f"BLE connecting to: {address if address else 'any'}")
            self.client: Optional[BLEClient] = self.connect(address)
            logging.debug("BLE connected")
        except BLEInterface.BLEError as e:
            self.close()
            raise e

        if self.client.has_characteristic(LEGACY_LOGRADIO_UUID):
            self.client.start_notify(LEGACY_LOGRADIO_UUID, self.legacy_log_radio_handler)

        if self.client.has_characteristic(LOGRADIO_UUID):
            self.client.start_notify(LOGRADIO_UUID, self.log_radio_handler)

        logging.debug("Mesh configure starting")
        self._startConfig()
        if not self.noProto:
            self._waitConnected(timeout=60.0)
            self.waitForConfig()

        logging.debug("Register FROMNUM notify callback")
        self.client.start_notify(FROMNUM_UUID, self.from_num_handler)

        # We MUST run atexit (if we can) because otherwise (at least on linux) the BLE device is not disconnected
        # and future connection attempts will fail.  (BlueZ kinda sucks)
        # Note: the on disconnected callback will call our self.close which will make us nicely wait for threads to exit
        self._exit_handler = atexit.register(self.client.disconnect)

    def from_num_handler(self, _, b):  # pylint: disable=C0116
        """Handle callbacks for fromnum notify.
        Note: this method does not need to be async because it is just setting a bool.
        """
        from_num = struct.unpack("<I", bytes(b))[0]
        logging.debug(f"FROMNUM notify: {from_num}")
        self.should_read = True

    async def log_radio_handler(self, _, b):  # pylint: disable=C0116
        log_record = mesh_pb2.LogRecord()
        try:
            log_record.ParseFromString(bytes(b))
        except google.protobuf.message.DecodeError:
            return

        message = f'[{log_record.source}] {log_record.message}' if log_record.source else log_record.message

        if log_record.DEBUG:
            print_color.print(message, color="cyan", end=None)
        elif log_record.INFO:
            print_color.print(message, color="white", end=None)
        elif log_record.WARNING:
            print_color.print(message, color="yellow", end=None)
        elif log_record.ERROR:
            print_color.print(message, color="red", end=None)
        else:
            print_color.print(message, end=None)

    async def legacy_log_radio_handler(self, _, b):  # pylint: disable=C0116
        log_radio = b.decode("utf-8").replace("\n", "")
        if log_radio.startswith("DEBUG"):
            print_color.print(log_radio, color="cyan", end=None)
        elif log_radio.startswith("INFO"):
            print_color.print(log_radio, color="white", end=None)
        elif log_radio.startswith("WARN"):
            print_color.print(log_radio, color="yellow", end=None)
        elif log_radio.startswith("ERROR"):
            print_color.print(log_radio, color="red", end=None)
        else:
            print_color.print(log_radio, end=None)

    @staticmethod
    def scan() -> List[BLEDevice]:
        """Scan for available BLE devices."""
        with BLEClient() as client:
            logging.info("Scanning for BLE devices (takes 10 seconds)...")
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

    def _sanitize_address(address):  # pylint: disable=E0213
        "Standardize BLE address by removing extraneous characters and lowercasing."
        return address.replace("-", "").replace("_", "").replace(":", "").lower()

    def connect(self, address: Optional[str] = None) -> "BLEClient":
        "Connect to a device by address."

        # Bleak docs recommend always doing a scan before connecting (even if we know addr)
        device = self.find_device(address)
        client = BLEClient(device.address, disconnected_callback=lambda _: self.close)
        client.connect()
        client.discover()
        return client

    def _receiveFromRadioImpl(self):
        while self._want_receive:
            if self.should_read:
                self.should_read = False
                retries = 0
                while self._want_receive:
                    try:
                        b = bytes(self.client.read_gatt_char(FROMRADIO_UUID))
                    except BleakDBusError as e:
                        # Device disconnected probably, so end our read loop immediately
                        logging.debug(f"Device disconnected, shutting down {e}")
                        self._want_receive = False
                    except BleakError as e:
                        # We were definitely disconnected
                        if "Not connected" in str(e):
                            logging.debug(f"Device disconnected, shutting down {e}")
                            self._want_receive = False
                        else:
                            raise BLEInterface.BLEError("Error reading BLE") from e
                    if not b:
                        if retries < 5:
                            time.sleep(0.1)
                            retries += 1
                            continue
                        break
                    logging.debug(f"FROMRADIO read: {b.hex()}")
                    self._handleFromRadio(b)
            else:
                time.sleep(0.01)

    def _sendToRadioImpl(self, toRadio):
        b = toRadio.SerializeToString()
        if b:
            logging.debug(f"TORADIO write: {b.hex()}")
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

    def close(self):
        atexit.unregister(self._exit_handler)
        try:
            MeshInterface.close(self)
        except Exception as e:
            logging.error(f"Error closing mesh interface: {e}")

        if self._want_receive:
            self.want_receive = False  # Tell the thread we want it to stop
            self._receiveThread.join(timeout=2) # If bleak is hung, don't wait for the thread to exit (it is critical we disconnect)
            self._receiveThread = None

        if self.client:
            self.client.disconnect()
            self.client.close()
            self.client = None


class BLEClient:
    """Client for managing connection to a BLE device"""

    def __init__(self, address=None, **kwargs):
        self._eventLoop = asyncio.new_event_loop()
        self._eventThread = Thread(
            target=self._run_event_loop, name="BLEClient", daemon=True
        )
        self._eventThread.start()

        if not address:
            logging.debug("No address provided - only discover method will work.")
            return

        self.bleak_client = BleakClient(address, **kwargs)

    def discover(self, **kwargs):  # pylint: disable=C0116
        return self.async_await(BleakScanner.discover(**kwargs))

    def pair(self, **kwargs):  # pylint: disable=C0116
        return self.async_await(self.bleak_client.pair(**kwargs))

    def connect(self, **kwargs):  # pylint: disable=C0116
        return self.async_await(self.bleak_client.connect(**kwargs))

    def disconnect(self, **kwargs):  # pylint: disable=C0116
        self.async_await(self.bleak_client.disconnect(**kwargs))

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
