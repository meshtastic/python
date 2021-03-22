"""
# an API for Meshtastic devices

Primary class: SerialInterface
Install with pip: "[pip3 install meshtastic](https://pypi.org/project/meshtastic/)"
Source code on [github](https://github.com/meshtastic/Meshtastic-python)

properties of SerialInterface:

- radioConfig - Current radio configuration and device settings, if you write to this the new settings will be applied to
the device.
- nodes - The database of received nodes.  Includes always up-to-date location and username information for each
node in the mesh.  This is a read-only datastructure.
- nodesByNum - like "nodes" but keyed by nodeNum instead of nodeId
- myInfo - Contains read-only information about the local radio device (software version, hardware version, etc)

# Published PubSub topics

We use a [publish-subscribe](https://pypubsub.readthedocs.io/en/v4.0.3/) model to communicate asynchronous events.  Available
topics:

- meshtastic.connection.established - published once we've successfully connected to the radio and downloaded the node DB
- meshtastic.connection.lost - published once we've lost our link to the radio
- meshtastic.receive.text(packet) - delivers a received packet as a dictionary, if you only care about a particular
type of packet, you should subscribe to the full topic name.  If you want to see all packets, simply subscribe to "meshtastic.receive".
- meshtastic.receive.position(packet)
- meshtastic.receive.user(packet)
- meshtastic.receive.data.portnum(packet) (where portnum is an integer or well known PortNum enum)
- meshtastic.node.updated(node = NodeInfo) - published when a node in the DB changes (appears, location changed, username changed, etc...)

We receive position, user, or data packets from the mesh.  You probably only care about meshtastic.receive.data.  The first argument for 
that publish will be the packet.  Text or binary data packets (from sendData or sendText) will both arrive this way.  If you print packet 
you'll see the fields in the dictionary.  decoded.data.payload will contain the raw bytes that were sent.  If the packet was sent with 
sendText, decoded.data.text will **also** be populated with the decoded string.  For ASCII these two strings will be the same, but for 
unicode scripts they can be different.

# Example Usage
```
import meshtastic
from pubsub import pub

def onReceive(packet, interface): # called when a packet arrives
    print(f"Received: {packet}")

def onConnection(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    # defaults to broadcast, specify a destination ID if you wish
    interface.sendText("hello mesh")

pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")
# By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface = meshtastic.SerialInterface()

```

"""

import pygatt
import google.protobuf.json_format
import serial
import threading
import logging
import sys
import random
import traceback
import time
import base64
import platform
import socket
from . import mesh_pb2, portnums_pb2, apponly_pb2, admin_pb2, environmental_measurement_pb2, remote_hardware_pb2, channel_pb2, radioconfig_pb2, util
from .util import fixme, catchAndIgnore, stripnl, DeferredExecution
from pubsub import pub
from dotmap import DotMap
from typing import *
from google.protobuf.json_format import MessageToJson

START1 = 0x94
START2 = 0xc3
HEADER_LEN = 4
MAX_TO_FROM_RADIO_SIZE = 512
defaultHopLimit = 3

"""A special ID that means broadcast"""
BROADCAST_ADDR = "^all"

"""A special ID that means the local node"""
LOCAL_ADDR = "^local"

# if using 8 bit nodenums this will be shortend on the target
BROADCAST_NUM = 0xffffffff

"""The numeric buildnumber (shared with android apps) specifying the level of device code we are guaranteed to understand

format is Mmmss (where M is 1+the numeric major number. i.e. 20120 means 1.1.20
"""
OUR_APP_VERSION = 20200

publishingThread = DeferredExecution("publishing")

class ResponseHandler(NamedTuple):
    """A pending response callback, waiting for a response to one of our messages"""
    # requestId: int - used only as a key
    callback: Callable
    # FIXME, add timestamp and age out old requests


class KnownProtocol(NamedTuple):
    """Used to automatically decode known protocol payloads"""
    name: str
    # portnum: int, now a key
    # If set, will be called to prase as a protocol buffer
    protobufFactory: Callable = None
    # If set, invoked as onReceive(interface, packet)
    onReceive: Callable = None


def waitForSet(target, sleep=.1, maxsecs=20, attrs=()):
    """Block until the specified attributes are set. Returns True if config has been received."""
    for _ in range(int(maxsecs/sleep)):
        if all(map(lambda a: getattr(target, a, None), attrs)):
            return True
        time.sleep(sleep)
    return False


def pskToString(psk: bytes):
    """Given an array of PSK bytes, decode them into a human readable (but privacy protecting) string"""
    if len(psk) == 0:
        return "unencrypted"
    elif len(psk) == 1: 
        b = psk[0]
        if b == 0:
            return "unencrypted"
        elif b == 1:
            return "default"
        else:
            return f"simple{b - 1}"
    else:
        return "secret"

