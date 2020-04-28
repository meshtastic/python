
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
        self._startConfig()

    def _startConfig(self):
        """Start device packets flowing"""
        self.myInfo = None
        self.nodes = {}  # nodes keyed by ID
        self._nodesByNum = {}  # nodes keyed by nodenum
        self.radioConfig = None

        startConfig = mesh_pb2.ToRadio()
        startConfig.want_config_id = 42  # we don't use this value
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
        if fromRadio.HasField("my_info"):
            self.myInfo = fromRadio.my_info
        if fromRadio.HasField("radio"):
            self.radioConfig = fromRadio.radio
        elif fromRadio.HasField("node_info"):
            node = fromRadio.node_info
            self._nodesByNum[node.num] = node
            self.nodes[node.user.id] = node
        elif fromRadio.HasField("config_complete_id"):
            # we ignore the config_complete_id, it is unneeded for our stream API fromRadio.config_complete_id
            pass


"""
    // / Tells the phone what our node number is, can be - 1 if we've not yet
    // / joined a mesh.
    // REV2: In the rev 1 API this is in the BLE mynodeinfo characteristic
    MyNodeInfo my_info = 3

    // / One packet is sent for each node in the on radio DB
    // REV2: In the rev1 API this is available in the nodeinfo characteristic
    // starts over with the first node in our DB
    NodeInfo node_info = 4

    // / REV2: In rev1 this was the radio BLE characteristic
    RadioConfig radio = 6

    // / REV2: sent as true once the device has finished sending all of the
    // / responses to want_config
    // / recipient should check if this ID matches our original request nonce, if
    // / not, it means your config responses haven't started yet
    uint32 config_complete_id = 8
"""


class StreamInterface(MeshInterface):
    """Interface class for meshtastic devices over a stream link (serial, TCP, etc)"""

    def __init__(self, devPath):
        """Constructor, opens a connection to a specified serial port"""
        logging.debug(f"Connecting to {devPath}")
        self._rxBuf = bytes()  # empty
        self._wantExit = False
        self.stream = serial.Serial(
            devPath, 921600, exclusive=True, timeout=0.5)
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
        """Close a connection to the device"""
        logging.debug("Closing serial stream")
        # pyserial cancel_read doesn't seem to work, therefore we ask the reader thread to close things for us
        self._wantExit = True

    def __reader(self):
        """The reader thread that reads bytes from our stream"""
        empty = bytes()

        while not self._wantExit:
            b = self.stream.read(1)
            if len(b) > 0:
                #logging.debug(f"read returned {b}")
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
                        try:
                            self._handleFromRadio(self._rxBuf[HEADER_LEN:])
                        except:
                            logging.warn(
                                f"Error handling FromRadio, possibly corrupted?")
                        self._rxBuf = empty
        logging.debug("reader is exiting")
        self.stream.close()
