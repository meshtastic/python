"""Mesh Interface class
"""

import collections
import json
import logging
import random
import sys
import threading
import time
from datetime import datetime
from decimal import Decimal

from typing import Any, Callable, Dict, List, Optional, Union

import google.protobuf.json_format
from pubsub import pub # type: ignore[import-untyped]
from tabulate import tabulate

import meshtastic.node

from meshtastic.protobuf import (
    mesh_pb2,
    portnums_pb2,
    telemetry_pb2,
)
from meshtastic import (
    BROADCAST_ADDR,
    BROADCAST_NUM,
    LOCAL_ADDR,
    NODELESS_WANT_CONFIG_ID,
    ResponseHandler,
    protocols,
    publishingThread,
)
from meshtastic.util import (
    Acknowledgment,
    Timeout,
    convert_mac_addr,
    our_exit,
    remove_keys_from_dict,
    stripnl,
    message_to_json,
)


def _timeago(delta_secs: int) -> str:
    """Convert a number of seconds in the past into a short, friendly string
    e.g. "now", "30 sec ago",  "1 hour ago"
    Zero or negative intervals simply return "now"
    """
    intervals = (
        ("year", 60 * 60 * 24 * 365),
        ("month", 60 * 60 * 24 * 30),
        ("day", 60 * 60 * 24),
        ("hour", 60 * 60),
        ("min", 60),
        ("sec", 1),
    )
    for name, interval_duration in intervals:
        if delta_secs < interval_duration:
            continue
        x = delta_secs // interval_duration
        plur = "s" if x > 1 else ""
        return f"{x} {name}{plur} ago"

    return "now"