class Node:
    """A model of a (local or remote) node in the mesh

    Includes methods for radioConfig and channels
    """

    def __init__(self, iface, nodeNum):
        """Constructor"""
        self.iface = iface
        self.nodeNum = nodeNum
        self.radioConfig = None
        self.channels = None

    def showChannels(self):
        """Show human readable description of our channels"""
        print("Channels:")
        for c in self.channels:
            if c.role != channel_pb2.Channel.Role.DISABLED:
                cStr = stripnl(MessageToJson(c.settings))
                print(f"  {channel_pb2.Channel.Role.Name(c.role)} psk={pskToString(c.settings.psk)} {cStr}")
        publicURL = self.getURL(includeAll = False)
        adminURL = self.getURL(includeAll = True)
        print(f"\nPrimary channel URL: {publicURL}")
        if adminURL != publicURL:
            print(f"Complete URL (includes all channels): {adminURL}")

    def showInfo(self):
        """Show human readable description of our node"""
        print(f"Preferences: {stripnl(MessageToJson(self.radioConfig.preferences))}\n")
        self.showChannels()


    def requestConfig(self):
        """
        Send regular MeshPackets to ask for settings and channels
        """
        self.radioConfig = None
        self.channels = None
        self.partialChannels = []  # We keep our channels in a temp array until finished

        self._requestSettings()

    def waitForConfig(self, maxsecs=20):
        """Block until radio config is received. Returns True if config has been received."""
        return waitForSet(self, attrs=('radioConfig', 'channels'), maxsecs=maxsecs)

    def writeConfig(self):
        """Write the current (edited) radioConfig to the device"""
        if self.radioConfig == None:
            raise Exception("No RadioConfig has been read")

        p = admin_pb2.AdminMessage()
        p.set_radio.CopyFrom(self.radioConfig)

        self._sendAdmin(p)
        logging.debug("Wrote config")

    def writeChannel(self, channelIndex, adminIndex = 0):
        """Write the current (edited) channel to the device"""

        p = admin_pb2.AdminMessage()
        p.set_channel.CopyFrom(self.channels[channelIndex])

        self._sendAdmin(p, adminIndex=adminIndex)
        logging.debug("Wrote channel {channelIndex}")

    def deleteChannel(self, channelIndex):
        """Delete the specifed channelIndex and shift other channels up"""
        ch = self.channels[channelIndex]
        if ch.role != channel_pb2.Channel.Role.SECONDARY:
            raise Exception("Only SECONDARY channels can be deleted")

        # we are careful here because if we move the "admin" channel the channelIndex we need to use
        # for sending admin channels will also change
        adminIndex = self.iface.localNode._getAdminChannelIndex()

        self.channels.pop(channelIndex)
        self._fixupChannels() # expand back to 8 channels

        index = channelIndex
        while index < self.iface.myInfo.max_channels:
            self.writeChannel(index, adminIndex=adminIndex)
            index += 1

            # if we are updating the local node, we might end up *moving* the admin channel index as we are writing
            if (self.iface.localNode == self) and index >= adminIndex:
                adminIndex = 0 # We've now passed the old location for admin index (and writen it), so we can start finding it by name again

    def getChannelByName(self, name):
        """Try to find the named channel or return None"""
        for c in (self.channels or []):
            if c.settings and c.settings.name == name:
                return c
        return None

    def getDisabledChannel(self):
        """Return the first channel that is disabled (i.e. available for some new use)"""
        for c in self.channels:
            if c.role == channel_pb2.Channel.Role.DISABLED:
                return c
        return None

    def _getAdminChannelIndex(self):
        """Return the channel number of the admin channel, or 0 if no reserved channel"""
        c = self.getChannelByName("admin")
        if c:
            return c.index
        else:
            return 0

    def setOwner(self, long_name, short_name=None):
        """Set device owner name"""
        nChars = 3
        minChars = 2
        if long_name is not None:
            long_name = long_name.strip()
            if short_name is None:
                words = long_name.split()
                if len(long_name) <= nChars:
                    short_name = long_name
                elif len(words) >= minChars:
                    short_name = ''.join(map(lambda word: word[0], words))
                else:
                    trans = str.maketrans(dict.fromkeys('aeiouAEIOU'))
                    short_name = long_name[0] + long_name[1:].translate(trans)
                    if len(short_name) < nChars:
                        short_name = long_name[:nChars]

        p = admin_pb2.AdminMessage()

        if long_name is not None:
            p.set_owner.long_name = long_name
        if short_name is not None:
            short_name = short_name.strip()
            if len(short_name) > nChars:
                short_name = short_name[:nChars]
            p.set_owner.short_name = short_name

        return self._sendAdmin(p)

    def getURL(self, includeAll: bool = True):
        """The sharable URL that describes the current channel
        """
        # Only keep the primary/secondary channels, assume primary is first
        channelSet = apponly_pb2.ChannelSet()
        for c in self.channels:
            if c.role == channel_pb2.Channel.Role.PRIMARY or (includeAll and c.role == channel_pb2.Channel.Role.SECONDARY):
                channelSet.settings.append(c.settings)
        bytes = channelSet.SerializeToString()
        s = base64.urlsafe_b64encode(bytes).decode('ascii')
        return f"https://www.meshtastic.org/d/#{s}".replace("=", "")

    def setURL(self, url):
        """Set mesh network URL"""
        if self.radioConfig == None:
            raise Exception("No RadioConfig has been read")

        # URLs are of the form https://www.meshtastic.org/d/#{base64_channel_set}
        # Split on '/#' to find the base64 encoded channel settings
        splitURL = url.split("/#")
        b64 = splitURL[-1]

        # We normally strip padding to make for a shorter URL, but the python parser doesn't like
        # that.  So add back any missing padding
        # per https://stackoverflow.com/a/9807138
        missing_padding = len(b64) % 4
        if missing_padding:
            b64 += '=' * (4 - missing_padding)

        decodedURL = base64.urlsafe_b64decode(b64)
        channelSet = apponly_pb2.ChannelSet()
        channelSet.ParseFromString(decodedURL)

        i = 0
        for chs in channelSet.settings:
            ch = channel_pb2.Channel()
            ch.role = channel_pb2.Channel.Role.PRIMARY if i == 0 else channel_pb2.Channel.Role.SECONDARY
            ch.index = i
            ch.settings.CopyFrom(chs)
            self.channels[ch.index] = ch
            self.writeChannel(ch.index)
            i = i + 1

    def _requestSettings(self):
        """
        Done with initial config messages, now send regular MeshPackets to ask for settings
        """
        p = admin_pb2.AdminMessage()
        p.get_radio_request = True

        def onResponse(p):
            """A closure to handle the response packet"""
            self.radioConfig = p["decoded"]["admin"]["raw"].get_radio_response
            logging.debug("Received radio config, now fetching channels...")
            self._requestChannel(0) # now start fetching channels

        return self._sendAdmin(p,
                               wantResponse=True,
                               onResponse=onResponse)

    def exitSimulator(self):
        """
        Tell a simulator node to exit (this message is ignored for other nodes)
        """
        p = admin_pb2.AdminMessage()
        p.exit_simulator = True

        return self._sendAdmin(p)                               

    def _fixupChannels(self):
        """Fixup indexes and add disabled channels as needed"""

        # Add extra disabled channels as needed
        for index, ch in enumerate(self.channels):
            ch.index = index # fixup indexes

        self._fillChannels()

    def _fillChannels(self):
        """Mark unused channels as disabled"""

        # Add extra disabled channels as needed
        index = len(self.channels)
        while index < self.iface.myInfo.max_channels:
            ch = channel_pb2.Channel()
            ch.role = channel_pb2.Channel.Role.DISABLED
            ch.index = index
            self.channels.append(ch)
            index += 1

    def _requestChannel(self, channelNum: int):
        """
        Done with initial config messages, now send regular MeshPackets to ask for settings
        """
        p = admin_pb2.AdminMessage()
        p.get_channel_request = channelNum + 1
        logging.debug(f"Requesting channel {channelNum}")

        def onResponse(p):
            """A closure to handle the response packet"""
            c = p["decoded"]["admin"]["raw"].get_channel_response
            self.partialChannels.append(c)
            logging.debug(f"Received channel {stripnl(c)}")
            index = c.index

            # for stress testing, we can always download all channels
            fastChannelDownload = True

            # Once we see a response that has NO settings, assume we are at the end of channels and stop fetching
            quitEarly = (
                c.role == channel_pb2.Channel.Role.DISABLED) and fastChannelDownload

            if quitEarly or index >= self.iface.myInfo.max_channels - 1:
                logging.debug("Finished downloading channels")

                self.channels = self.partialChannels
                self._fixupChannels()

                # FIXME, the following should only be called after we have settings and channels
                self.iface._connected()  # Tell everone else we are ready to go
            else:
                self._requestChannel(index + 1)

        return self._sendAdmin(p,
                               wantResponse=True,
                               onResponse=onResponse)

    def _sendAdmin(self, p: admin_pb2.AdminMessage, wantResponse=False,
                   onResponse=None, 
                   adminIndex=0):
        """Send an admin message to the specified node (or the local node if destNodeNum is zero)"""

        if adminIndex == 0: # unless a special channel index was used, we want to use the admin index
            adminIndex = self.iface.localNode._getAdminChannelIndex()

        return self.iface.sendData(p, self.nodeNum,
                                   portNum=portnums_pb2.PortNum.ADMIN_APP,
                                   wantAck=True,
                                   wantResponse=wantResponse,
                                   onResponse=onResponse,
                                   channelIndex=adminIndex)


