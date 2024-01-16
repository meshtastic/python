"""Bluetooth interface
"""
import logging
import time
import struct
from threading import Thread, Event
from meshtastic.mesh_interface import MeshInterface
from meshtastic.util import our_exit
from bleak import BleakScanner, BleakClient
import asyncio


SERVICE_UUID = "6ba1b218-15a8-461f-9fa8-5dcae273eafd"
TORADIO_UUID = "f75c76d2-129e-4dad-a1dd-7866124401e7"
FROMRADIO_UUID = "2c55e69e-4993-11ed-b878-0242ac120002"
FROMNUM_UUID = "ed9da18c-a800-4f66-a670-aa7547e34453"


class BLEInterface(MeshInterface):
    class BLEError(Exception):
        def __init__(self, message):
            self.message = message
            super().__init__(self.message)


    class BLEState():
        THREADS = False
        BLE = False
        MESH = False


    def __init__(self, address, noProto = False, debugOut = None):
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
        MeshInterface.__init__(self, debugOut = debugOut, noProto = noProto)
        self._startConfig()
        if not self.noProto:
            self._waitConnected()
            self.waitForConfig()
        self.state.MESH = True
        logging.debug("Mesh init finished")

        logging.debug("Register FROMNUM notify callback")
        self.client.start_notify(FROMNUM_UUID, self.from_num_handler)


    async def from_num_handler(self, _, b):
        from_num = struct.unpack('<I', bytes(b))[0]
        logging.debug(f"FROMNUM notify: {from_num}")
        self.should_read = True


    def scan(self):
        with BLEClient() as client:
            return [
                (x[0], x[1]) for x in (client.discover(
                    return_adv = True,
                    service_uuids = [ SERVICE_UUID ]
                )).values()
            ]


    def find_device(self, address):
        meshtastic_devices = self.scan()

        addressed_devices = list(filter(lambda x: address == x[1].local_name or address == x[0].name, meshtastic_devices))
        # If nothing is found try on the address
        if len(addressed_devices) == 0:
            addressed_devices = list(filter(lambda x: BLEInterface._sanitize_address(address) == BLEInterface._sanitize_address(x[0].address), meshtastic_devices))

        if len(addressed_devices) == 0:
            raise BLEInterface.BLEError(f"No Meshtastic BLE peripheral with identifier or address '{address}' found. Try --ble-scan to find it.")
        if len(addressed_devices) > 1:
            raise BLEInterface.BLEError(f"More than one Meshtastic BLE peripheral with identifier or address '{address}' found.")
        return addressed_devices[0][0]

    def _sanitize_address(address):
        return address \
            .replace("-", "") \
            .replace("_", "") \
            .replace(":", "") \
            .lower()

    def connect(self, address):
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
                while True:
                    b = bytes(self.client.read_gatt_char(FROMRADIO_UUID))
                    if not b:
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


    def discover(self, **kwargs):
        return self.async_await(BleakScanner.discover(**kwargs))

    def pair(self, **kwargs):
        return self.async_await(self.bleak_client.pair(**kwargs))

    def connect(self, **kwargs):
        return self.async_await(self.bleak_client.connect(**kwargs))

    def disconnect(self, **kwargs):
        self.async_await(self.bleak_client.disconnect(**kwargs))

    def read_gatt_char(self, *args, **kwargs):
        return self.async_await(self.bleak_client.read_gatt_char(*args, **kwargs))

    def write_gatt_char(self, *args, **kwargs):
        self.async_await(self.bleak_client.write_gatt_char(*args, **kwargs))

    def start_notify(self, *args, **kwargs):
        self.async_await(self.bleak_client.start_notify(*args, **kwargs))


    def close(self):
        self.async_run(self._stop_event_loop())
        self._eventThread_stopped.wait(5)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


    def async_await(self, coro, timeout = None):
        return self.async_run(coro).result(timeout)

    def async_run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._eventLoop)

    def _run_event_loop(self):
        self._eventLoop = asyncio.new_event_loop()
        self._eventThread_started.set()
        try:
            self._eventLoop.run_forever()
        finally:
            self._eventLoop.close()
        self._eventThread_stopped.set()

    async def _stop_event_loop(self):
        self._eventLoop.stop()
