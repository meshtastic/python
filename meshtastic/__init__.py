"""
# an API for Meshtastic devices

Primary class: StreamInterface
Install with pip: "[pip3 install meshtastic](https://pypi.org/project/meshtastic/)"
Source code on [github](https://github.com/meshtastic/Meshtastic-python)

properties of StreamInterface:

- radioConfig - Current radio configuration and device settings, if you write to this the new settings will be applied to
the device.
- nodes - The database of received nodes.  Includes always up-to-date location and username information for each
node in the mesh.  This is a read-only datastructure.
- myNodeInfo - Contains read-only information about the local radio device (software version, hardware version, etc)

# Published PubSub topics

We use a [publish-subscribe](https://pypubsub.readthedocs.io/en/v4.0.3/) model to communicate asynchronous events.  Available
topics:

- meshtastic.connection.established - published once we've successfully connected to the radio and downloaded the node DB
- meshtastic.connection.lost - published once we've lost our link to the radio
- meshtastic.receive.position(packet) - delivers a received packet as a dictionary, if you only care about a particular
type of packet, you should subscribe to the full topic name.  If you want to see all packets, simply subscribe to "meshtastic.receive".
- meshtastic.receive.user(packet)
- meshtastic.receive.data(packet)
- meshtastic.node.updated(node = NodeInfo) - published when a node in the DB changes (appears, location changed, username changed, etc...)

# Example Usage
```
import meshtastic
from pubsub import pub

def onReceive(packet): # called when a packet arrives
    print(f"Received: {packet}")

def onConnection(): # called when we (re)connect to the radio
    # defaults to broadcast, specify a destination ID if you wish
    interface.sendText("hello mesh")

pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")
# By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface = meshtastic.StreamInterface()

```

"""

import pygatt
import google.protobuf.json_format
import serial
import threading
import logging
import time
import sys
import traceback
from . import mesh_pb2
from . import util
from pubsub import pub
from dotmap import DotMap

START1 = 0x94
START2 = 0xc3
HEADER_LEN = 4
MAX_TO_FROM_RADIO_SIZE = 512

BROADCAST_ADDR = "^all"  # A special ID that means broadcast

# if using 8 bit nodenums this will be shortend on the target
BROADCAST_NUM = 0xffffffff

MY_CONFIG_ID = 42

"""The numeric buildnumber (shared with android apps) specifying the level of device code we are guaranteed to understand"""
OUR_APP_VERSION = 172