class MeshInterface:
    """Interface class for meshtastic devices

    Properties:

    isConnected
    nodes
    debugOut
    """

    def __init__(self, debugOut=None, noProto=False):
        """Constructor

        Keyword Arguments:
            noProto -- If True, don't try to run our protocol on the link - just be a dumb serial client.
        """
        self.debugOut = debugOut
        self.nodes = None  # FIXME
        self.isConnected = threading.Event()
        self.noProto = noProto
        self.localNode = Node(self, -1)  # We fixup nodenum later
        self.myInfo = None  # We don't have device info yet
        self.responseHandlers = {}  # A map from request ID to the handler
        self.failure = None  # If we've encountered a fatal exception it will be kept here
        random.seed()  # FIXME, we should not clobber the random seedval here, instead tell user they must call it
        self.currentPacketId = random.randint(0, 0xffffffff)
        self._startConfig()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None and exc_value is not None:
            logging.error(
                f'An exception of type {exc_type} with value {exc_value} has occurred')
        if traceback is not None:
            logging.error(f'Traceback: {traceback}')
        self.close()

    def showInfo(self):
        """Show human readable summary about this object"""
        print(f"My info: {stripnl(MessageToJson(self.myInfo))}")
        print("\nNodes in mesh:")
        for n in self.nodes.values():
            print("  " + stripnl(n))

    def getNode(self, nodeId):
        """Return a node object which contains device settings and channel info"""
        if nodeId == LOCAL_ADDR:
            return self.localNode
        else:
            logging.info("Requesting configuration from remote node (this could take a while)")
            n = Node(self, nodeId)
            n.requestConfig()
            if not n.waitForConfig(maxsecs = 60):
                raise Exception("Timed out waiting for node config")
            return n

    def sendText(self, text: AnyStr,
                 destinationId=BROADCAST_ADDR,
                 wantAck=False,
                 wantResponse=False,
                 hopLimit=defaultHopLimit,
                 onResponse=None):
        """Send a utf8 string to some other node, if the node has a display it will also be shown on the device.

        Arguments:
            text {string} -- The text to send

        Keyword Arguments:
            destinationId {nodeId or nodeNum} -- where to send this message (default: {BROADCAST_ADDR})
            portNum -- the application portnum (similar to IP port numbers) of the destination, see portnums.proto for a list
            wantAck -- True if you want the message sent in a reliable manner (with retries and ack/nak provided for delivery)
            wantResponse -- True if you want the service on the other side to send an application layer response

        Returns the sent packet. The id field will be populated in this packet and can be used to track future message acks/naks.
        """
        return self.sendData(text.encode("utf-8"), destinationId,
                             portNum=portnums_pb2.PortNum.TEXT_MESSAGE_APP,
                             wantAck=wantAck,
                             wantResponse=wantResponse,
                             hopLimit=hopLimit,
                             onResponse=onResponse)

    def sendData(self, data, destinationId=BROADCAST_ADDR,
                 portNum=portnums_pb2.PortNum.PRIVATE_APP, wantAck=False,
                 wantResponse=False,
                 hopLimit=defaultHopLimit,
                 onResponse=None,
                 channelIndex=0):
        """Send a data packet to some other node

        Keyword Arguments:
            data -- the data to send, either as an array of bytes or as a protobuf (which will be automatically serialized to bytes)
            destinationId {nodeId or nodeNum} -- where to send this message (default: {BROADCAST_ADDR})
            portNum -- the application portnum (similar to IP port numbers) of the destination, see portnums.proto for a list
            wantAck -- True if you want the message sent in a reliable manner (with retries and ack/nak provided for delivery)
            wantResponse -- True if you want the service on the other side to send an application layer response
            onResponse -- A closure of the form funct(packet), that will be called when a response packet arrives (or the transaction is NAKed due to non receipt)

        Returns the sent packet. The id field will be populated in this packet and can be used to track future message acks/naks.
        """
        if getattr(data, "SerializeToString", None):
            logging.debug(f"Serializing protobuf as data: {stripnl(data)}")
            data = data.SerializeToString()

        if len(data) > mesh_pb2.Constants.DATA_PAYLOAD_LEN:
            raise Exception("Data payload too big")

        if portNum == portnums_pb2.PortNum.UNKNOWN_APP:  # we are now more strict wrt port numbers
            raise Exception("A non-zero port number must be specified")

        meshPacket = mesh_pb2.MeshPacket()
        meshPacket.channel = channelIndex
        meshPacket.decoded.payload = data
        meshPacket.decoded.portnum = portNum
        meshPacket.decoded.want_response = wantResponse

        p = self._sendPacket(meshPacket, destinationId,
                             wantAck=wantAck, hopLimit=hopLimit)
        if onResponse is not None:
            self._addResponseHandler(p.id, onResponse)
        return p

    def sendPosition(self, latitude=0.0, longitude=0.0, altitude=0, timeSec=0, destinationId=BROADCAST_ADDR, wantAck=False, wantResponse=False):
        """
        Send a position packet to some other node (normally a broadcast)

        Also, the device software will notice this packet and use it to automatically set its notion of
        the local position.

        If timeSec is not specified (recommended), we will use the local machine time.

        Returns the sent packet. The id field will be populated in this packet and can be used to track future message acks/naks.
        """
        p = mesh_pb2.Position()
        if(latitude != 0.0):
            p.latitude_i = int(latitude / 1e-7)

        if(longitude != 0.0):
            p.longitude_i = int(longitude / 1e-7)

        if(altitude != 0):
            p.altitude = int(altitude)

        if timeSec == 0:
            timeSec = time.time()  # returns unix timestamp in seconds
        p.time = int(timeSec)

        return self.sendData(p, destinationId,
                             portNum=portnums_pb2.PortNum.POSITION_APP,
                             wantAck=wantAck,
                             wantResponse=wantResponse)

    def _addResponseHandler(self, requestId, callback):
        self.responseHandlers[requestId] = ResponseHandler(callback)

    def _sendPacket(self, meshPacket,
                    destinationId=BROADCAST_ADDR,
                    wantAck=False, hopLimit=defaultHopLimit):
        """Send a MeshPacket to the specified node (or if unspecified, broadcast).
        You probably don't want this - use sendData instead.

        Returns the sent packet. The id field will be populated in this packet and 
        can be used to track future message acks/naks.
        """

        # We allow users to talk to the local node before we've completed the full connection flow...
        if(self.myInfo is not None and destinationId != self.myInfo.my_node_num):
            self._waitConnected()

        toRadio = mesh_pb2.ToRadio()

        if destinationId is None:
            raise Exception("destinationId must not be None")
        elif isinstance(destinationId, int):
            nodeNum = destinationId
        elif destinationId == BROADCAST_ADDR:
            nodeNum = BROADCAST_NUM
        elif destinationId == LOCAL_ADDR:
            nodeNum = self.myInfo.my_node_num
        elif destinationId.startswith("!"): # A simple hex style nodeid - we can parse this without needing the DB
            nodeNum = int(destinationId[1:], 16)
        else:
            node = self.nodes.get(destinationId)
            if not node:
                raise Exception(f"NodeId {destinationId} not found in DB")
            nodeNum = node['num']

        meshPacket.to = nodeNum
        meshPacket.want_ack = wantAck
        meshPacket.hop_limit = hopLimit

        # if the user hasn't set an ID for this packet (likely and recommended), we should pick a new unique ID
        # so the message can be tracked.
        if meshPacket.id == 0:
            meshPacket.id = self._generatePacketId()

        toRadio.packet.CopyFrom(meshPacket)
        #logging.debug(f"Sending packet: {stripnl(meshPacket)}")
        self._sendToRadio(toRadio)
        return meshPacket

    def waitForConfig(self):
        """Block until radio config is received. Returns True if config has been received."""
        success = waitForSet(self, attrs=('myInfo', 'nodes')) and self.localNode.waitForConfig()
        if not success:
            raise Exception("Timed out waiting for interface config")

    def getMyNodeInfo(self):
        if self.myInfo is None:
            return None
        return self.nodesByNum.get(self.myInfo.my_node_num)

    def getMyUser(self):
        nodeInfo = self.getMyNodeInfo()
        if nodeInfo is not None:
            return nodeInfo.get('user')
        return None

    def getLongName(self):
        user = self.getMyUser()
        if user is not None:
            return user.get('longName', None)
        return None

    def getShortName(self):
        user = self.getMyUser()
        if user is not None:
            return user.get('shortName', None)
        return None

    def _waitConnected(self):
        """Block until the initial node db download is complete, or timeout
        and raise an exception"""
        if not self.isConnected.wait(5.0):  # timeout after 5 seconds
            raise Exception("Timed out waiting for connection completion")

        # If we failed while connecting, raise the connection to the client
        if self.failure:
            raise self.failure

    def _generatePacketId(self):
        """Get a new unique packet ID"""
        if self.currentPacketId is None:
            raise Exception("Not connected yet, can not generate packet")
        else:
            self.currentPacketId = (self.currentPacketId + 1) & 0xffffffff
            return self.currentPacketId

    def _disconnected(self):
        """Called by subclasses to tell clients this interface has disconnected"""
        self.isConnected.clear()
        publishingThread.queueWork(lambda: pub.sendMessage(
            "meshtastic.connection.lost", interface=self))

    def _connected(self):
        """Called by this class to tell clients we are now fully connected to a node
        """
        # (because I'm lazy) _connected might be called when remote Node
        # objects complete their config reads, don't generate redundant isConnected
        # for the local interface
        if not self.isConnected.is_set():
            self.isConnected.set()
            publishingThread.queueWork(lambda: pub.sendMessage(
                "meshtastic.connection.established", interface=self))

    def _startConfig(self):
        """Start device packets flowing"""
        self.myInfo = None
        self.nodes = {}  # nodes keyed by ID
        self.nodesByNum = {}  # nodes keyed by nodenum

        startConfig = mesh_pb2.ToRadio()
        self.configId = random.randint(0, 0xffffffff)
        startConfig.want_config_id = self.configId  
        self._sendToRadio(startConfig)

    def _sendToRadio(self, toRadio):
        """Send a ToRadio protobuf to the device"""
        if self.noProto:
            logging.warn(
                f"Not sending packet because protocol use is disabled by noProto")
        else:
            #logging.debug(f"Sending toRadio: {stripnl(toRadio)}")
            self._sendToRadioImpl(toRadio)

    def _sendToRadioImpl(self, toRadio):
        """Send a ToRadio protobuf to the device"""
        logging.error(f"Subclass must provide toradio: {toRadio}")

    def _handleConfigComplete(self):
        """
        Done with initial config messages, now send regular MeshPackets to ask for settings and channels
        """
        self.localNode.requestConfig()

    def _handleFromRadio(self, fromRadioBytes):
        """
        Handle a packet that arrived from the radio(update model and publish events)

        Called by subclasses."""
        fromRadio = mesh_pb2.FromRadio()
        fromRadio.ParseFromString(fromRadioBytes)
        asDict = google.protobuf.json_format.MessageToDict(fromRadio)
        # logging.debug(f"Received from radio: {fromRadio}")
        if fromRadio.HasField("my_info"):
            self.myInfo = fromRadio.my_info
            self.localNode.nodeNum = self.myInfo.my_node_num
            logging.debug(f"Received myinfo: {stripnl(fromRadio.my_info)}")

            failmsg = None
            # Check for app too old
            if self.myInfo.min_app_version > OUR_APP_VERSION:
                failmsg = "This device needs a newer python client, please \"pip install --upgrade meshtastic\".  For more information see https://tinyurl.com/5bjsxu32"

            # check for firmware too old
            if self.myInfo.max_channels == 0:
                failmsg = "This version of meshtastic-python requires device firmware version 1.2 or later. For more information see https://tinyurl.com/5bjsxu32"

            if failmsg:
                self.failure = Exception(failmsg)
                self.isConnected.set()  # let waitConnected return this exception
                self.close()

        elif fromRadio.HasField("node_info"):
            node = asDict["nodeInfo"]
            try:
                self._fixupPosition(node["position"])
            except:
                logging.debug("Node without position")

            logging.debug(f"Received nodeinfo: {node}")

            self.nodesByNum[node["num"]] = node
            if "user" in node:  # Some nodes might not have user/ids assigned yet
                self.nodes[node["user"]["id"]] = node
            publishingThread.queueWork(lambda: pub.sendMessage("meshtastic.node.updated",
                            node=node, interface=self))
        elif fromRadio.config_complete_id == self.configId:
            # we ignore the config_complete_id, it is unneeded for our stream API fromRadio.config_complete_id
            logging.debug(f"Config complete ID {self.configId}")
            self._handleConfigComplete()
        elif fromRadio.HasField("packet"):
            self._handlePacketFromRadio(fromRadio.packet)
        elif fromRadio.rebooted:
            # Tell clients the device went away.  Careful not to call the overridden subclass version that closes the serial port
            MeshInterface._disconnected(self)

            self._startConfig()  # redownload the node db etc...
        else:
            logging.debug("Unexpected FromRadio payload")

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
            return self.nodesByNum[num]["user"]["id"]
        except:
            logging.debug(f"Node {num} not found for fromId")
            return None

    def _getOrCreateByNum(self, nodeNum):
        """Given a nodenum find the NodeInfo in the DB (or create if necessary)"""
        if nodeNum == BROADCAST_NUM:
            raise Exception("Can not create/find nodenum by the broadcast num")

        if nodeNum in self.nodesByNum:
            return self.nodesByNum[nodeNum]
        else:
            n = {"num": nodeNum}  # Create a minimial node db entry
            self.nodesByNum[nodeNum] = n
            return n

    def _handlePacketFromRadio(self, meshPacket):
        """Handle a MeshPacket that just arrived from the radio

        Will publish one of the following events:
        - meshtastic.receive.text(packet = MeshPacket dictionary)
        - meshtastic.receive.position(packet = MeshPacket dictionary)
        - meshtastic.receive.user(packet = MeshPacket dictionary)
        - meshtastic.receive.data(packet = MeshPacket dictionary)
        """

        asDict = google.protobuf.json_format.MessageToDict(meshPacket)

        # We normally decompose the payload into a dictionary so that the client
        # doesn't need to understand protobufs.  But advanced clients might
        # want the raw protobuf, so we provide it in "raw"
        asDict["raw"] = meshPacket

        # from might be missing if the nodenum was zero.
        if not "from" in asDict:
            asDict["from"] = 0
            logging.error(
                f"Device returned a packet we sent, ignoring: {stripnl(asDict)}")
            return
        if not "to" in asDict:
            asDict["to"] = 0

        # /add fromId and toId fields based on the node ID
        try:
            asDict["fromId"] = self._nodeNumToId(asDict["from"])
        except Exception as ex:
            logging.warn(f"Not populating fromId {ex}")
        try:            
            asDict["toId"] = self._nodeNumToId(asDict["to"])
        except Exception as ex:
            logging.warn(f"Not populating toId {ex}")

        # We could provide our objects as DotMaps - which work with . notation or as dictionaries
        # asObj = DotMap(asDict)
        topic = "meshtastic.receive"  # Generic unknown packet type

        decoded = asDict["decoded"]
        # The default MessageToDict converts byte arrays into base64 strings.
        # We don't want that - it messes up data payload.  So slam in the correct
        # byte array.
        decoded["payload"] = meshPacket.decoded.payload

        # UNKNOWN_APP is the default protobuf portnum value, and therefore if not set it will not be populated at all
        # to make API usage easier, set it to prevent confusion
        if not "portnum" in decoded:
            decoded["portnum"] = portnums_pb2.PortNum.Name(
                portnums_pb2.PortNum.UNKNOWN_APP)

        portnum = decoded["portnum"]

        topic = f"meshtastic.receive.data.{portnum}"

        # decode position protobufs and update nodedb, provide decoded version as "position" in the published msg
        # move the following into a 'decoders' API that clients could register?
        portNumInt = meshPacket.decoded.portnum  # we want portnum as an int
        handler = protocols.get(portNumInt)
        # The decoded protobuf as a dictionary (if we understand this message)
        p = None
        if handler is not None:
            topic = f"meshtastic.receive.{handler.name}"

            # Convert to protobuf if possible
            if handler.protobufFactory is not None:
                pb = handler.protobufFactory()
                pb.ParseFromString(meshPacket.decoded.payload)
                p = google.protobuf.json_format.MessageToDict(pb)
                asDict["decoded"][handler.name] = p
                # Also provide the protobuf raw
                asDict["decoded"][handler.name]["raw"] = pb

            # Call specialized onReceive if necessary
            if handler.onReceive is not None:
                handler.onReceive(self, asDict)

        # Is this message in response to a request, if so, look for a handler
        requestId = decoded.get("requestId")
        if requestId is not None:
            # We ignore ACK packets, but send NAKs and data responses to the handlers
            routing = decoded.get("routing")
            isAck = routing is not None and ("errorReason" not in routing)
            if not isAck:
                # we keep the responseHandler in dict until we get a non ack
                handler = self.responseHandlers.pop(requestId, None)
                if handler is not None:
                    handler.callback(asDict)

        logging.debug(f"Publishing {topic}: packet={stripnl(asDict)} ")
        publishingThread.queueWork(lambda: pub.sendMessage(
            topic, packet=asDict, interface=self))


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

    def _sendToRadioImpl(self, toRadio):
        """Send a ToRadio protobuf to the device"""
        # logging.debug(f"Sending: {stripnl(toRadio)}")
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

    def __init__(self, debugOut=None, noProto=False, connectNow=True):
        """Constructor, opens a connection to self.stream 

        Keyword Arguments:
            devPath {string} -- A filepath to a device, i.e. /dev/ttyUSB0 (default: {None})
            debugOut {stream} -- If a stream is provided, any debug serial output from the device will be emitted to that stream. (default: {None})

        Raises:
            Exception: [description]
            Exception: [description]
        """

        if not hasattr(self, 'stream'):
            raise Exception(
                "StreamInterface is now abstract (to update existing code create SerialInterface instead)")
        self._rxBuf = bytes()  # empty
        self._wantExit = False

        # FIXME, figure out why daemon=True causes reader thread to exit too early
        self._rxThread = threading.Thread(target=self.__reader, args=())

        MeshInterface.__init__(self, debugOut=debugOut, noProto=noProto)

        # Start the reader thread after superclass constructor completes init
        if connectNow:
            self.connect()
            if not noProto:
                self.waitForConfig()

    def connect(self):
        """Connect to our radio

        Normally this is called automatically by the constructor, but if you passed in connectNow=False you can manually
        start the reading thread later.
        """

        # Send some bogus UART characters to force a sleeping device to wake
        self._writeBytes(bytes([START1, START1, START1, START1]))
        time.sleep(0.1)  # wait 100ms to give device time to start running

        self._rxThread.start()
        if not self.noProto:  # Wait for the db download if using the protocol
            self._waitConnected()

    def _disconnected(self):
        """We override the superclass implementation to close our port"""
        MeshInterface._disconnected(self)

        logging.debug("Closing our port")
        if not self.stream is None:
            self.stream.close()

    def _writeBytes(self, b):
        """Write an array of bytes to our stream and flush"""
        self.stream.write(b)
        self.stream.flush()

    def _readBytes(self, len):
        """Read an array of bytes from our stream"""
        return self.stream.read(len)

    def _sendToRadioImpl(self, toRadio):
        """Send a ToRadio protobuf to the device"""
        logging.debug(f"Sending: {stripnl(toRadio)}")
        b = toRadio.SerializeToString()
        bufLen = len(b)
        # We convert into a string, because the TCP code doesn't work with byte arrays
        header = bytes([START1, START2, (bufLen >> 8) & 0xff,  bufLen & 0xff])
        self._writeBytes(header + b)

    def close(self):
        """Close a connection to the device"""
        logging.debug("Closing stream")
        # pyserial cancel_read doesn't seem to work, therefore we ask the reader thread to close things for us
        self._wantExit = True
        if self._rxThread != threading.current_thread():
            self._rxThread.join()  # wait for it to exit

    def __reader(self):
        """The reader thread that reads bytes from our stream"""
        empty = bytes()

        try:
            while not self._wantExit:
                # logging.debug("reading character")
                b = self._readBytes(1)
                # logging.debug("In reader loop")
                # logging.debug(f"read returned {b}")
                if len(b) > 0:
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
                            self._rxBuf = empty  # failed to find start2
                    elif ptr >= HEADER_LEN:  # we've at least got a header
                        # big endian length follos header
                        packetlen = (self._rxBuf[2] << 8) + self._rxBuf[3]

                        if ptr == HEADER_LEN:  # we _just_ finished reading the header, validate length
                            if packetlen > MAX_TO_FROM_RADIO_SIZE:
                                self._rxBuf = empty  # length ws out out bounds, restart

                        if len(self._rxBuf) != 0 and ptr + 1 == packetlen + HEADER_LEN:
                            try:
                                self._handleFromRadio(self._rxBuf[HEADER_LEN:])
                            except Exception as ex:
                                logging.error(
                                    f"Error while handling message from radio {ex}")
                                traceback.print_exc()
                            self._rxBuf = empty
                else:
                    # logging.debug(f"timeout")
                    pass
        except serial.SerialException as ex:
            if not self._wantExit:  # We might intentionally get an exception during shutdown
                logging.warn(
                    f"Meshtastic serial port disconnected, disconnecting... {ex}")
        except OSError as ex:
            if not self._wantExit:  # We might intentionally get an exception during shutdown
                logging.error(
                    f"Unexpected OSError, terminating meshtastic reader... {ex}")
        except Exception as ex:
            logging.error(
                f"Unexpected exception, terminating meshtastic reader... {ex}")
        finally:
            logging.debug("reader is exiting")
            self._disconnected()


