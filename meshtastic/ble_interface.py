"""Bluetooth interface
"""
import logging
import platform

from meshtastic.mesh_interface import MeshInterface
from meshtastic.util import our_exit

if platform.system() == 'Linux':
    # pylint: disable=E0401
    import pygatt



# Our standard BLE characteristics
TORADIO_UUID = "f75c76d2-129e-4dad-a1dd-7866124401e7"
FROMRADIO_UUID = "8ba2bcc2-ee02-4a55-a531-c525c5e454d5"
FROMNUM_UUID = "ed9da18c-a800-4f66-a670-aa7547e34453"


class BLEInterface(MeshInterface):
    """A not quite ready - FIXME - BLE interface to devices"""

    def __init__(self, address, noProto=False, debugOut=None):
        if platform.system() != 'Linux':
            our_exit("Linux is the only platform with experimental BLE support.", 1)
        self.address = address
        if not noProto:
            self.adapter = pygatt.GATTToolBackend()  # BGAPIBackend()
            self.adapter.start()
            logging.debug(f"Connecting to {self.address}")
            self.device = self.adapter.connect(address)
        else:
            self.adapter = None
            self.device = None
        logging.debug("Connected to device")
        # fromradio = self.device.char_read(FROMRADIO_UUID)
        MeshInterface.__init__(self, debugOut=debugOut, noProto=noProto)

        self._readFromRadio()  # read the initial responses

        def handle_data(handle, data): # pylint: disable=W0613
            self._handleFromRadio(data)

        if self.device:
            self.device.subscribe(FROMNUM_UUID, callback=handle_data)

    def _sendToRadioImpl(self, toRadio):
        """Send a ToRadio protobuf to the device"""
        #logging.debug(f"Sending: {stripnl(toRadio)}")
        b = toRadio.SerializeToString()
        self.device.char_write(TORADIO_UUID, b)

    def close(self):
        MeshInterface.close(self)
        if self.adapter:
            self.adapter.stop()

    def _readFromRadio(self):
        if not self.noProto:
            wasEmpty = False
            while not wasEmpty:
                if self.device:
                    b = self.device.char_read(FROMRADIO_UUID)
                    wasEmpty = len(b) == 0
                    if not wasEmpty:
                        self._handleFromRadio(b)
