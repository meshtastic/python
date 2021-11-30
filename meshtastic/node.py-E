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
from .util import fixme, catchAndIgnore, stripnl, DeferredExecution, Timeout
from pubsub import pub
from dotmap import DotMap
from typing import *
from google.protobuf.json_format import MessageToJson



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
        self._timeout = Timeout(maxSecs=60)

    def showChannels(self):
        """Show human readable description of our channels"""
        print("Channels:")
        for c in self.channels:
            if c.role != channel_pb2.Channel.Role.DISABLED:
                cStr = stripnl(MessageToJson(c.settings))
                print(
                    f"  {channel_pb2.Channel.Role.Name(c.role)} psk={pskToString(c.settings.psk)} {cStr}")
        publicURL = self.getURL(includeAll=False)
        adminURL = self.getURL(includeAll=True)
        print(f"\nPrimary channel URL: {publicURL}")
        if adminURL != publicURL:
            print(f"Complete URL (includes all channels): {adminURL}")

    def showInfo(self):
        """Show human readable description of our node"""
        print(
            f"Preferences: {stripnl(MessageToJson(self.radioConfig.preferences))}\n")
        self.showChannels()

    def requestConfig(self):
        """
        Send regular MeshPackets to ask for settings and channels
        """
        self.radioConfig = None
        self.channels = None
        self.partialChannels = []  # We keep our channels in a temp array until finished

        self._requestSettings()

    def waitForConfig(self):
        """Block until radio config is received. Returns True if config has been received."""
        return self._timeout.waitForSet(self, attrs=('radioConfig', 'channels'))

    def writeConfig(self):
        """Write the current (edited) radioConfig to the device"""
        if self.radioConfig == None:
            raise Exception("No RadioConfig has been read")

        p = admin_pb2.AdminMessage()
        p.set_radio.CopyFrom(self.radioConfig)

        self._sendAdmin(p)
        logging.debug("Wrote config")

    def writeChannel(self, channelIndex, adminIndex=0):
        """Write the current (edited) channel to the device"""

        p = admin_pb2.AdminMessage()
        p.set_channel.CopyFrom(self.channels[channelIndex])

        self._sendAdmin(p, adminIndex=adminIndex)
        logging.debug(f"Wrote channel {channelIndex}")

    def deleteChannel(self, channelIndex):
        """Delete the specifed channelIndex and shift other channels up"""
        ch = self.channels[channelIndex]
        if ch.role != channel_pb2.Channel.Role.SECONDARY:
            raise Exception("Only SECONDARY channels can be deleted")

        # we are careful here because if we move the "admin" channel the channelIndex we need to use
        # for sending admin channels will also change
        adminIndex = self.iface.localNode._getAdminChannelIndex()

        self.channels.pop(channelIndex)
        self._fixupChannels()  # expand back to 8 channels

        index = channelIndex
        while index < self.iface.myInfo.max_channels:
            self.writeChannel(index, adminIndex=adminIndex)
            index += 1

            # if we are updating the local node, we might end up *moving* the admin channel index as we are writing
            if (self.iface.localNode == self) and index >= adminIndex:
                # We've now passed the old location for admin index (and writen it), so we can start finding it by name again
                adminIndex = 0

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

    def setOwner(self, long_name, short_name=None, is_licensed=False):
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
            p.set_owner.is_licensed = is_licensed

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
            self._timeout.reset()  # We made foreward progress
            self._requestChannel(0)  # now start fetching channels

        # Show progress message for super slow operations
        if self != self.iface.localNode:
            logging.info(
                "Requesting preferences from remote node (this could take a while)")

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

    def reboot(self, secs: int = 10):
        """
        Tell the node to reboot
        """
        p = admin_pb2.AdminMessage()
        p.reboot_seconds = secs
        logging.info(f"Telling node to reboot in {secs} seconds")

        return self._sendAdmin(p)

    def _fixupChannels(self):
        """Fixup indexes and add disabled channels as needed"""

        # Add extra disabled channels as needed
        for index, ch in enumerate(self.channels):
            ch.index = index  # fixup indexes

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

        # Show progress message for super slow operations
        if self != self.iface.localNode:
            logging.info(
                f"Requesting channel {channelNum} info from remote node (this could take a while)")
        else:
            logging.debug(f"Requesting channel {channelNum}")

        def onResponse(p):
            """A closure to handle the response packet"""
            c = p["decoded"]["admin"]["raw"].get_channel_response
            self.partialChannels.append(c)
            self._timeout.reset()  # We made foreward progress
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

        if adminIndex == 0:  # unless a special channel index was used, we want to use the admin index
            adminIndex = self.iface.localNode._getAdminChannelIndex()

        return self.iface.sendData(p, self.nodeNum,
                                   portNum=portnums_pb2.PortNum.ADMIN_APP,
                                   wantAck=True,
                                   wantResponse=wantResponse,
                                   onResponse=onResponse,
                                   channelIndex=adminIndex)