class SerialInterface(StreamInterface):
    """Interface class for meshtastic devices over a serial link"""

    def __init__(self, devPath=None, debugOut=None, noProto=False, connectNow=True):
        """Constructor, opens a connection to a specified serial port, or if unspecified try to
        find one Meshtastic device by probing

        Keyword Arguments:
            devPath {string} -- A filepath to a device, i.e. /dev/ttyUSB0 (default: {None})
            debugOut {stream} -- If a stream is provided, any debug serial output from the device will be emitted to that stream. (default: {None})
        """

        if devPath is None:
            ports = util.findPorts()
            if len(ports) == 0:
                raise Exception("No Meshtastic devices detected")
            elif len(ports) > 1:
                raise Exception(
                    f"Multiple ports detected, you must specify a device, such as {ports[0]}")
            else:
                devPath = ports[0]

        logging.debug(f"Connecting to {devPath}")

        # Note: we provide None for port here, because we will be opening it later
        self.stream = serial.Serial(
            None, 921600, exclusive=True, timeout=0.5)

        # rts=False Needed to prevent TBEAMs resetting on OSX, because rts is connected to reset
        self.stream.port = devPath
        # OS-X/Windows seems to have a bug in its serial driver.  It ignores that we asked for no RTSCTS
        # control and will always drive RTS either high or low (rather than letting the CP102 leave
        # it as an open-collector floating pin).  Since it is going to drive it anyways we want to make
        # sure it is driven low, so that the TBEAM won't reset
        # Linux does this properly, so don't apply this hack (because it makes the reset button not work)
        if platform.system() != 'Linux':
            self.stream.rts = False
        self.stream.open()

        StreamInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, connectNow=connectNow)


