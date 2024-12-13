"""
# A library for the Meshtastic Client API

Primary interfaces: SerialInterface, TCPInterface, BLEInterface

Install with pip: "[pip3 install meshtastic](https://pypi.org/project/meshtastic/)"

Source code on [github](https://github.com/meshtastic/python)

notable properties of interface classes:

- `nodes` - The database of received nodes.  Includes always up-to-date location and username information for each
node in the mesh.  This is a read-only datastructure.
- `nodesByNum` - like "nodes" but keyed by nodeNum instead of nodeId. As such, includes "unknown" nodes which haven't seen a User packet yet
- `myInfo` & `metadata` - Contain read-only information about the local radio device (software version, hardware version, etc)
- `localNode` - Pointer to a node object for the local node

notable properties of nodes:

- `localConfig` - Current radio settings, can be written to the radio with the `writeConfig` method.
- `moduleConfig` - Current module settings, can be written to the radio with the `writeConfig` method.
- `channels` - The node's channels, keyed by index.

# Published PubSub topics

We use a [publish-subscribe](https://pypubsub.readthedocs.io/en/v4.0.3/) model to communicate asynchronous events.  Available
topics:

- `meshtastic.connection.established` - published once we've successfully connected to the radio and downloaded the node DB
- `meshtastic.connection.lost` - published once we've lost our link to the radio
- `meshtastic.receive.text(packet)` - delivers a received packet as a dictionary, if you only care about a particular
type of packet, you should subscribe to the full topic name.  If you want to see all packets, simply subscribe to "meshtastic.receive".
- `meshtastic.receive.position(packet)`
- `meshtastic.receive.user(packet)`
- `meshtastic.receive.data.portnum(packet)` (where portnum is an integer or well known PortNum enum)
- `meshtastic.node.updated(node = NodeInfo)` - published when a node in the DB changes (appears, location changed, username changed, etc...)
- `meshtastic.log.line(line)` - a raw unparsed log line from the radio

We receive position, user, or data packets from the mesh.  You probably only care about `meshtastic.receive.data`.  The first argument for
that publish will be the packet.  Text or binary data packets (from `sendData` or `sendText`) will both arrive this way.  If you print packet
you'll see the fields in the dictionary.  `decoded.data.payload` will contain the raw bytes that were sent.  If the packet was sent with
`sendText`, `decoded.data.text` will **also** be populated with the decoded string.  For ASCII these two strings will be the same, but for
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
import stat
import sys
import threading
import time
import traceback
from datetime import datetime
from typing import *

import google.protobuf.json_format
import serial # type: ignore[import-untyped]
from google.protobuf.json_format import MessageToJson
from pubsub import pub # type: ignore[import-untyped]
from tabulate import tabulate

from meshtastic.node import Node
from meshtastic.util import DeferredExecution, Timeout, catchAndIgnore, fixme, stripnl

from .protobuf import (
    admin_pb2,
    apponly_pb2,
    channel_pb2,
    config_pb2,
    mesh_pb2,
    mqtt_pb2,
    paxcount_pb2,
    portnums_pb2,
    remote_hardware_pb2,
    storeforward_pb2,
    telemetry_pb2,
    powermon_pb2
)
from . import (
    util,
)

# Note: To follow PEP224, comments should be after the module variable.

LOCAL_ADDR = "^local"
"""A special ID that means the local node"""

BROADCAST_NUM: int = 0xFFFFFFFF
"""if using 8 bit nodenums this will be shortened on the target"""

BROADCAST_ADDR = "^all"
"""A special ID that means broadcast"""

OUR_APP_VERSION: int = 20300
"""The numeric buildnumber (shared with android apps) specifying the
   level of device code we are guaranteed to understand

   format is Mmmss (where M is 1+the numeric major number. i.e. 20120 means 1.1.20
"""

NODELESS_WANT_CONFIG_ID = 69420
"""A special thing to pass for want_config_id that instructs nodes to skip sending nodeinfos other than its own."""

publishingThread = DeferredExecution("publishing")


class ResponseHandler(NamedTuple):
    """A pending response callback, waiting for a response to one of our messages"""

    # requestId: int - used only as a key
    #: a callable to call when a response is received
    callback: Callable
    #: Whether ACKs and NAKs should be passed to this handler
    ackPermitted: bool = False
    # FIXME, add timestamp and age out old requests


class KnownProtocol(NamedTuple):
    """Used to automatically decode known protocol payloads"""

    #: A descriptive name (e.g. "text", "user", "admin")
    name: str
    #: If set, will be called to parse as a protocol buffer
    protobufFactory: Optional[Callable] = None
    #: If set, invoked as onReceive(interface, packet)
    onReceive: Optional[Callable] = None


def _onTextReceive(iface, asDict):
    """Special text auto parsing for received messages"""
    # We don't throw if the utf8 is invalid in the text message.  Instead we just don't populate
    # the decoded.data.text and we log an error message.  This at least allows some delivery to
    # the app and the app can deal with the missing decoded representation.
    #
    # Usually btw this problem is caused by apps sending binary data but setting the payload type to
    # text.
    logging.debug(f"in _onTextReceive() asDict:{asDict}")
    try:
        asBytes = asDict["decoded"]["payload"]
        asDict["decoded"]["text"] = asBytes.decode("utf-8")
    except Exception as ex:
        logging.error(f"Malformatted utf8 in text message: {ex}")
    _receiveInfoUpdate(iface, asDict)


def _onPositionReceive(iface, asDict):
    """Special auto parsing for received messages"""
    logging.debug(f"in _onPositionReceive() asDict:{asDict}")
    if "decoded" in asDict:
        if "position" in asDict["decoded"] and "from" in asDict:
            p = asDict["decoded"]["position"]
            logging.debug(f"p:{p}")
            p = iface._fixupPosition(p)
            logging.debug(f"after fixup p:{p}")
            # update node DB as needed
            iface._getOrCreateByNum(asDict["from"])["position"] = p


def _onNodeInfoReceive(iface, asDict):
    """Special auto parsing for received messages"""
    logging.debug(f"in _onNodeInfoReceive() asDict:{asDict}")
    if "decoded" in asDict:
        if "user" in asDict["decoded"] and "from" in asDict:
            p = asDict["decoded"]["user"]
            # decode user protobufs and update nodedb, provide decoded version as "position" in the published msg
            # update node DB as needed
            n = iface._getOrCreateByNum(asDict["from"])
            n["user"] = p
            # We now have a node ID, make sure it is up-to-date in that table
            iface.nodes[p["id"]] = n
            _receiveInfoUpdate(iface, asDict)

def _onTelemetryReceive(iface, asDict):
    """Automatically update device metrics on received packets"""
    logging.debug(f"in _onTelemetryReceive() asDict:{asDict}")
    if "from" not in asDict:
        return

    toUpdate = None

    telemetry = asDict.get("decoded", {}).get("telemetry", {})
    node = iface._getOrCreateByNum(asDict["from"])
    if "deviceMetrics" in telemetry:
        toUpdate = "deviceMetrics"
    elif "environmentMetrics" in telemetry:
        toUpdate = "environmentMetrics"
    elif "airQualityMetrics" in telemetry:
        toUpdate = "airQualityMetrics"
    elif "powerMetrics" in telemetry:
        toUpdate = "powerMetrics"
    elif "localStats" in telemetry:
        toUpdate = "localStats"
    else:
        return

    updateObj = telemetry.get(toUpdate)
    newMetrics = node.get(toUpdate, {})
    newMetrics.update(updateObj)
    logging.debug(f"updating {toUpdate} metrics for {asDict['from']} to {newMetrics}")
    node[toUpdate] = newMetrics

def _receiveInfoUpdate(iface, asDict):
    if "from" in asDict:
        iface._getOrCreateByNum(asDict["from"])["lastReceived"] = asDict
        iface._getOrCreateByNum(asDict["from"])["lastHeard"] = asDict.get("rxTime")
        iface._getOrCreateByNum(asDict["from"])["snr"] = asDict.get("rxSnr")
        iface._getOrCreateByNum(asDict["from"])["hopLimit"] = asDict.get("hopLimit")

def _onAdminReceive(iface, asDict):
    """Special auto parsing for received messages"""
    logging.debug(f"in _onAdminReceive() asDict:{asDict}")
    if "decoded" in asDict and "from" in asDict and "admin" in asDict["decoded"]:
        adminMessage = asDict["decoded"]["admin"]["raw"]
        iface._getOrCreateByNum(asDict["from"])["adminSessionPassKey"] = adminMessage.session_passkey

"""Well known message payloads can register decoders for automatic protobuf parsing"""
protocols = {
    portnums_pb2.PortNum.TEXT_MESSAGE_APP: KnownProtocol(
        "text", onReceive=_onTextReceive
    ),
    portnums_pb2.PortNum.RANGE_TEST_APP: KnownProtocol(
        "rangetest", onReceive=_onTextReceive
    ),
    portnums_pb2.PortNum.DETECTION_SENSOR_APP: KnownProtocol(
        "detectionsensor", onReceive=_onTextReceive
    ),

    portnums_pb2.PortNum.POSITION_APP: KnownProtocol(
        "position", mesh_pb2.Position, _onPositionReceive
    ),
    portnums_pb2.PortNum.NODEINFO_APP: KnownProtocol(
        "user", mesh_pb2.User, _onNodeInfoReceive
    ),
    portnums_pb2.PortNum.ADMIN_APP: KnownProtocol(
        "admin", admin_pb2.AdminMessage, _onAdminReceive
    ),
    portnums_pb2.PortNum.ROUTING_APP: KnownProtocol("routing", mesh_pb2.Routing),
    portnums_pb2.PortNum.TELEMETRY_APP: KnownProtocol(
        "telemetry", telemetry_pb2.Telemetry, _onTelemetryReceive
    ),
    portnums_pb2.PortNum.REMOTE_HARDWARE_APP: KnownProtocol(
        "remotehw", remote_hardware_pb2.HardwareMessage
    ),
    portnums_pb2.PortNum.SIMULATOR_APP: KnownProtocol("simulator", mesh_pb2.Compressed),
    portnums_pb2.PortNum.TRACEROUTE_APP: KnownProtocol(
        "traceroute", mesh_pb2.RouteDiscovery
    ),
    portnums_pb2.PortNum.POWERSTRESS_APP: KnownProtocol(
        "powerstress", powermon_pb2.PowerStressMessage
    ),
    portnums_pb2.PortNum.WAYPOINT_APP: KnownProtocol("waypoint", mesh_pb2.Waypoint),
    portnums_pb2.PortNum.PAXCOUNTER_APP: KnownProtocol("paxcounter", paxcount_pb2.Paxcount),
    portnums_pb2.PortNum.STORE_FORWARD_APP: KnownProtocol("storeforward", storeforward_pb2.StoreAndForward),
    portnums_pb2.PortNum.NEIGHBORINFO_APP: KnownProtocol("neighborinfo", mesh_pb2.NeighborInfo),
    portnums_pb2.PortNum.MAP_REPORT_APP: KnownProtocol("mapreport", mqtt_pb2.MapReport),
}
