"""Mesh Interface class
"""
# pylint: disable=R0917

import collections
import json
import logging
import math
import random
import secrets
import sys
import threading
import time
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Union

import google.protobuf.json_format
try:
    import print_color  # type: ignore[import-untyped]
except ImportError as e:
    print_color = None

from pubsub import pub  # type: ignore[import-untyped]
from tabulate import tabulate

import meshtastic.node
from meshtastic import (
    BROADCAST_ADDR,
    BROADCAST_NUM,
    LOCAL_ADDR,
    NODELESS_WANT_CONFIG_ID,
    ResponseHandler,
    protocols,
    publishingThread,
)
from meshtastic.protobuf import mesh_pb2, portnums_pb2, telemetry_pb2
from meshtastic.util import (
    Acknowledgment,
    Timeout,
    convert_mac_addr,
    message_to_json,
    our_exit,
    remove_keys_from_dict,
    stripnl,
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


class MeshInterface:  # pylint: disable=R0902
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

    def __init__(
        self, debugOut=None, noProto: bool = False, noNodes: bool = False
    ) -> None:
        """Constructor

        Keyword Arguments:
            noProto -- If True, don't try to run our protocol on the
                       link - just be a dumb serial client.
            noNodes -- If True, instruct the node to not send its nodedb
                       on startup, just other configuration information.
        """
        self.debugOut = debugOut
        self.nodes: Optional[Dict[str, Dict]] = None  # FIXME
        self.isConnected: threading.Event = threading.Event()
        self.noProto: bool = noProto
        self.localNode: meshtastic.node.Node = meshtastic.node.Node(
            self, -1
        )  # We fixup nodenum later
        self.myInfo: Optional[
            mesh_pb2.MyNodeInfo
        ] = None  # We don't have device info yet
        self.metadata: Optional[
            mesh_pb2.DeviceMetadata
        ] = None  # We don't have device metadata yet
        self.responseHandlers: Dict[
            int, ResponseHandler
        ] = {}  # A map from request ID to the handler
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

        # We could have just not passed in debugOut to MeshInterface, and instead told consumers to subscribe to
        # the meshtastic.log.line publish instead.  Alas though changing that now would be a breaking API change
        # for any external consumers of the library.
        if debugOut:
            pub.subscribe(MeshInterface._printLogLine, "meshtastic.log.line")

    def close(self):
        """Shutdown this interface"""
        if self.heartbeatTimer:
            self.heartbeatTimer.cancel()

        self._sendDisconnect()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        if exc_type is not None and exc_value is not None:
            logging.error(
                f"An exception of type {exc_type} with value {exc_value} has occurred"
            )
        if trace is not None:
            logging.error(f"Traceback: {trace}")
        self.close()

    @staticmethod
    def _printLogLine(line, interface):
        """Print a line of log output."""
        if print_color is not None and interface.debugOut == sys.stdout:
            # this isn't quite correct (could cause false positives), but currently our formatting differs between different log representations
            if "DEBUG" in line:
                print_color.print(line, color="cyan", end=None)
            elif "INFO" in line:
                print_color.print(line, color="white", end=None)
            elif "WARN" in line:
                print_color.print(line, color="yellow", end=None)
            elif "ERR" in line:
                print_color.print(line, color="red", end=None)
            else:
                print_color.print(line, end=None)
        else:
            interface.debugOut.write(line + "\n")

    def _handleLogLine(self, line: str) -> None:
        """Handle a line of log output from the device."""

        # Devices should _not_ be including a newline at the end of each log-line str (especially when
        # encapsulated as a LogRecord).  But to cope with old device loads, we check for that and fix it here:
        if line.endswith("\n"):
            line = line[:-1]

        pub.sendMessage("meshtastic.log.line", line=line, interface=self)

    def _handleLogRecord(self, record: mesh_pb2.LogRecord) -> None:
        """Handle a log record which was received encapsulated in a protobuf."""
        # For now we just try to format the line as if it had come in over the serial port
        self._handleLogLine(record.message)

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

    def showNodes(
        self, includeSelf: bool = True
    ) -> str:  # pylint: disable=W0613
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
                row = {
                    "N": 0,
                    "User": f"Meshtastic {presumptive_id[-4:]}",
                    "ID": presumptive_id,
                }

                user = node.get("user")
                if user:
                    row.update(
                        {
                            "User": user.get("longName", "N/A"),
                            "AKA": user.get("shortName", "N/A"),
                            "ID": user["id"],
                            "Hardware": user.get("hwModel", "UNSET"),
                            "Pubkey": user.get("publicKey", "UNSET"),
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
                        "Hops": node.get("hopsAway", "?"),
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

    def getNode(
        self, nodeId: str, requestChannels: bool = True, requestChannelAttempts: int = 3, timeout: int = 300
    ) -> meshtastic.node.Node:
        """Return a node object which contains device settings and channel info"""
        if nodeId in (LOCAL_ADDR, BROADCAST_ADDR):
            return self.localNode
        else:
            n = meshtastic.node.Node(self, nodeId, timeout=timeout)
            # Only request device settings and channel info when necessary
            if requestChannels:
                logging.debug("About to requestChannels")
                n.requestChannels()
                retries_left = requestChannelAttempts
                last_index: int = 0
                while retries_left > 0:
                    retries_left -= 1
                    if not n.waitForConfig():
                        new_index: int = len(n.partialChannels) if n.partialChannels else 0
                        # each time we get a new channel, reset the counter
                        if new_index != last_index:
                            retries_left = requestChannelAttempts - 1
                        if retries_left <= 0:
                            our_exit(f"Error: Timed out waiting for channels, giving up")
                        print("Timed out trying to retrieve channel info, retrying")
                        n.requestChannels(startingIndex=new_index)
                        last_index = new_index
                    else:
                        break
            return n

    def sendText(
        self,
        text: str,
        destinationId: Union[int, str] = BROADCAST_ADDR,
        wantAck: bool = False,
        wantResponse: bool = False,
        onResponse: Optional[Callable[[dict], Any]] = None,
        channelIndex: int = 0,
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


    def sendAlert(
        self,
        text: str,
        destinationId: Union[int, str] = BROADCAST_ADDR,
        onResponse: Optional[Callable[[dict], Any]] = None,
        channelIndex: int = 0,
    ):
        """Send an alert text to some other node. This is similar to a text message, 
            but carries a higher priority and is capable of generating special notifications
            on certain clients.

        Arguments:
            text {string} -- The text of the alert to send

        Keyword Arguments:
            destinationId {nodeId or nodeNum} -- where to send this
                                                 message (default: {BROADCAST_ADDR})

        Returns the sent packet. The id field will be populated in this packet
        and can be used to track future message acks/naks.
        """

        return self.sendData(
            text.encode("utf-8"),
            destinationId,
            portNum=portnums_pb2.PortNum.ALERT_APP,
            wantAck=False,
            wantResponse=False,
            onResponse=onResponse,
            channelIndex=channelIndex,
            priority=mesh_pb2.MeshPacket.Priority.ALERT
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
        pkiEncrypted: Optional[bool]=False,
        publicKey: Optional[bytes]=None,
        priority: mesh_pb2.MeshPacket.Priority.ValueType=mesh_pb2.MeshPacket.Priority.RELIABLE,
    ): # pylint: disable=R0913
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
        if priority is not None:
            meshPacket.priority = priority

        if onResponse is not None:
            logging.debug(f"Setting a response handler for requestId {meshPacket.id}")
            self._addResponseHandler(meshPacket.id, onResponse, ackPermitted=onResponseAckPermitted)
        p = self._sendPacket(meshPacket, destinationId, wantAck=wantAck, hopLimit=hopLimit, pkiEncrypted=pkiEncrypted, publicKey=publicKey)
        return p

    def sendPosition(
        self,
        latitude: float = 0.0,
        longitude: float = 0.0,
        altitude: int = 0,
        destinationId: Union[int, str] = BROADCAST_ADDR,
        wantAck: bool = False,
        wantResponse: bool = False,
        channelIndex: int = 0,
    ):
        """
        Send a position packet to some other node (normally a broadcast)

        Also, the device software will notice this packet and use it to automatically
        set its notion of the local position.

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
        if p["decoded"]["portnum"] == "POSITION_APP":
            self._acknowledgment.receivedPosition = True
            position = mesh_pb2.Position()
            position.ParseFromString(p["decoded"]["payload"])

            ret = "Position received: "
            if position.latitude_i != 0 and position.longitude_i != 0:
                ret += (
                    f"({position.latitude_i * 10**-7}, {position.longitude_i * 10**-7})"
                )
            else:
                ret += "(unknown)"
            if position.altitude != 0:
                ret += f" {position.altitude}m"

            if position.precision_bits not in [0, 32]:
                ret += f" precision:{position.precision_bits}"
            elif position.precision_bits == 32:
                ret += " full precision"
            elif position.precision_bits == 0:
                ret += " position disabled"

            print(ret)

        elif p["decoded"]["portnum"] == "ROUTING_APP":
            if p["decoded"]["routing"]["errorReason"] == "NO_RESPONSE":
                our_exit(
                    "No response from node. At least firmware 2.1.22 is required on the destination node."
                )

    def sendTraceRoute(
        self, dest: Union[int, str], hopLimit: int, channelIndex: int = 0
    ):
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
        UNK_SNR = -128 # Value representing unknown SNR

        routeDiscovery = mesh_pb2.RouteDiscovery()
        routeDiscovery.ParseFromString(p["decoded"]["payload"])
        asDict = google.protobuf.json_format.MessageToDict(routeDiscovery)

        print("Route traced towards destination:")
        routeStr = self._nodeNumToId(p["to"], False) or f"{p['to']:08x}" # Start with destination of response

        # SNR list should have one more entry than the route, as the final destination adds its SNR also
        lenTowards = 0 if "route" not in asDict else len(asDict["route"])
        snrTowardsValid = "snrTowards" in asDict and len(asDict["snrTowards"]) == lenTowards + 1
        if lenTowards > 0: # Loop through hops in route and add SNR if available
            for idx, nodeNum in enumerate(asDict["route"]):
                routeStr += " --> " + (self._nodeNumToId(nodeNum, False) or f"{nodeNum:08x}") \
                         + " (" + (str(asDict["snrTowards"][idx] / 4) if snrTowardsValid and asDict["snrTowards"][idx] != UNK_SNR else "?") + "dB)"

        # End with origin of response
        routeStr += " --> " + (self._nodeNumToId(p["from"], False) or f"{p['from']:08x}") \
                 + " (" + (str(asDict["snrTowards"][-1] / 4) if snrTowardsValid and asDict["snrTowards"][-1] != UNK_SNR else "?") + "dB)"

        print(routeStr) # Print the route towards destination

        # Only if hopStart is set and there is an SNR entry (for the origin) it's valid, even though route might be empty (direct connection)
        lenBack = 0 if "routeBack" not in asDict else len(asDict["routeBack"])
        backValid = "hopStart" in p and "snrBack" in asDict and len(asDict["snrBack"]) == lenBack + 1
        if backValid:
            print("Route traced back to us:")
            routeStr = self._nodeNumToId(p["from"], False) or f"{p['from']:08x}" # Start with origin of response

            if lenBack > 0: # Loop through hops in routeBack and add SNR if available
                for idx, nodeNum in enumerate(asDict["routeBack"]):
                    routeStr += " --> " + (self._nodeNumToId(nodeNum, False) or f"{nodeNum:08x}") \
                             + " (" + (str(asDict["snrBack"][idx] / 4) if asDict["snrBack"][idx] != UNK_SNR else "?") + "dB)"

            # End with destination of response (us)
            routeStr += " --> " + (self._nodeNumToId(p["to"], False) or f"{p['to']:08x}") \
                     + " (" + (str(asDict["snrBack"][-1] / 4) if asDict["snrBack"][-1] != UNK_SNR else "?") + "dB)"

            print(routeStr) # Print the route back to us

        self._acknowledgment.receivedTraceRoute = True

    def sendTelemetry(
        self,
        destinationId: Union[int, str] = BROADCAST_ADDR,
        wantResponse: bool = False,
        channelIndex: int = 0,
        telemetryType: str = "device_metrics"
    ):
        """Send telemetry and optionally ask for a response"""
        r = telemetry_pb2.Telemetry()

        if telemetryType == "environment_metrics":
            r.environment_metrics.CopyFrom(telemetry_pb2.EnvironmentMetrics())
        elif telemetryType == "air_quality_metrics":
            r.air_quality_metrics.CopyFrom(telemetry_pb2.AirQualityMetrics())
        elif telemetryType == "power_metrics":
            r.power_metrics.CopyFrom(telemetry_pb2.PowerMetrics())
        elif telemetryType == "local_stats":
            r.local_stats.CopyFrom(telemetry_pb2.LocalStats())
        else: # fall through to device metrics
            if self.nodesByNum is not None:
                node = self.nodesByNum.get(self.localNode.nodeNum)
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
                        uptime_seconds = metrics.get("uptimeSeconds")
                        if uptime_seconds is not None:
                            r.device_metrics.uptime_seconds = uptime_seconds

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
        if p["decoded"]["portnum"] == "TELEMETRY_APP":
            self._acknowledgment.receivedTelemetry = True
            telemetry = telemetry_pb2.Telemetry()
            telemetry.ParseFromString(p["decoded"]["payload"])
            print("Telemetry received:")
            # Check if the telemetry message has the device_metrics field
            # This is the original code that was the default for --request-telemetry and is kept for compatibility
            if telemetry.HasField("device_metrics"):
                if telemetry.device_metrics.battery_level is not None:
                    print(f"Battery level: {telemetry.device_metrics.battery_level:.2f}%")
                if telemetry.device_metrics.voltage is not None:
                    print(f"Voltage: {telemetry.device_metrics.voltage:.2f} V")
                if telemetry.device_metrics.channel_utilization is not None:
                    print(
                        f"Total channel utilization: {telemetry.device_metrics.channel_utilization:.2f}%"
                    )
                if telemetry.device_metrics.air_util_tx is not None:
                    print(
                        f"Transmit air utilization: {telemetry.device_metrics.air_util_tx:.2f}%"
                    )
                if telemetry.device_metrics.uptime_seconds is not None:
                    print(f"Uptime: {telemetry.device_metrics.uptime_seconds} s")
            else:
                # this is the new code if --request-telemetry <type> is used.
                telemetry_dict = google.protobuf.json_format.MessageToDict(telemetry)
                for key, value in telemetry_dict.items():
                    if key != "time": # protobuf includes a time field that we don't print for device_metrics.
                        print(f"{key}:")
                        for sub_key, sub_value in value.items():
                            print(f"  {sub_key}: {sub_value}")

        elif p["decoded"]["portnum"] == "ROUTING_APP":
            if p["decoded"]["routing"]["errorReason"] == "NO_RESPONSE":
                our_exit(
                    "No response from node. At least firmware 2.1.22 is required on the destination node."
                )

    def onResponseWaypoint(self, p: dict):
        """on response for waypoint"""
        if p["decoded"]["portnum"] == "WAYPOINT_APP":
            self._acknowledgment.receivedWaypoint = True
            w = mesh_pb2.Waypoint()
            w.ParseFromString(p["decoded"]["payload"])
            print(f"Waypoint received: {w}")
        elif p["decoded"]["portnum"] == "ROUTING_APP":
            if p["decoded"]["routing"]["errorReason"] == "NO_RESPONSE":
                our_exit(
                    "No response from node. At least firmware 2.1.22 is required on the destination node."
                )

    def sendWaypoint(
        self,
        name,
        description,
        expire: int,
        waypoint_id: Optional[int] = None,
        latitude: float = 0.0,
        longitude: float = 0.0,
        destinationId: Union[int, str] = BROADCAST_ADDR,
        wantAck: bool = True,
        wantResponse: bool = False,
        channelIndex: int = 0,
    ): # pylint: disable=R0913
        """
        Send a waypoint packet to some other node (normally a broadcast)

        Returns the sent packet. The id field will be populated in this packet and
        can be used to track future message acks/naks.
        """
        w = mesh_pb2.Waypoint()
        w.name = name
        w.description = description
        w.expire = expire
        if waypoint_id is None:
            # Generate a waypoint's id, NOT a packet ID.
            # same algorithm as https://github.com/meshtastic/js/blob/715e35d2374276a43ffa93c628e3710875d43907/src/meshDevice.ts#L791
            seed = secrets.randbits(32)
            w.id = math.floor(seed * math.pow(2, -32) * 1e9)
            logging.debug(f"w.id:{w.id}")
        else:
            w.id = waypoint_id
        if latitude != 0.0:
            w.latitude_i = int(latitude * 1e7)
            logging.debug(f"w.latitude_i:{w.latitude_i}")
        if longitude != 0.0:
            w.longitude_i = int(longitude * 1e7)
            logging.debug(f"w.longitude_i:{w.longitude_i}")

        if wantResponse:
            onResponse = self.onResponseWaypoint
        else:
            onResponse = None

        d = self.sendData(
            w,
            destinationId,
            portNum=portnums_pb2.PortNum.WAYPOINT_APP,
            wantAck=wantAck,
            wantResponse=wantResponse,
            onResponse=onResponse,
            channelIndex=channelIndex,
        )
        if wantResponse:
            self.waitForWaypoint()
        return d

    def deleteWaypoint(
        self,
        waypoint_id: int,
        destinationId: Union[int, str] = BROADCAST_ADDR,
        wantAck: bool = True,
        wantResponse: bool = False,
        channelIndex: int = 0,
    ):
        """
        Send a waypoint deletion packet to some other node (normally a broadcast)

        NB: The id must be the waypoint's id and not the id of the packet creation.
        
        Returns the sent packet. The id field will be populated in this packet and
        can be used to track future message acks/naks.
        """
        p = mesh_pb2.Waypoint()
        p.id = waypoint_id
        p.expire = 0

        if wantResponse:
            onResponse = self.onResponseWaypoint
        else:
            onResponse = None

        d = self.sendData(
            p,
            destinationId,
            portNum=portnums_pb2.PortNum.WAYPOINT_APP,
            wantAck=wantAck,
            wantResponse=wantResponse,
            onResponse=onResponse,
            channelIndex=channelIndex,
        )
        if wantResponse:
            self.waitForWaypoint()
        return d

    def _addResponseHandler(
        self,
        requestId: int,
        callback: Callable[[dict], Any],
        ackPermitted: bool = False,
    ):
        self.responseHandlers[requestId] = ResponseHandler(
            callback=callback, ackPermitted=ackPermitted
        )

    def _sendPacket(
        self,
        meshPacket: mesh_pb2.MeshPacket,
        destinationId: Union[int,str]=BROADCAST_ADDR,
        wantAck: bool=False,
        hopLimit: Optional[int]=None,
        pkiEncrypted: Optional[bool]=False,
        publicKey: Optional[bytes]=None,
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

        if pkiEncrypted:
            meshPacket.pki_encrypted = True

        if publicKey is not None:
            meshPacket.public_key = publicKey

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
            raise MeshInterface.MeshInterfaceError(
                "Timed out waiting for interface config"
            )

    def waitForAckNak(self):
        """Wait for the ack/nak"""
        success = self._timeout.waitForAckNak(self._acknowledgment)
        if not success:
            raise MeshInterface.MeshInterfaceError(
                "Timed out waiting for an acknowledgment"
            )

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

    def waitForWaypoint(self):
        """Wait for waypoint"""
        success = self._timeout.waitForWaypoint(self._acknowledgment)
        if not success:
            raise MeshInterface.MeshInterfaceError("Timed out waiting for waypoint")

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

    def getPublicKey(self):
        """Get Public Key"""
        user = self.getMyUser()
        if user is not None:
            return user.get("publicKey", None)
        return None

    def _waitConnected(self, timeout=30.0):
        """Block until the initial node db download is complete, or timeout
        and raise an exception"""
        if not self.noProto:
            if not self.isConnected.wait(timeout):  # timeout after x seconds
                raise MeshInterface.MeshInterfaceError(
                    "Timed out waiting for connection completion"
                )

        # If we failed while connecting, raise the connection to the client
        if self.failure:
            raise self.failure

    def _generatePacketId(self) -> int:
        """Get a new unique packet ID"""
        if self.currentPacketId is None:
            raise MeshInterface.MeshInterfaceError(
                "Not connected yet, can not generate packet"
            )
        else:
            nextPacketId = (self.currentPacketId + 1) & 0xFFFFFFFF
            nextPacketId = nextPacketId & 0x3FF                           # == (0xFFFFFFFF >> 22), masks upper 22 bits
            randomPart = (random.randint(0, 0x3FFFFF) << 10) & 0xFFFFFFFF # generate number with 10 zeros at end
            self.currentPacketId = nextPacketId | randomPart              # combine
            return self.currentPacketId

    def _disconnected(self):
        """Called by subclasses to tell clients this interface has disconnected"""
        self.isConnected.clear()
        publishingThread.queueWork(
            lambda: pub.sendMessage("meshtastic.connection.lost", interface=self)
        )

    def sendHeartbeat(self):
        """Sends a heartbeat to the radio. Can be used to verify the connection is healthy."""
        p = mesh_pb2.ToRadio()
        p.heartbeat.CopyFrom(mesh_pb2.Heartbeat())
        self._sendToRadio(p)

    def _startHeartbeat(self):
        """We need to send a heartbeat message to the device every X seconds"""

        def callback():
            self.heartbeatTimer = None
            interval = 300
            logging.debug(f"Sending heartbeat, interval {interval} seconds")
            self.heartbeatTimer = threading.Timer(interval, callback)
            self.heartbeatTimer.start()
            self.sendHeartbeat()

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
        self._localChannels = (
            []
        )  # empty until we start getting channels pushed from the device (during config)

        startConfig = mesh_pb2.ToRadio()
        if self.configId is None or not self.noNodes:
            self.configId = random.randint(0, 0xFFFFFFFF)
            if self.configId == NODELESS_WANT_CONFIG_ID:
                self.configId = self.configId + 1
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
        logging.debug(
            f"in mesh_interface.py _handleFromRadio() fromRadioBytes: {fromRadioBytes}"
        )
        try:
            fromRadio.ParseFromString(fromRadioBytes)
        except Exception as ex:
            logging.error(
                    f"Error while parsing FromRadio bytes:{fromRadioBytes} {ex}"
            )
            traceback.print_exc()
            raise ex
        asDict = google.protobuf.json_format.MessageToDict(fromRadio)
        logging.debug(f"Received from radio: {fromRadio}")
        if fromRadio.HasField("my_info"):
            self.myInfo = fromRadio.my_info
            self.localNode.nodeNum = self.myInfo.my_node_num
            logging.debug(f"Received myinfo: {stripnl(fromRadio.my_info)}")

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
            # self.nodesByNum[node["num"]] = node
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
        elif fromRadio.HasField("log_record"):
            self._handleLogRecord(fromRadio.log_record)
        elif fromRadio.HasField("queueStatus"):
            self._handleQueueStatusFromRadio(fromRadio.queueStatus)

        elif fromRadio.HasField("mqttClientProxyMessage"):
            publishingThread.queueWork(
                lambda: pub.sendMessage(
                    "meshtastic.mqttclientproxymessage",
                    proxymessage=fromRadio.mqttClientProxyMessage,
                    interface=self,
                )
            )

        elif fromRadio.HasField("xmodemPacket"):
            publishingThread.queueWork(
                lambda: pub.sendMessage(
                    "meshtastic.xmodempacket",
                    packet=fromRadio.xmodemPacket,
                    interface=self,
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
            elif fromRadio.config.HasField("security"):
                self.localNode.localConfig.security.CopyFrom(
                    fromRadio.config.security
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

    def _nodeNumToId(self, num: int, isDest = True) -> Optional[str]:
        """Map a node node number to a node ID

        Arguments:
            num {int} -- Node number
            isDest {bool} -- True if the node number is a destination (to show broadcast address or unknown node)

        Returns:
            string -- Node ID
        """
        if num == BROADCAST_NUM:
            if isDest:
                return BROADCAST_ADDR
            else:
                return "Unknown"

        try:
            return self.nodesByNum[num]["user"]["id"]  # type: ignore[index]
        except:
            logging.debug(f"Node {num} not found for fromId")
            return None

    def _getOrCreateByNum(self, nodeNum):
        """Given a nodenum find the NodeInfo in the DB (or create if necessary)"""
        if nodeNum == BROADCAST_NUM:
            raise MeshInterface.MeshInterfaceError(
                "Can not create/find nodenum by the broadcast num"
            )

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
                    "hwModel": "UNSET",
                },
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
            asDict["fromId"] = self._nodeNumToId(asDict["from"], False)
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
                isAck = routing is not None and (
                    "errorReason" not in routing or routing["errorReason"] == "NONE"
                )
                # we keep the responseHandler in dict until we actually call it
                handler = self.responseHandlers.get(requestId, None)
                if handler is not None:
                    if (
                        (not isAck)
                        or handler.callback.__name__ == "onAckNak"
                        or handler.ackPermitted
                    ):
                        handler = self.responseHandlers.pop(requestId, None)
                        logging.debug(
                            f"Calling response handler for requestId {requestId}"
                        )
                        handler.callback(asDict)

        logging.debug(f"Publishing {topic}: packet={stripnl(asDict)} ")
        publishingThread.queueWork(
            lambda: pub.sendMessage(topic, packet=asDict, interface=self)
        )