class TCPInterface(StreamInterface):
    """Interface class for meshtastic devices over a TCP link"""

    def __init__(self, hostname: AnyStr, debugOut=None, noProto=False, connectNow=True, portNumber=4403):
        """Constructor, opens a connection to a specified IP address/hostname

        Keyword Arguments:
            hostname {string} -- Hostname/IP address of the device to connect to
        """

        logging.debug(f"Connecting to {hostname}")

        server_address = (hostname, portNumber)
        sock = socket.create_connection(server_address)

        # Instead of wrapping as a stream, we use the native socket API
        # self.stream = sock.makefile('rw')
        self.stream = None
        self.socket = sock

        StreamInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, connectNow=connectNow)

    def close(self):
        """Close a connection to the device"""
        logging.debug("Closing TCP stream")
        # Sometimes the socket read might be blocked in the reader thread.  Therefore we force the shutdown by closing
        # the socket here
        self._wantExit = True
        if not self.socket is None:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        StreamInterface.close(self)

    def _writeBytes(self, b):
        """Write an array of bytes to our stream and flush"""
        self.socket.send(b)

    def _readBytes(self, len):
        """Read an array of bytes from our stream"""
        return self.socket.recv(len)


def _onTextReceive(iface, asDict):
    """Special text auto parsing for received messages"""
    # We don't throw if the utf8 is invalid in the text message.  Instead we just don't populate
    # the decoded.data.text and we log an error message.  This at least allows some delivery to
    # the app and the app can deal with the missing decoded representation.
    #
    # Usually btw this problem is caused by apps sending binary data but setting the payload type to
    # text.
    try:
        asBytes = asDict["decoded"]["payload"]
        asDict["decoded"]["text"] = asBytes.decode("utf-8")
    except Exception as ex:
        logging.error(f"Malformatted utf8 in text message: {ex}")


