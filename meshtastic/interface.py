
import serial
import threading
import logging
import sys
import traceback
from . import mesh_pb2

START1 = 0x94
START2 = 0xc3
HEADER_LEN = 4
MAX_TO_FROM_RADIO_SIZE = 512

BROADCAST_ADDR = "all"  # A special ID that means broadcast

"""

TODO:
* use port enumeration to find ports https://pyserial.readthedocs.io/en/latest/shortintro.html


Contains a reader thread that is always trying to read on the serial port.

methods:

- radioConfig - getter/setter syntax: https://www.python-course.eu/python3_properties.php
- nodes - the database of received nodes
- myNodeInfo
- myNodeId

# PubSub topics

Use a pubsub model to communicate events [https://pypubsub.readthedocs.io/en/v4.0.3/ ]

- meshtastic.connection.established - published once we've successfully connected to the radio and downloaded the node DB
- meshtastic.connection.lost - published once we've lost our link to the radio
- meshtastic.receive.position(MeshPacket)
- meshtastic.receive.user(MeshPacket)
- meshtastic.receive.data(MeshPacket)
- meshtastic.node.updated(NodeInfo) - published when a node in the DB changes (appears, location changed, username changed, etc...)
- meshtastic.debug(string)
- meshtastic.send(MeshPacket) - Not yet implemented, instead call sendPacket(...) on MeshInterface

"""

MY_CONFIG_ID = 42


class MeshInterface:
    """Interface class for meshtastic devices"""

    def __init__(self):
        """Constructor"""
        self.debugOut = sys.stdout
        self.nodes = None  # FIXME
        self._startConfig()

    def sendText(self, text, destinationId=BROADCAST_ADDR):
        """Send a utf8 string to some other node, if the node has a display it will also be shown on the device."""
        self.sendData(text.encode("utf-8"), destinationId,
                      dataType=mesh_pb2.Data.CLEAR_TEXT)

    def sendData(self, byteData, destinationId=BROADCAST_ADDR, dataType=mesh_pb2.Data.OPAQUE):
        """Send a data packet to some other node"""
        meshPacket = mesh_pb2.MeshPacket()
        meshPacket.payload.data.payload = byteData
        meshPacket.payload.data.typ = dataType
        self.sendPacket(meshPacket, destinationId)

    def sendPacket(self, meshPacket, destinationId=BROADCAST_ADDR):
        """Send a MeshPacket to the specified node (or if unspecified, broadcast). 
        You probably don't want this - use sendData instead."""
        toRadio = mesh_pb2.ToRadio()
        # FIXME add support for non broadcast addresses
        meshPacket.to = 255
        toRadio.packet.CopyFrom(meshPacket)
        self._sendToRadio(toRadio)

    def _startConfig(self):
        """Start device packets flowing"""
        self.myInfo = None
        self.nodes = {}  # nodes keyed by ID
        self._nodesByNum = {}  # nodes keyed by nodenum
        self.radioConfig = None

        startConfig = mesh_pb2.ToRadio()
        startConfig.want_config_id = MY_CONFIG_ID  # we don't use this value
        self._sendToRadio(startConfig)

    def _sendToRadio(self, toRadio):
        """Send a ToRadio protobuf to the device"""
        logging.error(f"Subclass must provide toradio: {toRadio}")

    def _handleFromRadio(self, fromRadioBytes):
        """
        Handle a packet that arrived from the radio(update model and publish events)

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
        elif fromRadio.config_complete_id == MY_CONFIG_ID:
            # we ignore the config_complete_id, it is unneeded for our stream API fromRadio.config_complete_id
            pass
        else:
            logging.warn("Unexpected FromRadio payload")


class StreamInterface(MeshInterface):
    """Interface class for meshtastic devices over a stream link(serial, TCP, etc)"""

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
                # logging.debug(f"read returned {b}")
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
                        except Exception as ex:
                            logging.warn(
                                f"Error handling FromRadio, possibly corrupted? {ex}")
                            traceback.print_exc()
                        self._rxBuf = empty
        logging.debug("reader is exiting")
        self.stream.close()
