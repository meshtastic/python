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
import meshtastic.serial_interface
from pubsub import pub

def onReceive(packet, interface): # called when a packet arrives
    print(f"Received: {packet}")

def onConnection(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    # defaults to broadcast, specify a destination ID if you wish
    interface.sendText("hello mesh")

pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")
# By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface = meshtastic.serial_interface.SerialInterface()

```

"""

import base64
import logging
import os
import platform
import random
import socket
import sys
import stat
import threading
import traceback
import time
from datetime import datetime
from typing import *
import serial
import timeago
import google.protobuf.json_format
from pubsub import pub
from dotmap import DotMap
from tabulate import tabulate
from google.protobuf.json_format import MessageToJson
from meshtastic.util import fixme, catchAndIgnore, stripnl, DeferredExecution, Timeout
from meshtastic.node import Node
from meshtastic import (mesh_pb2, portnums_pb2, apponly_pb2, admin_pb2,
                        environmental_measurement_pb2, remote_hardware_pb2,
                        channel_pb2, radioconfig_pb2, util)


# Note: To follow PEP224, comments should be after the module variable.

LOCAL_ADDR = "^local"
"""A special ID that means the local node"""

BROADCAST_NUM = 0xffffffff
"""if using 8 bit nodenums this will be shortend on the target"""

BROADCAST_ADDR = "^all"
"""A special ID that means broadcast"""

OUR_APP_VERSION = 20200
"""The numeric buildnumber (shared with android apps) specifying the
   level of device code we are guaranteed to understand

   format is Mmmss (where M is 1+the numeric major number. i.e. 20120 means 1.1.20
"""

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


def _onTextReceive(iface, asDict):
    """Special text auto parsing for received messages"""
    # We don't throw if the utf8 is invalid in the text message.  Instead we just don't populate
    # the decoded.data.text and we log an error message.  This at least allows some delivery to
    # the app and the app can deal with the missing decoded representation.
    #
    # Usually btw this problem is caused by apps sending binary data but setting the payload type to
    # text.
    logging.debug(f'in _onTextReceive() asDict:{asDict}')
    try:
        asBytes = asDict["decoded"]["payload"]
        asDict["decoded"]["text"] = asBytes.decode("utf-8")
    except Exception as ex:
        logging.error(f"Malformatted utf8 in text message: {ex}")
    _receiveInfoUpdate(iface, asDict)


def _onPositionReceive(iface, asDict):
    """Special auto parsing for received messages"""
    logging.debug(f'in _onPositionReceive() asDict:{asDict}')
    if 'decoded' in asDict:
        if 'position' in asDict['decoded'] and 'from' in asDict:
            p = asDict["decoded"]["position"]
            logging.debug(f'p:{p}')
            p = iface._fixupPosition(p)
            logging.debug(f'after fixup p:{p}')
            # update node DB as needed
            iface._getOrCreateByNum(asDict["from"])["position"] = p


def _onNodeInfoReceive(iface, asDict):
    """Special auto parsing for received messages"""
    logging.debug(f'in _onNodeInfoReceive() asDict:{asDict}')
    if 'decoded' in asDict:
        if 'user' in asDict['decoded'] and 'from' in asDict:
            p = asDict["decoded"]["user"]
            # decode user protobufs and update nodedb, provide decoded version as "position" in the published msg
            # update node DB as needed
            n = iface._getOrCreateByNum(asDict["from"])
            n["user"] = p
            # We now have a node ID, make sure it is uptodate in that table
            iface.nodes[p["id"]] = n
            _receiveInfoUpdate(iface, asDict)


def _receiveInfoUpdate(iface, asDict):
    if "from" in asDict:
        iface._getOrCreateByNum(asDict["from"])["lastReceived"] = asDict
        iface._getOrCreateByNum(asDict["from"])["lastHeard"] = asDict.get("rxTime")
        iface._getOrCreateByNum(asDict["from"])["snr"] = asDict.get("rxSnr")
        iface._getOrCreateByNum(asDict["from"])["hopLimit"] = asDict.get("hopLimit")


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
