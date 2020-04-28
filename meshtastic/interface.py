
import serial
import threading
import logging
import sys
from . import mesh_pb2

START1 = 0x94
START2 = 0xc3
HEADER_LEN = 4
MAX_TO_FROM_RADIO_SIZE = 512


"""

TODO: 
* use port enumeration to find ports https://pyserial.readthedocs.io/en/latest/shortintro.html


Contains a reader thread that is always trying to read on the serial port.

methods:

- constructor(serialPort)
- sendData(destinationId, bytes, variant)
- sendPacket(destinationId, meshPacket) - throws errors if we have errors talking to the device
- close() - shuts down the interface
- init() - starts the enumeration process to download NodeDB etc... - we will not publish to topics until this enumeration completes
- radioConfig - getter/setter syntax: https://www.python-course.eu/python3_properties.php
- nodes - the database of received nodes
- myNodeInfo
- myNodeId

## PubSub topics

Use a pubsub model to communicate events [https://pypubsub.readthedocs.io/en/v4.0.3/ ]

- meshtastic.send(MeshPacket) - Not implemented, instead call send(packet) on MeshInterface
- meshtastic.connection.established - published once we've successfully connected to the radio and downloaded the node DB
- meshtastic.connection.lost - published once we've lost our link to the radio
- meshtastic.receive.position(MeshPacket)
- meshtastic.receive.user(MeshPacket)
- meshtastic.receive.data(MeshPacket)
- meshtastic.node.updated(NodeInfo) - published when a node in the DB changes (appears, location changed, username changed, etc...)
- meshtastic.debug(string)

"""


class MeshInterface:
    """Interface class for meshtastic devices"""

    def __init__(self):
        self.debugOut = sys.stdout
        self.nodes = None  # FIXME
        self.configId = 17
        self._startConfig()

    def _startConfig(self):
        """Start device packets flowing"""
        startConfig = mesh_pb2.ToRadio()
        startConfig.want_config_id = self.configId
        self._sendToRadio(startConfig)

    def _sendToRadio(self, toRadio):
        """Send a ToRadio protobuf to the device"""
        logging.error(f"Subclass must provide toradio: {toRadio}")

    def _handleFromRadio(self, fromRadioBytes):
        """
        Handle a packet that arrived from the radio (update model and publish events)

        Called by subclasses."""
        fromRadio = mesh_pb2.FromRadio()
        fromRadio.ParseFromString(fromRadioBytes)
        logging.debug(f"Received: {fromRadio}")


class StreamInterface(MeshInterface):
    """Interface class for meshtastic devices over a stream link (serial, TCP, etc)"""

    def __init__(self, devPath):
        """Constructor, opens a connection to a specified serial port"""
        logging.debug(f"Connecting to {devPath}")
        self._rxBuf = bytes()  # empty
        self.stream = serial.Serial(devPath, 921600)
        self._rxThread = threading.Thread(target=self.__reader, args=())
        self._rxThread.start()
        MeshInterface.__init__(self)

    def _sendToRadio(self, toRadio):
        """Send a ToRadio protobuf to the device"""
        logging.debug(f"Sending: {toRadio}")
        b = toRadio.SerializeToString()
        bufLen = len(b)
        header = bytes([START1, START2, (bufLen >> 8) & 0xff,  bufLen & 0xff])
        self.stream.write(header)
        self.stream.write(b)
        self.stream.flush()

    def close(self):
        self.stream.close()  # This will cause our reader thread to exit

    def __reader(self):
        """The reader thread that reads bytes from our stream"""
        empty = bytes()

        while True:
            b = self.stream.read(1)
            c = b[0]
            ptr = len(self._rxBuf)

            # Assume we want to append this byte, fixme use bytearray instead
            self._rxBuf = self._rxBuf + b

            if ptr == 0:  # looking for START1
                if c != START1:
                    self._rxBuf = empty  # failed to find start
                    try:
                        self.debugOut.write(b.decode("utf-8"))
                    except:
                        self.debugOut.write('?')

            elif ptr == 1:  # looking for START2
                if c != START2:
                    self.rfBuf = empty  # failed to find start2
            elif ptr >= HEADER_LEN:  # we've at least got a header
                # big endian length follos header
                packetlen = (self._rxBuf[2] << 8) + self._rxBuf[3]

                if ptr == HEADER_LEN:  # we _just_ finished reading the header, validate length
                    if packetlen > MAX_TO_FROM_RADIO_SIZE:
                        self.rfBuf = empty  # length ws out out bounds, restart

                if len(self._rxBuf) != 0 and ptr + 1 == packetlen + HEADER_LEN:
                    self._handleFromRadio(self._rxBuf[HEADER_LEN:])
                    self._rxBuf = empty