class MeshInterface:
    """Interface class for meshtastic devices

    Properties:

    isConnected
    nodes
    debugOut
    """

    def __init__(self, debugOut=None, noProto=False):
        """Constructor"""
        self.debugOut = debugOut
        self.nodes = None  # FIXME
        self.isConnected = False
        if not noProto:
            self._startConfig()

    def sendText(self, text, destinationId=BROADCAST_ADDR, wantAck=False, wantResponse=False):
        """Send a utf8 string to some other node, if the node has a display it will also be shown on the device.

        Arguments:
            text {string} -- The text to send

        Keyword Arguments:
            destinationId {nodeId or nodeNum} -- where to send this message (default: {BROADCAST_ADDR})
        """
        self.sendData(text.encode("utf-8"), destinationId,
                      dataType=mesh_pb2.Data.CLEAR_TEXT, wantAck=wantAck, wantResponse=wantResponse)

    def sendData(self, byteData, destinationId=BROADCAST_ADDR, dataType=mesh_pb2.Data.OPAQUE, wantAck=False, wantResponse=False):
        """Send a data packet to some other node"""
        meshPacket = mesh_pb2.MeshPacket()
        meshPacket.decoded.data.payload = byteData
        meshPacket.decoded.data.typ = dataType
        meshPacket.decoded.want_response = wantResponse
        self.sendPacket(meshPacket, destinationId, wantAck=wantAck)

    def sendPacket(self, meshPacket, destinationId=BROADCAST_ADDR, wantAck=False):
        """Send a MeshPacket to the specified node (or if unspecified, broadcast).
        You probably don't want this - use sendData instead."""
        toRadio = mesh_pb2.ToRadio()
        # FIXME add support for non broadcast addresses

        if isinstance(destinationId, int):
            nodeNum = destinationId
        elif destinationId == BROADCAST_ADDR:
            nodeNum = BROADCAST_NUM
        else:
            nodeNum = self.nodes[destinationId].num

        meshPacket.to = nodeNum
        meshPacket.want_ack = wantAck
        toRadio.packet.CopyFrom(meshPacket)
        self._sendToRadio(toRadio)

    def writeConfig(self):
        """Write the current (edited) radioConfig to the device"""
        if self.radioConfig == None:
            raise Exception("No RadioConfig has been read")

        t = mesh_pb2.ToRadio()
        t.set_radio.CopyFrom(self.radioConfig)
        self._sendToRadio(t)

    def _disconnected(self):
        """Called by subclasses to tell clients this interface has disconnected"""
        self.isConnected = False
        pub.sendMessage("meshtastic.connection.lost", interface=self)

    def _connected(self):
        """Called by this class to tell clients we are now fully connected to a node
        """
        self.isConnected = True
        pub.sendMessage("meshtastic.connection.established", interface=self)

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
        asDict = google.protobuf.json_format.MessageToDict(fromRadio)
        logging.debug(f"Received: {asDict}")
        if fromRadio.HasField("my_info"):
            self.myInfo = fromRadio.my_info
            if self.myInfo.min_app_version > OUR_APP_VERSION:
                raise Exception(
                    "This device needs a newer python client, please \"pip install --upgrade meshtastic\"")
        elif fromRadio.HasField("radio"):
            self.radioConfig = fromRadio.radio
        elif fromRadio.HasField("node_info"):
            node = asDict["nodeInfo"]
            try:
                self._fixupPosition(node["position"])
            except:
                logging.debug("Node without position")
            self._nodesByNum[node["num"]] = node
            if "user" in node:  # Some nodes might not have user/ids assigned yet
                self.nodes[node["user"]["id"]] = node
        elif fromRadio.config_complete_id == MY_CONFIG_ID:
            # we ignore the config_complete_id, it is unneeded for our stream API fromRadio.config_complete_id
            self._connected()
        elif fromRadio.HasField("packet"):
            self._handlePacketFromRadio(fromRadio.packet)
        elif fromRadio.rebooted:
            self._disconnected()
            self._startConfig()  # redownload the node db etc...
        else:
            logging.warn("Unexpected FromRadio payload")

    def _fixupPosition(self, position):
        """Convert integer lat/lon into floats

        Arguments:
            position {Position dictionary} -- object ot fix up
        """
        if "latitudeI" in position:
            position["latitude"] = position["latitudeI"] * 1e-7
        if "longitudeI" in position:
            position["longitude"] = position["longitudeI"] * 1e-7

    def _nodeNumToId(self, num):
        """Map a node node number to a node ID

        Arguments:
            num {int} -- Node number

        Returns:
            string -- Node ID
        """
        if num == BROADCAST_NUM:
            return BROADCAST_ADDR

        try:
            return self._nodesByNum[num]["user"]["id"]
        except:
            logging.error("Node not found for fromId")
            return None

    def _getOrCreateByNum(self, nodeNum):
        """Given a nodenum find the NodeInfo in the DB (or create if necessary)"""
        if nodeNum == BROADCAST_NUM:
            raise Exception("Can not create/find nodenum by the broadcast num")

        if nodeNum in self._nodesByNum:
            return self._nodesByNum[nodeNum]
        else:
            n = {"num": nodeNum}  # Create a minimial node db entry
            self._nodesByNum[nodeNum] = n
            return n

    def _handlePacketFromRadio(self, meshPacket):
        """Handle a MeshPacket that just arrived from the radio

        Will publish one of the following events:
        - meshtastic.receive.position(packet = MeshPacket dictionary)
        - meshtastic.receive.user(packet = MeshPacket dictionary)
        - meshtastic.receive.data(packet = MeshPacket dictionary)
        """

        asDict = google.protobuf.json_format.MessageToDict(meshPacket)
        # /add fromId and toId fields based on the node ID
        asDict["fromId"] = self._nodeNumToId(asDict["from"])
        asDict["toId"] = self._nodeNumToId(asDict["to"])

        # We could provide our objects as DotMaps - which work with . notation or as dictionaries
        # asObj = DotMap(asDict)
        topic = "meshtastic.receive"  # Generic unknown packet type
        if meshPacket.decoded.HasField("position"):
            topic = "meshtastic.receive.position"
            p = asDict["decoded"]["position"]
            self._fixupPosition(p)
            # update node DB as needed
            self._getOrCreateByNum(asDict["from"])["position"] = p

        if meshPacket.decoded.HasField("user"):
            topic = "meshtastic.receive.user"
            u = asDict["decoded"]["user"]
            # update node DB as needed
            n = self._getOrCreateByNum(asDict["from"])
            n["user"] = u
            # We now have a node ID, make sure it is uptodate in that table
            self.nodes[u["id"]] = u

        if meshPacket.decoded.HasField("data"):
            topic = "meshtastic.receive.data"
            # For text messages, we go ahead and decode the text to ascii for our users
            if asDict["decoded"]["data"]["typ"] == "CLEAR_TEXT":
                asDict["decoded"]["data"]["text"] = meshPacket.decoded.data.payload.decode(
                    "utf-8")

        pub.sendMessage(topic, packet=asDict, interface=self)


