# code for IP tunnel over a mesh
# Note python-pytuntap was too buggy
# using pip3 install pytap2
# make sure to "sudo setcap cap_net_admin+eip /usr/bin/python3.8" so python can access tun device without being root
# sudo ip tuntap del mode tun tun0

# FIXME: set MTU correctly
# select local ip address based on nodeid
# print known node ids as IP addresses
# change dev name to mesh

from . import portnums_pb2
from pubsub import pub
from pytap2 import TapDevice
import logging
import threading

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
    p = packet["decoded"]["data"]["payload"]
    logging.debug(f"Received tunnel message")


class Tunnel:
    """A TUN based IP tunnel over meshtastic"""
    
    def __init__(self, iface):
        """
        Constructor

        iface is the already open MeshInterface instance
        """
        self.iface = iface

        logging.info("Starting IP to mesh tunnel (you must be root for this pre-alpha feature to work)")

        pub.subscribe(onTunnelReceive, "meshtastic.receive.data.IP_TUNNEL_APP")

        logging.debug("creating TUN device")
        self.tun = TapDevice(mtu=200)
        # tun.create()
        self.tun.up()
        self.tun.ifconfig(address="10.115.1.2",netmask="255.255.0.0")
        logging.debug("starting TUN reader")
        self._rxThread = threading.Thread(target=self.__tunReader, args=(), daemon=True)
        self._rxThread.start()

    def __tunReader(self):
        tap = self.tun
        logging.debug("TUN reader running")
        while True:
            p = tap.read()

            protocol = p[8 + 1]
            srcaddr = p[12:16]
            destaddr = p[16:20]
            subheader = 20
            ignore = False # Assume we will be forwarding the packet
            if protocol in protocolBlacklist:
                ignore = True
                logging.debug(f"Ignoring blacklisted protocol 0x{protocol:02x}")
            elif protocol == 0x01: # ICMP
                logging.debug("forwarding ICMP message")
                # reply to pings (swap src and dest but keep rest of packet unchanged)
                #pingback = p[:12]+p[16:20]+p[12:16]+p[20:]
                #tap.write(pingback)
            elif protocol == 0x11: # UDP
                srcport = readnet_u16(p, subheader)
                destport = readnet_u16(p, subheader + 2)
                logging.debug(f"udp srcport={srcport}, destport={destport}")
                if destport in udpBlacklist:
                    ignore = True
                    logging.debug(f"ignoring blacklisted UDP port {destport}")
            elif protocol == 0x06: # TCP
                srcport = readnet_u16(p, subheader)
                destport = readnet_u16(p, subheader + 2)
                logging.debug(f"tcp srcport={srcport}, destport={destport}")
                if destport in tcpBlacklist:
                    ignore = True
                    logging.debug(f"ignoring blacklisted TCP port {destport}")
            else:
                logging.warning(f"unexpected protocol 0x{protocol:02x}, src={ipstr(srcaddr)}, dest={ipstr(destaddr)}")

            if not ignore:
                logging.debug(f"Forwarding packet bytelen={len(p)} src={ipstr(srcaddr)}, dest={ipstr(destaddr)}")

    def close(self):
        self.tun.close()