def _onPositionReceive(iface, asDict):
    """Special auto parsing for received messages"""
    p = asDict["decoded"]["position"]
    iface._fixupPosition(p)
    # update node DB as needed
    iface._getOrCreateByNum(asDict["from"])["position"] = p


def _onNodeInfoReceive(iface, asDict):
    """Special auto parsing for received messages"""
    p = asDict["decoded"]["user"]
    # decode user protobufs and update nodedb, provide decoded version as "position" in the published msg
    # update node DB as needed
    n = iface._getOrCreateByNum(asDict["from"])
    n["user"] = p
    # We now have a node ID, make sure it is uptodate in that table
    iface.nodes[p["id"]] = n


"""Well known message payloads can register decoders for automatic protobuf parsing"""
protocols = {
    portnums_pb2.PortNum.TEXT_MESSAGE_APP: KnownProtocol("text", onReceive=_onTextReceive),
    portnums_pb2.PortNum.POSITION_APP: KnownProtocol("position", mesh_pb2.Position, _onPositionReceive),
    portnums_pb2.PortNum.NODEINFO_APP: KnownProtocol("user", mesh_pb2.User, _onNodeInfoReceive),
    portnums_pb2.PortNum.ADMIN_APP: KnownProtocol("admin", admin_pb2.AdminMessage),
    portnums_pb2.PortNum.ROUTING_APP: KnownProtocol("routing", mesh_pb2.Routing),
    portnums_pb2.PortNum.ENVIRONMENTAL_MEASUREMENT_APP: KnownProtocol("environmental", environmental_measurement_pb2.EnvironmentalMeasurement),
    portnums_pb2.PortNum.REMOTE_HARDWARE_APP: KnownProtocol(
        "remotehw", remote_hardware_pb2.HardwareMessage)
}
