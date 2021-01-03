# code for IP tunnel over a mesh
# Note python-pytuntap was too buggy
# using pip3 install pytap2
# make sure to "sudo setcap cap_net_admin+eip /usr/bin/python3.8" so python can access tun device without being root
# sudo ip tuntap del mode tun tun0
# sudo bin/run.sh --port /dev/ttyUSB0 --setch-shortfast
# sudo bin/run.sh --port /dev/ttyUSB0 --tunnel --debug
# ssh -Y root@192.168.10.151 (or dietpi), default password p
# ncat -e /bin/cat -k -u -l 1235 
# ncat -u 10.115.64.152 1235
# ping -c 1 -W 20 10.115.64.152
# ping -i 30 -W 30 10.115.64.152

# FIXME: use a more optimal MTU

from . import portnums_pb2
from pubsub import pub
import logging, threading

# A new non standard log level that is lower level than DEBUG
LOG_TRACE = 5

# fixme - find a way to move onTunnelReceive inside of the class
tunnelInstance = None

"""A list of chatty UDP services we should never accidentally
forward to our slow network"""
udpBlacklist = {
    1900, # SSDP
    5353, # multicast DNS
}

"""A list of TCP services to block"""
tcpBlacklist = {}

"""A list of protocols we ignore"""
protocolBlacklist = {
    0x02, # IGMP
	0x80, # Service-Specific Connection-Oriented Protocol in a Multilink and Connectionless Environment
}

def hexstr(barray):
    """Print a string of hex digits"""
    return ":".join('{:02x}'.format(x) for x in barray)

def ipstr(barray):
    """Print a string of ip digits"""
    return ".".join('{}'.format(x) for x in barray)

def readnet_u16(p, offset):
    """Read big endian u16 (network byte order)"""
    return p[offset] * 256 + p[offset + 1]

def onTunnelReceive(packet, interface):
    """Callback for received tunneled messages from mesh
    
    FIXME figure out how to do closures with methods in python"""
    tunnelInstance.onReceive(packet)

class Tunnel:
    """A TUN based IP tunnel over meshtastic"""
    
    def __init__(self, iface, subnet=None, netmask="255.255.0.0"):
        """
        Constructor

        iface is the already open MeshInterface instance
        subnet is used to construct our network number (normally 10.115.x.x)
        """

        if subnet is None:
            subnet = "10.115"

        self.iface = iface
        self.subnetPrefix = subnet

        global tunnelInstance
        tunnelInstance = self

        logging.info("Starting IP to mesh tunnel (you must be root for this *pre-alpha* feature to work).  Mesh members:")

        pub.subscribe(onTunnelReceive, "meshtastic.receive.data.IP_TUNNEL_APP")
        myAddr = self._nodeNumToIp(self.iface.myInfo.my_node_num)

        for node in self.iface.nodes.values():
            nodeId = node["user"]["id"]
            ip = self._nodeNumToIp(node["num"])
            logging.info(f"Node { nodeId } has IP address { ip }")        

        logging.debug("creating TUN device with MTU=200")
        # FIXME - figure out real max MTU, it should be 240 - the overhead bytes for SubPacket and Data
        from pytap2 import TapDevice
        self.tun = TapDevice(name="mesh")
        self.tun.up()
        self.tun.ifconfig(address=myAddr,netmask=netmask,mtu=200)
        logging.debug(f"starting TUN reader, our IP address is {myAddr}")
        self._rxThread = threading.Thread(target=self.__tunReader, args=(), daemon=True)
        self._rxThread.start()

    def onReceive(self, packet):
        p = packet["decoded"]["data"]["payload"]
        if packet["from"] == self.iface.myInfo.my_node_num:
            logging.debug("Ignoring message we sent")
        else:
            logging.debug(f"Received mesh tunnel message type={type(p)} len={len(p)}")
            # we don't really need to check for filtering here (sender should have checked), but this provides
            # useful debug printing on types of packets received
            if not self._shouldFilterPacket(p):
                self.tun.write(p)

    def _shouldFilterPacket(self, p):
        """Given a packet, decode it and return true if it should be ignored"""
        protocol = p[8 + 1]
        srcaddr = p[12:16]
        destAddr = p[16:20]
        subheader = 20
        ignore = False # Assume we will be forwarding the packet
        if protocol in protocolBlacklist:
            ignore = True
            logging.log(LOG_TRACE, f"Ignoring blacklisted protocol 0x{protocol:02x}")
        elif protocol == 0x01: # ICMP
            icmpType = p[20]
            icmpCode = p[21]
            checksum = p[22:24]
            logging.debug(f"forwarding ICMP message src={ipstr(srcaddr)}, dest={ipstr(destAddr)}, type={icmpType}, code={icmpCode}, checksum={checksum}")
            # reply to pings (swap src and dest but keep rest of packet unchanged)
            #pingback = p[:12]+p[16:20]+p[12:16]+p[20:]
            #tap.write(pingback)
        elif protocol == 0x11: # UDP
            srcport = readnet_u16(p, subheader)
            destport = readnet_u16(p, subheader + 2)
            if destport in udpBlacklist:
                ignore = True
                logging.log(LOG_TRACE, f"ignoring blacklisted UDP port {destport}")
            else:
                logging.debug(f"forwarding udp srcport={srcport}, destport={destport}")
        elif protocol == 0x06: # TCP
            srcport = readnet_u16(p, subheader)
            destport = readnet_u16(p, subheader + 2)
            if destport in tcpBlacklist:
                ignore = True
                logging.log(LOG_TRACE, f"ignoring blacklisted TCP port {destport}")
            else:
                logging.debug(f"forwarding tcp srcport={srcport}, destport={destport}")
        else:
            logging.warning(f"forwarding unexpected protocol 0x{protocol:02x}, src={ipstr(srcaddr)}, dest={ipstr(destAddr)}")

        return ignore

    def __tunReader(self):
        tap = self.tun
        logging.debug("TUN reader running")
        while True:
            p = tap.read()
            #logging.debug(f"IP packet received on TUN interface, type={type(p)}")
            destAddr = p[16:20]

            if not self._shouldFilterPacket(p):
                self.sendPacket(destAddr, p)

    def _ipToNodeId(self, ipAddr):
        # We only consider the last 16 bits of the nodenum for IP address matching
        ipBits = ipAddr[2] * 256 + ipAddr[3]

        if ipBits == 0xffff:
            return "^all"

        for node in self.iface.nodes.values():
            nodeNum = node["num"] & 0xffff
            # logging.debug(f"Considering nodenum 0x{nodeNum:x} for ipBits 0x{ipBits:x}")
            if (nodeNum) == ipBits:
                return node["user"]["id"]
        return None

    def _nodeNumToIp(self, nodeNum):
        return f"{self.subnetPrefix}.{(nodeNum >> 8) & 0xff}.{nodeNum & 0xff}"

    def sendPacket(self, destAddr, p):
        """Forward the provided IP packet into the mesh"""
        nodeId = self._ipToNodeId(destAddr)
        if nodeId is not None:
            logging.debug(f"Forwarding packet bytelen={len(p)} dest={ipstr(destAddr)}, destNode={nodeId}")
            self.iface.sendData(p, nodeId, portnums_pb2.IP_TUNNEL_APP, wantAck = False)
        else:
            logging.warning(f"Dropping packet because no node found for destIP={ipstr(destAddr)}")

    def close(self):
        self.tun.close()