# Our standard BLE characteristics
TORADIO_UUID = "f75c76d2-129e-4dad-a1dd-7866124401e7"
FROMRADIO_UUID = "8ba2bcc2-ee02-4a55-a531-c525c5e454d5"
FROMNUM_UUID = "ed9da18c-a800-4f66-a670-aa7547e34453"


class BLEInterface(MeshInterface):
    """A not quite ready - FIXME - BLE interface to devices"""

    def __init__(self, address, debugOut=None):
        self.address = address
        self.adapter = pygatt.GATTToolBackend()  # BGAPIBackend()
        self.adapter.start()
        logging.debug(f"Connecting to {self.address}")
        self.device = self.adapter.connect(address)
        logging.debug("Connected to device")
        # fromradio = self.device.char_read(FROMRADIO_UUID)
        MeshInterface.__init__(self, debugOut=debugOut)

        self._readFromRadio()  # read the initial responses

        def handle_data(handle, data):
            self._handleFromRadio(data)

        self.device.subscribe(FROMNUM_UUID, callback=handle_data)

    def _sendToRadio(self, toRadio):
        """Send a ToRadio protobuf to the device"""
        logging.debug(f"Sending: {toRadio}")
        b = toRadio.SerializeToString()
        self.device.char_write(TORADIO_UUID, b)

    def close(self):
        self.adapter.stop()

    def _readFromRadio(self):
        wasEmpty = False
        while not wasEmpty:
            b = self.device.char_read(FROMRADIO_UUID)
            wasEmpty = len(b) == 0
            if not wasEmpty:
                self._handleFromRadio(b)


class StreamInterface(MeshInterface):
    """Interface class for meshtastic devices over a stream link (serial, TCP, etc)"""

    def __init__(self, devPath=None, debugOut=None, noProto=False):
        """Constructor, opens a connection to a specified serial port, or if unspecified try to
        find one Meshtastic device by probing

        Keyword Arguments:
            devPath {string} -- A filepath to a device, i.e. /dev/ttyUSB0 (default: {None})
            debugOut {stream} -- If a stream is provided, any debug serial output from the device will be emitted to that stream. (default: {None})

        Raises:
            Exception: [description]
            Exception: [description]
        """

        if devPath is None:
            ports = util.findPorts()
            if len(ports) == 0:
                raise Exception("No Meshtastic devices detected")
            elif len(ports) > 1:
                raise Exception(
                    f"Multiple ports detected, you must specify a device, such as {ports[0].device}")
            else:
                devPath = ports[0]

        logging.debug(f"Connecting to {devPath}")
        self.devPath = devPath
        self._rxBuf = bytes()  # empty
        self._wantExit = False
        self.stream = serial.Serial(
            devPath, 921600, exclusive=True, timeout=0.5)
        self._rxThread = threading.Thread(target=self.__reader, args=())

        # Send some bogus UART characters to force a sleeping device to wake
        self.stream.write(bytes([START1, START1, START1, START1]))
        self.stream.flush()
        time.sleep(0.1)  # wait 100ms to give device time to start running

        MeshInterface.__init__(self, debugOut=debugOut, noProto=noProto)

        # Start the reader thread after superclass constructor completes init
        self._rxThread.start()

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
        if self._rxThread != threading.current_thread():
            self._rxThread.join()  # wait for it to exit

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
                        if self.debugOut != None:
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
                            logging.error(
                                f"Error handling FromRadio, possibly corrupted? {ex}")
                            traceback.print_exc()
                        self._rxBuf = empty
            else:
                # logging.debug(f"timeout on {self.devPath}")
                pass
        logging.debug("reader is exiting")
        self.stream.close()
        self._disconnected()
