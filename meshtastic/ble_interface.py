"""Bluetooth interface
"""
import logging
import time
import struct
import asyncio
from threading import Thread, Event
from typing import Optional

from bleak import BleakScanner, BleakClient

from meshtastic.mesh_interface import MeshInterface
from meshtastic.util import our_exit

SERVICE_UUID = "6ba1b218-15a8-461f-9fa8-5dcae273eafd"
TORADIO_UUID = "f75c76d2-129e-4dad-a1dd-7866124401e7"
FROMRADIO_UUID = "2c55e69e-4993-11ed-b878-0242ac120002"
FROMNUM_UUID = "ed9da18c-a800-4f66-a670-aa7547e34453"


class BLEInterface(MeshInterface):
    """MeshInterface using BLE to connect to devices"""
    class BLEError(Exception):
        """An exception class for BLE errors"""
        def __init__(self, message):
            self.message = message
            super().__init__(self.message)

    class BLEState(): # pylint: disable=C0115
        THREADS = False
        BLE = False
        MESH = False


    def __init__(self, address: Optional[str], noProto: bool = False, debugOut = None, noNodes: bool = False):
        self.state = BLEInterface.BLEState()

        if not address:
            return

        self.should_read = False

        logging.debug("Threads starting")
        self._receiveThread = Thread(target = self._receiveFromRadioImpl)
        self._receiveThread_started = Event()
        self._receiveThread_stopped = Event()
        self._receiveThread.start()
        self._receiveThread_started.wait(1)
        self.state.THREADS = True
        logging.debug("Threads running")

        try:
            logging.debug(f"BLE connecting to: {address}")
            self.client = self.connect(address)
            self.state.BLE = True
            logging.debug("BLE connected")
        except BLEInterface.BLEError as e:
            self.close()
            our_exit(e.message, 1)
            return

        logging.debug("Mesh init starting")
        MeshInterface.__init__(self, debugOut = debugOut, noProto = noProto, noNodes = noNodes)
        self._startConfig()
        if not self.noProto:
            self._waitConnected(timeout = 60.0)
            self.waitForConfig()
        self.state.MESH = True
        logging.debug("Mesh init finished")

        logging.debug("Register FROMNUM notify callback")
        self.client.start_notify(FROMNUM_UUID, self.from_num_handler)


    async def from_num_handler(self, _, b): # pylint: disable=C0116
        from_num = struct.unpack('<I', bytes(b))[0]
        logging.debug(f"FROMNUM notify: {from_num}")
        self.should_read = True


    def scan(self):
        "Scan for available BLE devices"
        with BLEClient() as client:
            return [
                (x[0], x[1]) for x in (client.discover(
                    return_adv = True,
                    service_uuids = [ SERVICE_UUID ]
                )).values()
            ]


    def find_device(self, address):
        "Find a device by address"
        meshtastic_devices = self.scan()

        addressed_devices = list(filter(lambda x: address in (x[1].local_name, x[0].name), meshtastic_devices))
        # If nothing is found try on the address
        if len(addressed_devices) == 0:
            addressed_devices = list(filter(
                lambda x: BLEInterface._sanitize_address(address) == BLEInterface._sanitize_address(x[0].address),
                meshtastic_devices))

        if len(addressed_devices) == 0:
            raise BLEInterface.BLEError(f"No Meshtastic BLE peripheral with identifier or address '{address}' found. Try --ble-scan to find it.")
        if len(addressed_devices) > 1:
            raise BLEInterface.BLEError(f"More than one Meshtastic BLE peripheral with identifier or address '{address}' found.")
        return addressed_devices[0][0]

    def _sanitize_address(address): # pylint: disable=E0213
        "Standardize BLE address by removing extraneous characters and lowercasing"
        return address \
            .replace("-", "") \
            .replace("_", "") \
            .replace(":", "") \
            .lower()

    def connect(self, address):
        "Connect to a device by address"
        device = self.find_device(address)
        client = BLEClient(device.address)
        client.connect()
        try:
            client.pair()
        except NotImplementedError:
            # Some bluetooth backends do not require explicit pairing.
            # See Bleak docs for details on this.
            pass
        return client


    def _receiveFromRadioImpl(self):
        self._receiveThread_started.set()
        while self._receiveThread_started.is_set():
            if self.should_read:
                self.should_read = False
                retries = 0
                while True:
                    b = bytes(self.client.read_gatt_char(FROMRADIO_UUID))
                    if not b:
                        if retries < 5:
                            time.sleep(0.1)
                            retries += 1
                            continue
                        break
                    logging.debug(f"FROMRADIO read: {b.hex()}")
                    self._handleFromRadio(b)
            else:
                time.sleep(0.1)
        self._receiveThread_stopped.set()

    def _sendToRadioImpl(self, toRadio):
        b = toRadio.SerializeToString()
        if b:
            logging.debug(f"TORADIO write: {b.hex()}")
            self.client.write_gatt_char(TORADIO_UUID, b, response = True)
            # Allow to propagate and then make sure we read
            time.sleep(0.1)
            self.should_read = True


    def close(self):
        if self.state.MESH:
            MeshInterface.close(self)

        if self.state.THREADS:
            self._receiveThread_started.clear()
            self._receiveThread_stopped.wait(5)

        if self.state.BLE:
            self.client.disconnect()
            self.client.close()


class BLEClient():
    """Client for managing connection to a BLE device"""
    def __init__(self, address = None, **kwargs):
        self._eventThread = Thread(target = self._run_event_loop)
        self._eventThread_started = Event()
        self._eventThread_stopped = Event()
        self._eventThread.start()
        self._eventThread_started.wait(1)

        if not address:
            logging.debug("No address provided - only discover method will work.")
            return

        self.bleak_client = BleakClient(address, **kwargs)


    def discover(self, **kwargs): # pylint: disable=C0116
        return self.async_await(BleakScanner.discover(**kwargs))

    def pair(self, **kwargs): # pylint: disable=C0116
        return self.async_await(self.bleak_client.pair(**kwargs))

    def connect(self, **kwargs): # pylint: disable=C0116
        return self.async_await(self.bleak_client.connect(**kwargs))

    def disconnect(self, **kwargs): # pylint: disable=C0116
        self.async_await(self.bleak_client.disconnect(**kwargs))

    def read_gatt_char(self, *args, **kwargs): # pylint: disable=C0116
        return self.async_await(self.bleak_client.read_gatt_char(*args, **kwargs))

    def write_gatt_char(self, *args, **kwargs): # pylint: disable=C0116
        self.async_await(self.bleak_client.write_gatt_char(*args, **kwargs))

    def start_notify(self, *args, **kwargs): # pylint: disable=C0116
        self.async_await(self.bleak_client.start_notify(*args, **kwargs))

    def close(self): # pylint: disable=C0116
        self.async_run(self._stop_event_loop())
        self._eventThread_stopped.wait(5)

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()

    def async_await(self, coro, timeout = None): # pylint: disable=C0116
        return self.async_run(coro).result(timeout)

    def async_run(self, coro): # pylint: disable=C0116
        return asyncio.run_coroutine_threadsafe(coro, self._eventLoop)

    def _run_event_loop(self):
        # I don't know if the event loop can be initialized in __init__ so silencing pylint
        self._eventLoop = asyncio.new_event_loop() # pylint: disable=W0201
        self._eventThread_started.set()
        try:
            self._eventLoop.run_forever()
        finally:
            self._eventLoop.close()
        self._eventThread_stopped.set()

    async def _stop_event_loop(self):
        self._eventLoop.stop()
