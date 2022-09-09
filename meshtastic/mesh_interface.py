"""Mesh Interface class
"""
import sys
import random
import time
import logging
from typing import AnyStr
import threading
from datetime import datetime
import timeago
from tabulate import tabulate

import google.protobuf.json_format

from pubsub import pub
from google.protobuf.json_format import MessageToJson


import meshtastic.node
from meshtastic import portnums_pb2, mesh_pb2
from meshtastic.util import stripnl, Timeout, our_exit, remove_keys_from_dict, convert_mac_addr
from meshtastic.__init__ import LOCAL_ADDR, BROADCAST_NUM, BROADCAST_ADDR, ResponseHandler, publishingThread, OUR_APP_VERSION, protocols

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
            noProto -- If True, don't try to run our protocol on the
                       link - just be a dumb serial client.
        """
        self.debugOut = debugOut
        self.nodes = None  # FIXME
        self.isConnected = threading.Event()
        self.noProto = noProto
        self.localNode = meshtastic.node.Node(self, -1)  # We fixup nodenum later
        self.myInfo = None  # We don't have device info yet
        self.responseHandlers = {}  # A map from request ID to the handler
        self.failure = None  # If we've encountered a fatal exception it will be kept here
        self._timeout = Timeout()
        self.heartbeatTimer = None
        random.seed()  # FIXME, we should not clobber the random seedval here, instead tell user they must call it
        self.currentPacketId = random.randint(0, 0xffffffff)
        self.nodesByNum = None
        self.configId = None
        self.defaultHopLimit = 3
        self.gotResponse = False # used in gpio read
        self.mask = None # used in gpio read and gpio watch

    def close(self):
        """Shutdown this interface"""
        if self.heartbeatTimer:
            self.heartbeatTimer.cancel()

        self._sendDisconnect()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None and exc_value is not None:
            logging.error(f'An exception of type {exc_type} with value {exc_value} has occurred')
        if traceback is not None:
            logging.error(f'Traceback: {traceback}')
        self.close()

    def showInfo(self, file=sys.stdout): # pylint: disable=W0613
        """Show human readable summary about this object"""
        owner = f"Owner: {self.getLongName()} ({self.getShortName()})"
        myinfo = ''
        if self.myInfo:
            myinfo = f"\nMy info: {stripnl(MessageToJson(self.myInfo))}"
        mesh = "\nNodes in mesh:"
        nodes = ""
        if self.nodes:
            for n in self.nodes.values():
                # when the TBeam is first booted, it sometimes shows the raw data
                # so, we will just remove any raw keys
                keys_to_remove = ('raw', 'decoded', 'payload')
                n2 = remove_keys_from_dict(keys_to_remove, n)

                # if we have 'macaddr', re-format it
                if 'macaddr' in n2['user']:
                    val = n2['user']['macaddr']
                    # decode the base64 value
                    addr = convert_mac_addr(val)
                    n2['user']['macaddr'] = addr

                nodes = nodes + f"  {stripnl(n2)}"
        infos = owner + myinfo + mesh + nodes
        print(infos)
        return infos

    def showNodes(self, includeSelf=True, file=sys.stdout): # pylint: disable=W0613
        """Show table summary of nodes in mesh"""
        def formatFloat(value, precision=2, unit=''):
            """Format a float value with precsion."""
            return f'{value:.{precision}f}{unit}' if value else None

        def getLH(ts):
            """Format last heard"""
            return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else None

        def getTimeAgo(ts):
            """Format how long ago have we heard from this node (aka timeago)."""
            return timeago.format(datetime.fromtimestamp(ts), datetime.now()) if ts else None

        rows = []
        if self.nodes:
            logging.debug(f'self.nodes:{self.nodes}')
            for node in self.nodes.values():
                if not includeSelf and node['num'] == self.localNode.nodeNum:
                    continue

                row = {"N": 0}

                user = node.get('user')
                if user:
                    row.update({
                        "User": user['longName'],
                        "AKA":  user['shortName'],
                        "ID":   user['id'],
                    })

                pos = node.get('position')
                if pos:
                    row.update({
                        "Latitude":  formatFloat(pos.get("latitude"),     4, "°"),
                        "Longitude": formatFloat(pos.get("longitude"),    4, "°"),
                        "Altitude":  formatFloat(pos.get("altitude"),     0, " m"),
                        "Battery":   formatFloat(pos.get("batteryLevel"), 2, "%"),
                    })

                row.update({
                    "SNR":       formatFloat(node.get("snr"), 2, " dB"),
                    "LastHeard": getLH(node.get("lastHeard")),
                    "Since":     getTimeAgo(node.get("lastHeard")),
                })

                rows.append(row)

        rows.sort(key=lambda r: r.get('LastHeard') or '0000', reverse=True)
        for i, row in enumerate(rows):
            row['N'] = i+1

        table = tabulate(rows, headers='keys', missingval='N/A', tablefmt='fancy_grid')
        print(table)
        return table


    def getNode(self, nodeId):
        """Return a node object which contains device settings and channel info"""
        if nodeId in (LOCAL_ADDR, BROADCAST_ADDR):
            return self.localNode
        else:
            n = meshtastic.node.Node(self, nodeId)
            logging.debug("About to requestConfig")
            n.requestConfig()
            if not n.waitForConfig():
                our_exit("Error: Timed out waiting for node config")
            return n

    def sendText(self, text: AnyStr,
                 destinationId=BROADCAST_ADDR,
                 wantAck=False,
                 wantResponse=False,
                 hopLimit=None,
                 onResponse=None,
                 channelIndex=0):
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
        if hopLimit is None:
            hopLimit = self.defaultHopLimit

        return self.sendData(text.encode("utf-8"), destinationId,
                             portNum=portnums_pb2.PortNum.TEXT_MESSAGE_APP,
                             wantAck=wantAck,
                             wantResponse=wantResponse,
                             hopLimit=hopLimit,
                             onResponse=onResponse,
                             channelIndex=channelIndex)

    def sendData(self, data, destinationId=BROADCAST_ADDR,
                 portNum=portnums_pb2.PortNum.PRIVATE_APP, wantAck=False,
                 wantResponse=False,
                 hopLimit=None,
                 onResponse=None,
                 channelIndex=0):
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
            channelIndex - channel number to use

        Returns the sent packet. The id field will be populated in this packet
        and can be used to track future message acks/naks.
        """
        if hopLimit is None:
            hopLimit = self.defaultHopLimit

        if getattr(data, "SerializeToString", None):
            logging.debug(f"Serializing protobuf as data: {stripnl(data)}")
            data = data.SerializeToString()

        logging.debug(f"len(data): {len(data)}")
        logging.debug(f"mesh_pb2.Constants.DATA_PAYLOAD_LEN: {mesh_pb2.Constants.DATA_PAYLOAD_LEN}")
        if len(data) > mesh_pb2.Constants.DATA_PAYLOAD_LEN:
            raise Exception("Data payload too big")

        if portNum == portnums_pb2.PortNum.UNKNOWN_APP:  # we are now more strict wrt port numbers
            our_exit("Warning: A non-zero port number must be specified")

        meshPacket = mesh_pb2.MeshPacket()
        meshPacket.channel = channelIndex
        meshPacket.decoded.payload = data
        meshPacket.decoded.portnum = portNum
        meshPacket.decoded.want_response = wantResponse
        meshPacket.id = self._generatePacketId()

        if onResponse is not None:
            self._addResponseHandler(meshPacket.id, onResponse)
        p = self._sendPacket(meshPacket, destinationId,
                             wantAck=wantAck, hopLimit=hopLimit)
        return p

    def sendPosition(self, latitude=0.0, longitude=0.0, altitude=0, timeSec=0,
                     destinationId=BROADCAST_ADDR, wantAck=False, wantResponse=False):
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
            logging.debug(f'p.latitude_i:{p.latitude_i}')

        if longitude != 0.0:
            p.longitude_i = int(longitude / 1e-7)
            logging.debug(f'p.longitude_i:{p.longitude_i}')

        if altitude != 0:
            p.altitude = int(altitude)
            logging.debug(f'p.altitude:{p.altitude}')

        if timeSec == 0:
            timeSec = time.time()  # returns unix timestamp in seconds
        p.time = int(timeSec)
        logging.debug(f'p.time:{p.time}')

        return self.sendData(p, destinationId,
                             portNum=portnums_pb2.PortNum.POSITION_APP,
                             wantAck=wantAck,
                             wantResponse=wantResponse)

    def _addResponseHandler(self, requestId, callback):
        self.responseHandlers[requestId] = ResponseHandler(callback)

    def _sendPacket(self, meshPacket,
                    destinationId=BROADCAST_ADDR,
                    wantAck=False, hopLimit=None):
        """Send a MeshPacket to the specified node (or if unspecified, broadcast).
        You probably don't want this - use sendData instead.

        Returns the sent packet. The id field will be populated in this packet and
        can be used to track future message acks/naks.
        """
        if hopLimit is None:
            hopLimit = self.defaultHopLimit

        # We allow users to talk to the local node before we've completed the full connection flow...
        if(self.myInfo is not None and destinationId != self.myInfo.my_node_num):
            self._waitConnected()

        toRadio = mesh_pb2.ToRadio()

        nodeNum = 0
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
                if not node:
                    our_exit(f"Warning: NodeId {destinationId} not found in DB")
                nodeNum = node['num']
            else:
                logging.warning("Warning: There were no self.nodes.")

        meshPacket.to = nodeNum
        meshPacket.want_ack = wantAck
        meshPacket.hop_limit = hopLimit

        # if the user hasn't set an ID for this packet (likely and recommended),
        # we should pick a new unique ID so the message can be tracked.
        if meshPacket.id == 0:
            meshPacket.id = self._generatePacketId()

        toRadio.packet.CopyFrom(meshPacket)
        if self.noProto:
            logging.warning(f"Not sending packet because protocol use is disabled by noProto")
        else:
            logging.debug(f"Sending packet: {stripnl(meshPacket)}")
            self._sendToRadio(toRadio)
        return meshPacket

    def waitForConfig(self):
        """Block until radio config is received. Returns True if config has been received."""
        success = self._timeout.waitForSet(self, attrs=('myInfo', 'nodes')) and self.localNode.waitForConfig()
        if not success:
            raise Exception("Timed out waiting for interface config")

    def getMyNodeInfo(self):
        """Get info about my node."""
        if self.myInfo is None:
            return None
        logging.debug(f'self.nodesByNum:{self.nodesByNum}')
        return self.nodesByNum.get(self.myInfo.my_node_num)

    def getMyUser(self):
        """Get user"""
        nodeInfo = self.getMyNodeInfo()
        if nodeInfo is not None:
            return nodeInfo.get('user')
        return None

    def getLongName(self):
        """Get long name"""
        user = self.getMyUser()
        if user is not None:
            return user.get('longName', None)
        return None

    def getShortName(self):
        """Get short name"""
        user = self.getMyUser()
        if user is not None:
            return user.get('shortName', None)
        return None

    def _waitConnected(self, timeout=15.0):
        """Block until the initial node db download is complete, or timeout
        and raise an exception"""
        if not self.noProto:
            if not self.isConnected.wait(timeout):  # timeout after x seconds
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
        publishingThread.queueWork(lambda: pub.sendMessage("meshtastic.connection.lost", interface=self))

    def _startHeartbeat(self):
        """We need to send a heartbeat message to the device every X seconds"""
        def callback():
            self.heartbeatTimer = None
            prefs = self.localNode.localConfig
            i = prefs.power.ls_secs / 2
            logging.debug(f"Sending heartbeat, interval {i}")
            if i != 0:
                self.heartbeatTimer = threading.Timer(i, callback)
                self.heartbeatTimer.start()
                p = mesh_pb2.ToRadio()
                self._sendToRadio(p)

        callback()  # run our periodic callback now, it will make another timer if necessary

    def _connected(self):
        """Called by this class to tell clients we are now fully connected to a node
        """
        # (because I'm lazy) _connected might be called when remote Node
        # objects complete their config reads, don't generate redundant isConnected
        # for the local interface
        if not self.isConnected.is_set():
            self.isConnected.set()
            self._startHeartbeat()
            publishingThread.queueWork(lambda: pub.sendMessage("meshtastic.connection.established", interface=self))

    def _startConfig(self):
        """Start device packets flowing"""
        self.myInfo = None
        self.nodes = {}  # nodes keyed by ID
        self.nodesByNum = {}  # nodes keyed by nodenum

        startConfig = mesh_pb2.ToRadio()
        self.configId = random.randint(0, 0xffffffff)
        startConfig.want_config_id = self.configId
        self._sendToRadio(startConfig)

    def _sendDisconnect(self):
        """Tell device we are done using it"""
        m = mesh_pb2.ToRadio()
        m.disconnect = True
        self._sendToRadio(m)

    def _sendToRadio(self, toRadio):
        """Send a ToRadio protobuf to the device"""
        if self.noProto:
            logging.warning(f"Not sending packet because protocol use is disabled by noProto")
        else:
            #logging.debug(f"Sending toRadio: {stripnl(toRadio)}")
            self._sendToRadioImpl(toRadio)

    def _sendToRadioImpl(self, toRadio):
        """Send a ToRadio protobuf to the device"""
        logging.error(f"Subclass must provide toradio: {toRadio}")

    def _handleConfigComplete(self):
        """
        Done with initial config messages, now send regular MeshPackets
        to ask for settings and channels
        """
        self.localNode.requestConfig()

    def _handleFromRadio(self, fromRadioBytes):
        """
        Handle a packet that arrived from the radio(update model and publish events)

        Called by subclasses."""
        fromRadio = mesh_pb2.FromRadio()
        fromRadio.ParseFromString(fromRadioBytes)
        logging.debug(f"in mesh_interface.py _handleFromRadio() fromRadioBytes: {fromRadioBytes}")
        asDict = google.protobuf.json_format.MessageToDict(fromRadio)
        logging.debug(f"Received from radio: {fromRadio}")
        if fromRadio.HasField("my_info"):
            self.myInfo = fromRadio.my_info
            self.localNode.nodeNum = self.myInfo.my_node_num
            logging.debug(f"Received myinfo: {stripnl(fromRadio.my_info)}")

            failmsg = None
            # Check for app too old
            if self.myInfo.min_app_version > OUR_APP_VERSION:
                failmsg = "This device needs a newer python client, run 'pip install --upgrade meshtastic'."\
                          "For more information see https://tinyurl.com/5bjsxu32"

            # check for firmware too old
            if self.myInfo.max_channels == 0:
                failmsg = "This version of meshtastic-python requires device firmware version 1.2 or later. "\
                          "For more information see https://tinyurl.com/5bjsxu32"

            if failmsg:
                self.failure = Exception(failmsg)
                self.isConnected.set()  # let waitConnected return this exception
                self.close()

        elif fromRadio.HasField("node_info"):
            node = asDict["nodeInfo"]
            try:
                newpos = self._fixupPosition(node["position"])
                node["position"] = newpos
            except:
                logging.debug("Node without position")

            logging.debug(f"Received nodeinfo: {node}")

            self.nodesByNum[node["num"]] = node
            if "user" in node:  # Some nodes might not have user/ids assigned yet
                if "id" in node["user"]:
                    self.nodes[node["user"]["id"]] = node
            publishingThread.queueWork(lambda: pub.sendMessage("meshtastic.node.updated",
                                                               node=node, interface=self))
        elif fromRadio.config_complete_id == self.configId:
            # we ignore the config_complete_id, it is unneeded for our
            # stream API fromRadio.config_complete_id
            logging.debug(f"Config complete ID {self.configId}")
            self._handleConfigComplete()

        elif fromRadio.HasField("packet"):
            self._handlePacketFromRadio(fromRadio.packet)

        elif fromRadio.rebooted:
            # Tell clients the device went away.  Careful not to call the overridden
            # subclass version that closes the serial port
            MeshInterface._disconnected(self)

            self._startConfig()  # redownload the node db etc...

        elif fromRadio.config or fromRadio.moduleConfig:
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
                self.localNode.localConfig.bluetooth.CopyFrom(fromRadio.config.bluetooth)

            elif fromRadio.moduleConfig.HasField("mqtt"):
                self.localNode.moduleConfig.mqtt.CopyFrom(fromRadio.moduleConfig.mqtt)
            elif fromRadio.moduleConfig.HasField("serial"):
                self.localNode.moduleConfig.serial.CopyFrom(fromRadio.moduleConfig.serial)
            elif fromRadio.moduleConfig.HasField("external_notification"):
                self.localNode.moduleConfig.external_notification.CopyFrom(fromRadio.moduleConfig.external_notification)
            elif fromRadio.moduleConfig.HasField("range_test"):
                self.localNode.moduleConfig.range_test.CopyFrom(fromRadio.moduleConfig.range_test)
            elif fromRadio.moduleConfig.HasField("telemetry"):
                self.localNode.moduleConfig.telemetry.CopyFrom(fromRadio.moduleConfig.telemetry)
            elif fromRadio.moduleConfig.HasField("canned_message"):
                self.localNode.moduleConfig.canned_message.CopyFrom(fromRadio.moduleConfig.canned_message)

        else:
            logging.debug("Unexpected FromRadio payload")

    def _fixupPosition(self, position):
        """Convert integer lat/lon into floats

        Arguments:
            position {Position dictionary} -- object to fix up
        Returns the position with the updated keys
        """
        if "latitudeI" in position:
            position["latitude"] = position["latitudeI"] * 1e-7
        if "longitudeI" in position:
            position["longitude"] = position["longitudeI"] * 1e-7
        return position

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
            logging.error(f"Device returned a packet we sent, ignoring: {stripnl(asDict)}")
            print(f"Error: Device returned a packet we sent, ignoring: {stripnl(asDict)}")
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
        if 'decoded' in asDict:
            decoded = asDict["decoded"]
            # The default MessageToDict converts byte arrays into base64 strings.
            # We don't want that - it messes up data payload.  So slam in the correct
            # byte array.
            decoded["payload"] = meshPacket.decoded.payload

        # UNKNOWN_APP is the default protobuf portnum value, and therefore if not
        # set it will not be populated at all to make API usage easier, set
        # it to prevent confusion
        if decoded and "portnum" not in decoded:
            new_portnum = portnums_pb2.PortNum.Name(portnums_pb2.PortNum.UNKNOWN_APP)
            decoded["portnum"] = new_portnum
            logging.warning(f"portnum was not in decoded. Setting to:{new_portnum}")

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