class MeshInterface: # pylint: disable=R0902
    """Interface class for meshtastic devices

    Properties:

    isConnected
    nodes
    debugOut
    """

    class MeshInterfaceError(Exception):
        """An exception class for general mesh interface errors"""
        def __init__(self, message):
            self.message = message
            super().__init__(self.message)

    def __init__(self, debugOut=None, noProto: bool=False, noNodes: bool=False) -> None:
        """Constructor

        Keyword Arguments:
            noProto -- If True, don't try to run our protocol on the
                       link - just be a dumb serial client.
            noNodes -- If True, instruct the node to not send its nodedb
                       on startup, just other configuration information.
        """
        self.debugOut = debugOut
        self.nodes: Optional[Dict[str,Dict]] = None  # FIXME
        self.isConnected: threading.Event = threading.Event()
        self.noProto: bool = noProto
        self.localNode: meshtastic.node.Node = meshtastic.node.Node(self, -1)  # We fixup nodenum later
        self.myInfo: Optional[mesh_pb2.MyNodeInfo] = None  # We don't have device info yet
        self.metadata: Optional[mesh_pb2.DeviceMetadata] = None  # We don't have device metadata yet
        self.responseHandlers: Dict[int,ResponseHandler] = {}  # A map from request ID to the handler
        self.failure = (
            None  # If we've encountered a fatal exception it will be kept here
        )
        self._timeout: Timeout = Timeout()
        self._acknowledgment: Acknowledgment = Acknowledgment()
        self.heartbeatTimer: Optional[threading.Timer] = None
        random.seed()  # FIXME, we should not clobber the random seedval here, instead tell user they must call it
        self.currentPacketId: int = random.randint(0, 0xFFFFFFFF)
        self.nodesByNum: Optional[Dict[int, Dict]] = None
        self.noNodes: bool = noNodes
        self.configId: Optional[int] = NODELESS_WANT_CONFIG_ID if noNodes else None
        self.gotResponse: bool = False  # used in gpio read
        self.mask: Optional[int] = None  # used in gpio read and gpio watch
        self.queueStatus: Optional[mesh_pb2.QueueStatus] = None
        self.queue: collections.OrderedDict = collections.OrderedDict()
        self._localChannels = None

    def close(self):
        """Shutdown this interface"""
        if self.heartbeatTimer:
            self.heartbeatTimer.cancel()

        self._sendDisconnect()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None and exc_value is not None:
            logging.error(
                f"An exception of type {exc_type} with value {exc_value} has occurred"
            )
        if traceback is not None:
            logging.error(f"Traceback: {traceback}")
        self.close()

    def showInfo(self, file=sys.stdout) -> str:  # pylint: disable=W0613
        """Show human readable summary about this object"""
        owner = f"Owner: {self.getLongName()} ({self.getShortName()})"
        myinfo = ""
        if self.myInfo:
            myinfo = f"\nMy info: {message_to_json(self.myInfo)}"
        metadata = ""
        if self.metadata:
            metadata = f"\nMetadata: {message_to_json(self.metadata)}"
        mesh = "\n\nNodes in mesh: "
        nodes = {}
        if self.nodes:
            for n in self.nodes.values():
                # when the TBeam is first booted, it sometimes shows the raw data
                # so, we will just remove any raw keys
                keys_to_remove = ("raw", "decoded", "payload")
                n2 = remove_keys_from_dict(keys_to_remove, n)

                # if we have 'macaddr', re-format it
                if "macaddr" in n2["user"]:
                    val = n2["user"]["macaddr"]
                    # decode the base64 value
                    addr = convert_mac_addr(val)
                    n2["user"]["macaddr"] = addr

                # use id as dictionary key for correct json format in list of nodes
                nodeid = n2["user"]["id"]
                nodes[nodeid] = n2
        infos = owner + myinfo + metadata + mesh + json.dumps(nodes, indent=2)
        print(infos)
        return infos

    def showNodes(self, includeSelf: bool=True, file=sys.stdout) -> str:  # pylint: disable=W0613
        """Show table summary of nodes in mesh"""

        def formatFloat(value, precision=2, unit="") -> Optional[str]:
            """Format a float value with precision."""
            return f"{value:.{precision}f}{unit}" if value else None

        def getLH(ts) -> Optional[str]:
            """Format last heard"""
            return (
                datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else None
            )

        def getTimeAgo(ts) -> Optional[str]:
            """Format how long ago have we heard from this node (aka timeago)."""
            if ts is None:
                return None
            delta = datetime.now() - datetime.fromtimestamp(ts)
            delta_secs = int(delta.total_seconds())
            if delta_secs < 0:
                return None  # not handling a timestamp from the future
            return _timeago(delta_secs)

        rows: List[Dict[str, Any]] = []
        if self.nodesByNum:
            logging.debug(f"self.nodes:{self.nodes}")
            for node in self.nodesByNum.values():
                if not includeSelf and node["num"] == self.localNode.nodeNum:
                    continue

                presumptive_id = f"!{node['num']:08x}"
                row = {"N": 0, "User": f"Meshtastic {presumptive_id[-4:]}", "ID": presumptive_id}

                user = node.get("user")
                if user:
                    row.update(
                        {
                            "User": user.get("longName", "N/A"),
                            "AKA": user.get("shortName", "N/A"),
                            "ID": user["id"],
                            "Hardware": user.get("hwModel", "UNSET")
                        }
                    )

                pos = node.get("position")
                if pos:
                    row.update(
                        {
                            "Latitude": formatFloat(pos.get("latitude"), 4, "°"),
                            "Longitude": formatFloat(pos.get("longitude"), 4, "°"),
                            "Altitude": formatFloat(pos.get("altitude"), 0, " m"),
                        }
                    )

                metrics = node.get("deviceMetrics")
                if metrics:
                    batteryLevel = metrics.get("batteryLevel")
                    if batteryLevel is not None:
                        if batteryLevel == 0:
                            batteryString = "Powered"
                        else:
                            batteryString = str(batteryLevel) + "%"
                        row.update({"Battery": batteryString})
                    row.update(
                        {
                            "Channel util.": formatFloat(
                                metrics.get("channelUtilization"), 2, "%"
                            ),
                            "Tx air util.": formatFloat(
                                metrics.get("airUtilTx"), 2, "%"
                            ),
                        }
                    )

                row.update(
                    {
                        "SNR": formatFloat(node.get("snr"), 2, " dB"),
                        "Hops Away": node.get("hopsAway", "0/unknown"),
                        "Channel": node.get("channel", 0),
                        "LastHeard": getLH(node.get("lastHeard")),
                        "Since": getTimeAgo(node.get("lastHeard")),
                    }
                )

                rows.append(row)

        rows.sort(key=lambda r: r.get("LastHeard") or "0000", reverse=True)
        for i, row in enumerate(rows):
            row["N"] = i + 1

        table = tabulate(rows, headers="keys", missingval="N/A", tablefmt="fancy_grid")
        print(table)
        return table

    def getNode(self, nodeId: str, requestChannels: bool=True) -> meshtastic.node.Node:
        """Return a node object which contains device settings and channel info"""
        if nodeId in (LOCAL_ADDR, BROADCAST_ADDR):
            return self.localNode
        else:
            n = meshtastic.node.Node(self, nodeId)
            # Only request device settings and channel info when necessary
            if requestChannels:
                logging.debug("About to requestChannels")
                n.requestChannels()
                if not n.waitForConfig():
                    our_exit("Error: Timed out waiting for channels")
            return n

    def sendText(
        self,
        text: str,
        destinationId: Union[int, str]=BROADCAST_ADDR,
        wantAck: bool=False,
        wantResponse: bool=False,
        onResponse: Optional[Callable[[dict], Any]]=None,
        channelIndex: int=0,
    ):
        """Send a utf8 string to some other node, if the node has a display it
           will also be shown on the device.

        Arguments:
            text {string} -- The text to send

        Keyword Arguments:
            destinationId {nodeId or nodeNum} -- where to send this
                                                 message (default: {BROADCAST_ADDR})
            portNum -- the application portnum (similar to IP port numbers)
                       of the destination, see portnums.proto for a list
            wantAck -- True if you want the message sent in a reliable manner
                       (with retries and ack/nak provided for delivery)
            wantResponse -- True if you want the service on the other side to
                            send an application layer response

        Returns the sent packet. The id field will be populated in this packet
        and can be used to track future message acks/naks.
        """

        return self.sendData(
            text.encode("utf-8"),
            destinationId,
            portNum=portnums_pb2.PortNum.TEXT_MESSAGE_APP,
            wantAck=wantAck,
            wantResponse=wantResponse,
            onResponse=onResponse,
            channelIndex=channelIndex,
        )

    def sendData(
        self,
        data,
        destinationId: Union[int, str]=BROADCAST_ADDR,
        portNum: portnums_pb2.PortNum.ValueType=portnums_pb2.PortNum.PRIVATE_APP,
        wantAck: bool=False,
        wantResponse: bool=False,
        onResponse: Optional[Callable[[dict], Any]]=None,
        onResponseAckPermitted: bool=False,
        channelIndex: int=0,
        hopLimit: Optional[int]=None,
    ):
        """Send a data packet to some other node

        Keyword Arguments:
            data -- the data to send, either as an array of bytes or
                    as a protobuf (which will be automatically
                    serialized to bytes)
            destinationId {nodeId or nodeNum} -- where to send this
                    message (default: {BROADCAST_ADDR})
            portNum -- the application portnum (similar to IP port numbers)
                    of the destination, see portnums.proto for a list
            wantAck -- True if you want the message sent in a reliable
                    manner (with retries and ack/nak provided for delivery)
            wantResponse -- True if you want the service on the other
                    side to send an application layer response
            onResponse -- A closure of the form funct(packet), that will be
                    called when a response packet arrives (or the transaction
                    is NAKed due to non receipt)
            onResponseAckPermitted -- should the onResponse callback be called
                    for regular ACKs (True) or just data responses & NAKs (False)
                    Note that if the onResponse callback is called 'onAckNak' this
                    will implicitly be true.
            channelIndex -- channel number to use
            hopLimit -- hop limit to use

        Returns the sent packet. The id field will be populated in this packet
        and can be used to track future message acks/naks.
        """

        if getattr(data, "SerializeToString", None):
            logging.debug(f"Serializing protobuf as data: {stripnl(data)}")
            data = data.SerializeToString()

        logging.debug(f"len(data): {len(data)}")
        logging.debug(
            f"mesh_pb2.Constants.DATA_PAYLOAD_LEN: {mesh_pb2.Constants.DATA_PAYLOAD_LEN}"
        )
        if len(data) > mesh_pb2.Constants.DATA_PAYLOAD_LEN:
            raise MeshInterface.MeshInterfaceError("Data payload too big")

        if (
            portNum == portnums_pb2.PortNum.UNKNOWN_APP
        ):  # we are now more strict wrt port numbers
            our_exit("Warning: A non-zero port number must be specified")

        meshPacket = mesh_pb2.MeshPacket()
        meshPacket.channel = channelIndex
        meshPacket.decoded.payload = data
        meshPacket.decoded.portnum = portNum
        meshPacket.decoded.want_response = wantResponse
        meshPacket.id = self._generatePacketId()

        if onResponse is not None:
            logging.debug(f"Setting a response handler for requestId {meshPacket.id}")
            self._addResponseHandler(meshPacket.id, onResponse, ackPermitted=onResponseAckPermitted)
        p = self._sendPacket(meshPacket, destinationId, wantAck=wantAck, hopLimit=hopLimit)
        return p

    def sendPosition(
        self,
        latitude: float=0.0,
        longitude: float=0.0,
        altitude: int=0,
        timeSec: int=0,
        destinationId: Union[int, str]=BROADCAST_ADDR,
        wantAck: bool=False,
        wantResponse: bool=False,
        channelIndex: int=0,
    ):
        """
        Send a position packet to some other node (normally a broadcast)

        Also, the device software will notice this packet and use it to automatically
        set its notion of the local position.

        If timeSec is not specified (recommended), we will use the local machine time.

        Returns the sent packet. The id field will be populated in this packet and
        can be used to track future message acks/naks.
        """
        p = mesh_pb2.Position()
        if latitude != 0.0:
            p.latitude_i = int(latitude / 1e-7)
            logging.debug(f"p.latitude_i:{p.latitude_i}")

        if longitude != 0.0:
            p.longitude_i = int(longitude / 1e-7)
            logging.debug(f"p.longitude_i:{p.longitude_i}")

        if altitude != 0:
            p.altitude = int(altitude)
            logging.debug(f"p.altitude:{p.altitude}")

        if timeSec == 0:
            timeSec = int(time.time())  # returns unix timestamp in seconds
        p.time = timeSec
        logging.debug(f"p.time:{p.time}")

        if wantResponse:
            onResponse = self.onResponsePosition
        else:
            onResponse = None

        d = self.sendData(
            p,
            destinationId,
            portNum=portnums_pb2.PortNum.POSITION_APP,
            wantAck=wantAck,
            wantResponse=wantResponse,
            onResponse=onResponse,
            channelIndex=channelIndex,
        )
        if wantResponse:
            self.waitForPosition()
        return d

    def onResponsePosition(self, p):
        """on response for position"""
        if p["decoded"]["portnum"] == 'POSITION_APP':
            self._acknowledgment.receivedPosition = True
            position = mesh_pb2.Position()
            position.ParseFromString(p["decoded"]["payload"])

            ret = "Position received: "
            if position.latitude_i != 0 and position.longitude_i != 0:
                ret += f"({position.latitude_i * 10**-7}, {position.longitude_i * 10**-7})"
            else:
                ret += "(unknown)"
            if position.altitude != 0:
                ret += f" {position.altitude}m"

            if position.precision_bits not in [0,32]:
                ret += f" precision:{position.precision_bits}"
            elif position.precision_bits == 32:
                ret += " full precision"
            elif position.precision_bits == 0:
                ret += " position disabled"

            print(ret)

        elif p["decoded"]["portnum"] == 'ROUTING_APP':
            if p["decoded"]["routing"]["errorReason"] == 'NO_RESPONSE':
                our_exit("No response from node. At least firmware 2.1.22 is required on the destination node.")

    def sendTraceRoute(self, dest: Union[int, str], hopLimit: int, channelIndex: int=0):
        """Send the trace route"""
        r = mesh_pb2.RouteDiscovery()
        self.sendData(
            r,
            destinationId=dest,
            portNum=portnums_pb2.PortNum.TRACEROUTE_APP,
            wantResponse=True,
            onResponse=self.onResponseTraceRoute,
            channelIndex=channelIndex,
            hopLimit=hopLimit,
        )
        # extend timeout based on number of nodes, limit by configured hopLimit
        waitFactor = min(len(self.nodes) - 1 if self.nodes else 0, hopLimit)
        self.waitForTraceRoute(waitFactor)

    def onResponseTraceRoute(self, p: dict):
        """on response for trace route"""
        routeDiscovery = mesh_pb2.RouteDiscovery()
        routeDiscovery.ParseFromString(p["decoded"]["payload"])
        asDict = google.protobuf.json_format.MessageToDict(routeDiscovery)

        print("Route traced:")
        routeStr = self._nodeNumToId(p["to"]) or f"{p['to']:08x}"
        if "route" in asDict:
            for nodeNum in asDict["route"]:
                routeStr += " --> " + (self._nodeNumToId(nodeNum) or f"{nodeNum:08x}")
        routeStr += " --> " + (self._nodeNumToId(p["from"]) or f"{p['from']:08x}")
        print(routeStr)

        self._acknowledgment.receivedTraceRoute = True

    def sendTelemetry(self, destinationId: Union[int,str]=BROADCAST_ADDR, wantResponse: bool=False, channelIndex: int=0):
        """Send telemetry and optionally ask for a response"""
        r = telemetry_pb2.Telemetry()

        if self.nodes is not None:
            node = next(n for n in self.nodes.values() if n["num"] == self.localNode.nodeNum)
            if node is not None:
                metrics = node.get("deviceMetrics")
                if metrics:
                    batteryLevel = metrics.get("batteryLevel")
                    if batteryLevel is not None:
                        r.device_metrics.battery_level = batteryLevel
                    voltage = metrics.get("voltage")
                    if voltage is not None:
                        r.device_metrics.voltage = voltage
                    channel_utilization = metrics.get("channelUtilization")
                    if channel_utilization is not None:
                        r.device_metrics.channel_utilization = channel_utilization
                    air_util_tx = metrics.get("airUtilTx")
                    if air_util_tx is not None:
                        r.device_metrics.air_util_tx = air_util_tx

        if wantResponse:
            onResponse = self.onResponseTelemetry
        else:
            onResponse = None

        self.sendData(
            r,
            destinationId=destinationId,
            portNum=portnums_pb2.PortNum.TELEMETRY_APP,
            wantResponse=wantResponse,
            onResponse=onResponse,
            channelIndex=channelIndex,
        )
        if wantResponse:
            self.waitForTelemetry()

    def onResponseTelemetry(self, p: dict):
        """on response for telemetry"""
        if p["decoded"]["portnum"] == 'TELEMETRY_APP':
            self._acknowledgment.receivedTelemetry = True
            telemetry = telemetry_pb2.Telemetry()
            telemetry.ParseFromString(p["decoded"]["payload"])

            print("Telemetry received:")
            if telemetry.device_metrics.battery_level is not None:
                print(f"Battery level: {telemetry.device_metrics.battery_level:.2f}%")
            if telemetry.device_metrics.voltage is not None:
                print(f"Voltage: {telemetry.device_metrics.voltage:.2f} V")
            if telemetry.device_metrics.channel_utilization is not None:
                print(
                    f"Total channel utilization: {telemetry.device_metrics.channel_utilization:.2f}%"
                )
            if telemetry.device_metrics.air_util_tx is not None:
                print(f"Transmit air utilization: {telemetry.device_metrics.air_util_tx:.2f}%")

        elif p["decoded"]["portnum"] == 'ROUTING_APP':
            if p["decoded"]["routing"]["errorReason"] == 'NO_RESPONSE':
                our_exit("No response from node. At least firmware 2.1.22 is required on the destination node.")

    def _addResponseHandler(self, requestId: int, callback: Callable[[dict], Any], ackPermitted: bool=False):
        self.responseHandlers[requestId] = ResponseHandler(callback=callback, ackPermitted=ackPermitted)

    def _sendPacket(
        self,
        meshPacket: mesh_pb2.MeshPacket,
        destinationId: Union[int,str]=BROADCAST_ADDR,
        wantAck: bool=False,
        hopLimit: Optional[int]=None
    ):
        """Send a MeshPacket to the specified node (or if unspecified, broadcast).
        You probably don't want this - use sendData instead.

        Returns the sent packet. The id field will be populated in this packet and
        can be used to track future message acks/naks.
        """

        # We allow users to talk to the local node before we've completed the full connection flow...
        if self.myInfo is not None and destinationId != self.myInfo.my_node_num:
            self._waitConnected()

        toRadio = mesh_pb2.ToRadio()

        nodeNum: int = 0
        if destinationId is None:
            our_exit("Warning: destinationId must not be None")
        elif isinstance(destinationId, int):
            nodeNum = destinationId
        elif destinationId == BROADCAST_ADDR:
            nodeNum = BROADCAST_NUM
        elif destinationId == LOCAL_ADDR:
            if self.myInfo:
                nodeNum = self.myInfo.my_node_num
            else:
                our_exit("Warning: No myInfo found.")
        # A simple hex style nodeid - we can parse this without needing the DB
        elif destinationId.startswith("!"):
            nodeNum = int(destinationId[1:], 16)
        else:
            if self.nodes:
                node = self.nodes.get(destinationId)
                if node is None:
                    our_exit(f"Warning: NodeId {destinationId} not found in DB")
                else:
                    nodeNum = node["num"]
            else:
                logging.warning("Warning: There were no self.nodes.")

        meshPacket.to = nodeNum
        meshPacket.want_ack = wantAck

        if hopLimit is not None:
            meshPacket.hop_limit = hopLimit
        else:
            loraConfig = getattr(self.localNode.localConfig, "lora")
            meshPacket.hop_limit = getattr(loraConfig, "hop_limit")

        # if the user hasn't set an ID for this packet (likely and recommended),
        # we should pick a new unique ID so the message can be tracked.
        if meshPacket.id == 0:
            meshPacket.id = self._generatePacketId()

        toRadio.packet.CopyFrom(meshPacket)
        if self.noProto:
            logging.warning(
                f"Not sending packet because protocol use is disabled by noProto"
            )
        else:
            logging.debug(f"Sending packet: {stripnl(meshPacket)}")
            self._sendToRadio(toRadio)
        return meshPacket

    def waitForConfig(self):
        """Block until radio config is received. Returns True if config has been received."""
        success = (
            self._timeout.waitForSet(self, attrs=("myInfo", "nodes"))
            and self.localNode.waitForConfig()
        )
        if not success:
            raise MeshInterface.MeshInterfaceError("Timed out waiting for interface config")

    def waitForAckNak(self):
        """Wait for the ack/nak"""
        success = self._timeout.waitForAckNak(self._acknowledgment)
        if not success:
            raise MeshInterface.MeshInterfaceError("Timed out waiting for an acknowledgment")

    def waitForTraceRoute(self, waitFactor):
        """Wait for trace route"""
        success = self._timeout.waitForTraceRoute(waitFactor, self._acknowledgment)
        if not success:
            raise MeshInterface.MeshInterfaceError("Timed out waiting for traceroute")

    def waitForTelemetry(self):
        """Wait for telemetry"""
        success = self._timeout.waitForTelemetry(self._acknowledgment)
        if not success:
            raise MeshInterface.MeshInterfaceError("Timed out waiting for telemetry")

    def waitForPosition(self):
        """Wait for position"""
        success = self._timeout.waitForPosition(self._acknowledgment)
        if not success:
            raise MeshInterface.MeshInterfaceError("Timed out waiting for position")

    def getMyNodeInfo(self) -> Optional[Dict]:
        """Get info about my node."""
        if self.myInfo is None or self.nodesByNum is None:
            return None
        logging.debug(f"self.nodesByNum:{self.nodesByNum}")
        return self.nodesByNum.get(self.myInfo.my_node_num)

    def getMyUser(self):
        """Get user"""
        nodeInfo = self.getMyNodeInfo()
        if nodeInfo is not None:
            return nodeInfo.get("user")
        return None

    def getLongName(self):
        """Get long name"""
        user = self.getMyUser()
        if user is not None:
            return user.get("longName", None)
        return None

    def getShortName(self):
        """Get short name"""
        user = self.getMyUser()
        if user is not None:
            return user.get("shortName", None)
        return None

    def _waitConnected(self, timeout=30.0):
        """Block until the initial node db download is complete, or timeout
        and raise an exception"""
        if not self.noProto:
            if not self.isConnected.wait(timeout):  # timeout after x seconds
                raise MeshInterface.MeshInterfaceError("Timed out waiting for connection completion")

        # If we failed while connecting, raise the connection to the client
        if self.failure:
            raise self.failure

    def _generatePacketId(self) -> int:
        """Get a new unique packet ID"""
        if self.currentPacketId is None:
            raise MeshInterface.MeshInterfaceError("Not connected yet, can not generate packet")
        else:
            self.currentPacketId = (self.currentPacketId + 1) & 0xFFFFFFFF
            return self.currentPacketId

    def _disconnected(self):
        """Called by subclasses to tell clients this interface has disconnected"""
        self.isConnected.clear()
        publishingThread.queueWork(
            lambda: pub.sendMessage("meshtastic.connection.lost", interface=self)
        )

    def _startHeartbeat(self):
        """We need to send a heartbeat message to the device every X seconds"""

        def callback():
            self.heartbeatTimer = None
            i = 300
            logging.debug(f"Sending heartbeat, interval {i} seconds")
            if i != 0:
                self.heartbeatTimer = threading.Timer(i, callback)
                self.heartbeatTimer.start()
                p = mesh_pb2.ToRadio()
                p.heartbeat.CopyFrom(mesh_pb2.Heartbeat())
                self._sendToRadio(p)

        callback()  # run our periodic callback now, it will make another timer if necessary

    def _connected(self):
        """Called by this class to tell clients we are now fully connected to a node"""
        # (because I'm lazy) _connected might be called when remote Node
        # objects complete their config reads, don't generate redundant isConnected
        # for the local interface
        if not self.isConnected.is_set():
            self.isConnected.set()
            self._startHeartbeat()
            publishingThread.queueWork(
                lambda: pub.sendMessage(
                    "meshtastic.connection.established", interface=self
                )
            )

    def _startConfig(self):
        """Start device packets flowing"""
        self.myInfo = None
        self.nodes = {}  # nodes keyed by ID
        self.nodesByNum = {}  # nodes keyed by nodenum
        self._localChannels = [] # empty until we start getting channels pushed from the device (during config)

        startConfig = mesh_pb2.ToRadio()
        if self.configId is None or not self.noNodes:
            self.configId = random.randint(0, 0xFFFFFFFF)
        startConfig.want_config_id = self.configId
        self._sendToRadio(startConfig)

    def _sendDisconnect(self):
        """Tell device we are done using it"""
        m = mesh_pb2.ToRadio()
        m.disconnect = True
        self._sendToRadio(m)

    def _queueHasFreeSpace(self) -> bool:
        # We never got queueStatus, maybe the firmware is old
        if self.queueStatus is None:
            return True
        return self.queueStatus.free > 0

    def _queueClaim(self) -> None:
        if self.queueStatus is None:
            return
        self.queueStatus.free -= 1

    def _sendToRadio(self, toRadio: mesh_pb2.ToRadio) -> None:
        """Send a ToRadio protobuf to the device"""
        if self.noProto:
            logging.warning(
                f"Not sending packet because protocol use is disabled by noProto"
            )
        else:
            # logging.debug(f"Sending toRadio: {stripnl(toRadio)}")

            if not toRadio.HasField("packet"):
                # not a meshpacket -- send immediately, give queue a chance,
                # this makes heartbeat trigger queue
                self._sendToRadioImpl(toRadio)
            else:
                # meshpacket -- queue
                self.queue[toRadio.packet.id] = toRadio

            resentQueue = collections.OrderedDict()

            while self.queue:
                # logging.warn("queue: " + " ".join(f'{k:08x}' for k in self.queue))
                while not self._queueHasFreeSpace():
                    logging.debug("Waiting for free space in TX Queue")
                    time.sleep(0.5)
                try:
                    toResend = self.queue.popitem(last=False)
                except KeyError:
                    break
                packetId, packet = toResend
                # logging.warn(f"packet: {packetId:08x} {packet}")
                resentQueue[packetId] = packet
                if packet is False:
                    continue
                self._queueClaim()
                if packet != toRadio:
                    logging.debug(f"Resending packet ID {packetId:08x} {packet}")
                self._sendToRadioImpl(packet)

            # logging.warn("resentQueue: " + " ".join(f'{k:08x}' for k in resentQueue))
            for packetId, packet in resentQueue.items():
                if (
                    self.queue.pop(packetId, False) is False
                ):  # Packet got acked under us
                    logging.debug(f"packet {packetId:08x} got acked under us")
                    continue
                if packet:
                    self.queue[packetId] = packet
            # logging.warn("queue + resentQueue: " + " ".join(f'{k:08x}' for k in self.queue))

    def _sendToRadioImpl(self, toRadio: mesh_pb2.ToRadio) -> None:
        """Send a ToRadio protobuf to the device"""
        logging.error(f"Subclass must provide toradio: {toRadio}")

    def _handleConfigComplete(self) -> None:
        """
        Done with initial config messages, now send regular MeshPackets
        to ask for settings and channels
        """
        # This is no longer necessary because the current protocol statemachine has already proactively sent us the locally visible channels
        # self.localNode.requestChannels()
        self.localNode.setChannels(self._localChannels)

        # the following should only be called after we have settings and channels
        self._connected()  # Tell everyone else we are ready to go

    def _handleQueueStatusFromRadio(self, queueStatus) -> None:
        self.queueStatus = queueStatus
        logging.debug(
            f"TX QUEUE free {queueStatus.free} of {queueStatus.maxlen}, res = {queueStatus.res}, id = {queueStatus.mesh_packet_id:08x} "
        )

        if queueStatus.res:
            return

        # logging.warn("queue: " + " ".join(f'{k:08x}' for k in self.queue))
        justQueued = self.queue.pop(queueStatus.mesh_packet_id, None)

        if justQueued is None and queueStatus.mesh_packet_id != 0:
            self.queue[queueStatus.mesh_packet_id] = False
            logging.debug(
                f"Reply for unexpected packet ID {queueStatus.mesh_packet_id:08x}"
            )
        # logging.warn("queue: " + " ".join(f'{k:08x}' for k in self.queue))

    def _handleFromRadio(self, fromRadioBytes):
        """
        Handle a packet that arrived from the radio(update model and publish events)

        Called by subclasses."""
        fromRadio = mesh_pb2.FromRadio()
        fromRadio.ParseFromString(fromRadioBytes)
        logging.debug(
            f"in mesh_interface.py _handleFromRadio() fromRadioBytes: {fromRadioBytes}"
        )
        asDict = google.protobuf.json_format.MessageToDict(fromRadio)
        logging.debug(f"Received from radio: {fromRadio}")
        if fromRadio.HasField("my_info"):
            self.myInfo = fromRadio.my_info
            self.localNode.nodeNum = self.myInfo.my_node_num
            logging.debug(f"Received myinfo: {stripnl(fromRadio.my_info)}")

            failmsg = None

            if failmsg:
                self.failure = MeshInterface.MeshInterfaceError(failmsg)
                self.isConnected.set()  # let waitConnected return this exception
                self.close()

        elif fromRadio.HasField("metadata"):
            self.metadata = fromRadio.metadata
            logging.debug(f"Received device metadata: {stripnl(fromRadio.metadata)}")

        elif fromRadio.HasField("node_info"):
            logging.debug(f"Received nodeinfo: {asDict['nodeInfo']}")

            node = self._getOrCreateByNum(asDict["nodeInfo"]["num"])
            node.update(asDict["nodeInfo"])
            try:
                newpos = self._fixupPosition(node["position"])
                node["position"] = newpos
            except:
                logging.debug("Node without position")

            # no longer necessary since we're mutating directly in nodesByNum via _getOrCreateByNum
            #self.nodesByNum[node["num"]] = node
            if "user" in node:  # Some nodes might not have user/ids assigned yet
                if "id" in node["user"]:
                    self.nodes[node["user"]["id"]] = node
            publishingThread.queueWork(
                lambda: pub.sendMessage(
                    "meshtastic.node.updated", node=node, interface=self
                )
            )
        elif fromRadio.config_complete_id == self.configId:
            # we ignore the config_complete_id, it is unneeded for our
            # stream API fromRadio.config_complete_id
            logging.debug(f"Config complete ID {self.configId}")
            self._handleConfigComplete()
        elif fromRadio.HasField("channel"):
            self._handleChannel(fromRadio.channel)
        elif fromRadio.HasField("packet"):
            self._handlePacketFromRadio(fromRadio.packet)

        elif fromRadio.HasField("queueStatus"):
            self._handleQueueStatusFromRadio(fromRadio.queueStatus)

        elif fromRadio.HasField("mqttClientProxyMessage"):
            publishingThread.queueWork(
                lambda: pub.sendMessage(
                    "meshtastic.mqttclientproxymessage", proxymessage=fromRadio.mqttClientProxyMessage, interface=self
                )
            )

        elif fromRadio.HasField("xmodemPacket"):
            publishingThread.queueWork(
                lambda: pub.sendMessage(
                    "meshtastic.xmodempacket", packet=fromRadio.xmodemPacket, interface=self
                )
            )

        elif fromRadio.HasField("rebooted") and fromRadio.rebooted:
            # Tell clients the device went away.  Careful not to call the overridden
            # subclass version that closes the serial port
            MeshInterface._disconnected(self)

            self._startConfig()  # redownload the node db etc...

        elif fromRadio.HasField("config") or fromRadio.HasField("moduleConfig"):
            if fromRadio.config.HasField("device"):
                self.localNode.localConfig.device.CopyFrom(fromRadio.config.device)
            elif fromRadio.config.HasField("position"):
                self.localNode.localConfig.position.CopyFrom(fromRadio.config.position)
            elif fromRadio.config.HasField("power"):
                self.localNode.localConfig.power.CopyFrom(fromRadio.config.power)
            elif fromRadio.config.HasField("network"):
                self.localNode.localConfig.network.CopyFrom(fromRadio.config.network)
            elif fromRadio.config.HasField("display"):
                self.localNode.localConfig.display.CopyFrom(fromRadio.config.display)
            elif fromRadio.config.HasField("lora"):
                self.localNode.localConfig.lora.CopyFrom(fromRadio.config.lora)
            elif fromRadio.config.HasField("bluetooth"):
                self.localNode.localConfig.bluetooth.CopyFrom(
                    fromRadio.config.bluetooth
                )

            elif fromRadio.moduleConfig.HasField("mqtt"):
                self.localNode.moduleConfig.mqtt.CopyFrom(fromRadio.moduleConfig.mqtt)
            elif fromRadio.moduleConfig.HasField("serial"):
                self.localNode.moduleConfig.serial.CopyFrom(
                    fromRadio.moduleConfig.serial
                )
            elif fromRadio.moduleConfig.HasField("external_notification"):
                self.localNode.moduleConfig.external_notification.CopyFrom(
                    fromRadio.moduleConfig.external_notification
                )
            elif fromRadio.moduleConfig.HasField("store_forward"):
                self.localNode.moduleConfig.store_forward.CopyFrom(
                    fromRadio.moduleConfig.store_forward
                )
            elif fromRadio.moduleConfig.HasField("range_test"):
                self.localNode.moduleConfig.range_test.CopyFrom(
                    fromRadio.moduleConfig.range_test
                )
            elif fromRadio.moduleConfig.HasField("telemetry"):
                self.localNode.moduleConfig.telemetry.CopyFrom(
                    fromRadio.moduleConfig.telemetry
                )
            elif fromRadio.moduleConfig.HasField("canned_message"):
                self.localNode.moduleConfig.canned_message.CopyFrom(
                    fromRadio.moduleConfig.canned_message
                )
            elif fromRadio.moduleConfig.HasField("audio"):
                self.localNode.moduleConfig.audio.CopyFrom(fromRadio.moduleConfig.audio)
            elif fromRadio.moduleConfig.HasField("remote_hardware"):
                self.localNode.moduleConfig.remote_hardware.CopyFrom(
                    fromRadio.moduleConfig.remote_hardware
                )
            elif fromRadio.moduleConfig.HasField("neighbor_info"):
                self.localNode.moduleConfig.neighbor_info.CopyFrom(
                    fromRadio.moduleConfig.neighbor_info
                )
            elif fromRadio.moduleConfig.HasField("detection_sensor"):
                self.localNode.moduleConfig.detection_sensor.CopyFrom(
                    fromRadio.moduleConfig.detection_sensor
                )
            elif fromRadio.moduleConfig.HasField("ambient_lighting"):
                self.localNode.moduleConfig.ambient_lighting.CopyFrom(
                    fromRadio.moduleConfig.ambient_lighting
                )
            elif fromRadio.moduleConfig.HasField("paxcounter"):
                self.localNode.moduleConfig.paxcounter.CopyFrom(
                    fromRadio.moduleConfig.paxcounter
                )

        else:
            logging.debug("Unexpected FromRadio payload")

    def _fixupPosition(self, position: Dict) -> Dict:
        """Convert integer lat/lon into floats

        Arguments:
            position {Position dictionary} -- object to fix up
        Returns the position with the updated keys
        """
        if "latitudeI" in position:
            position["latitude"] = float(position["latitudeI"] * Decimal("1e-7"))
        if "longitudeI" in position:
            position["longitude"] = float(position["longitudeI"] * Decimal("1e-7"))
        return position

    def _nodeNumToId(self, num: int) -> Optional[str]:
        """Map a node node number to a node ID

        Arguments:
            num {int} -- Node number

        Returns:
            string -- Node ID
        """
        if num == BROADCAST_NUM:
            return BROADCAST_ADDR

        try:
            return self.nodesByNum[num]["user"]["id"] #type: ignore[index]
        except:
            logging.debug(f"Node {num} not found for fromId")
            return None

    def _getOrCreateByNum(self, nodeNum):
        """Given a nodenum find the NodeInfo in the DB (or create if necessary)"""
        if nodeNum == BROADCAST_NUM:
            raise MeshInterface.MeshInterfaceError("Can not create/find nodenum by the broadcast num")

        if nodeNum in self.nodesByNum:
            return self.nodesByNum[nodeNum]
        else:
            presumptive_id = f"!{nodeNum:08x}"
            n = {
                "num": nodeNum,
                "user": {
                    "id": presumptive_id,
                    "longName": f"Meshtastic {presumptive_id[-4:]}",
                    "shortName": f"{presumptive_id[-4:]}",
                    "hwModel": "UNSET"
                    }
                }  # Create a minimal node db entry
            self.nodesByNum[nodeNum] = n
            return n

    def _handleChannel(self, channel):
        """During initial config the local node will proactively send all N (8) channels it knows"""
        self._localChannels.append(channel)

    def _handlePacketFromRadio(self, meshPacket, hack=False):
        """Handle a MeshPacket that just arrived from the radio

        hack - well, since we used 'from', which is a python keyword,
               as an attribute to MeshPacket in protobufs,
               there really is no way to do something like this:
                    meshPacket = mesh_pb2.MeshPacket()
                    meshPacket.from = 123
               If hack is True, we can unit test this code.

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
        if not hack and "from" not in asDict:
            asDict["from"] = 0
            logging.error(
                f"Device returned a packet we sent, ignoring: {stripnl(asDict)}"
            )
            print(
                f"Error: Device returned a packet we sent, ignoring: {stripnl(asDict)}"
            )
            return
        if "to" not in asDict:
            asDict["to"] = 0

        # /add fromId and toId fields based on the node ID
        try:
            asDict["fromId"] = self._nodeNumToId(asDict["from"])
        except Exception as ex:
            logging.warning(f"Not populating fromId {ex}")
        try:
            asDict["toId"] = self._nodeNumToId(asDict["to"])
        except Exception as ex:
            logging.warning(f"Not populating toId {ex}")

        # We could provide our objects as DotMaps - which work with . notation or as dictionaries
        # asObj = DotMap(asDict)
        topic = "meshtastic.receive"  # Generic unknown packet type

        decoded = None
        portnum = portnums_pb2.PortNum.Name(portnums_pb2.PortNum.UNKNOWN_APP)
        if "decoded" in asDict:
            decoded = asDict["decoded"]
            # The default MessageToDict converts byte arrays into base64 strings.
            # We don't want that - it messes up data payload.  So slam in the correct
            # byte array.
            decoded["payload"] = meshPacket.decoded.payload

            # UNKNOWN_APP is the default protobuf portnum value, and therefore if not
            # set it will not be populated at all to make API usage easier, set
            # it to prevent confusion
            if "portnum" not in decoded:
                decoded["portnum"] = portnum
                logging.warning(f"portnum was not in decoded. Setting to:{portnum}")
            else:
                portnum = decoded["portnum"]

            topic = f"meshtastic.receive.data.{portnum}"

            # decode position protobufs and update nodedb, provide decoded version
            # as "position" in the published msg move the following into a 'decoders'
            # API that clients could register?
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
                logging.debug(f"Got a response for requestId {requestId}")
                # We ignore ACK packets unless the callback is named `onAckNak`
                # or the handler is set as ackPermitted, but send NAKs and
                # other, data-containing responses to the handlers
                routing = decoded.get("routing")
                isAck = routing is not None and ("errorReason" not in routing or routing["errorReason"] == "NONE")
                # we keep the responseHandler in dict until we actually call it
                handler = self.responseHandlers.get(requestId, None)
                if handler is not None:
                    if (not isAck) or handler.callback.__name__ == "onAckNak" or handler.ackPermitted:
                        handler = self.responseHandlers.pop(requestId, None)
                        logging.debug(f"Calling response handler for requestId {requestId}")
                        handler.callback(asDict)

        logging.debug(f"Publishing {topic}: packet={stripnl(asDict)} ")
        publishingThread.queueWork(
            lambda: pub.sendMessage(topic, packet=asDict, interface=self)
        )
