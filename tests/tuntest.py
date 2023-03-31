# delete me eventually
# Note python-pytuntap was too buggy
# using pip3 install pytap2
# make sure to "sudo setcap cap_net_admin+eip /usr/bin/python3.8" so python can access tun device without being root
# sudo ip tuntap del mode tun tun0

# FIXME: set MTU correctly
# select local ip address based on nodeid
# print known node ids as IP addresses

import logging
from _thread import start_new_thread

from pytap2 import TapDevice

"""A list of chatty UDP services we should never accidentally
forward to our slow network"""
udpBlacklist = {
    1900,  # SSDP
    5353,  # multicast DNS
}

"""A list of TCP services to block"""
tcpBlacklist = {}

"""A list of protocols we ignore"""
protocolBlacklist = {
    0x02,  # IGMP
    0x80,  # Service-Specific Connection-Oriented Protocol in a Multilink and Connectionless Environment
}


def hexstr(barray):
    """Print a string of hex digits"""
    return ":".join("{:02x}".format(x) for x in barray)


def ipstr(barray):
    """Print a string of ip digits"""
    return ".".join("{}".format(x) for x in barray)


def readnet_u16(p, offset):
    """Read big endian u16 (network byte order)"""
    return p[offset] * 256 + p[offset + 1]


def readtest(tap):
    while True:
        p = tap.read()

        protocol = p[8 + 1]
        srcaddr = p[12:16]
        destaddr = p[16:20]
        subheader = 20
        ignore = False  # Assume we will be forwarding the packet
        if protocol in protocolBlacklist:
            ignore = True
            logging.debug(f"Ignoring blacklisted protocol 0x{protocol:02x}")
        elif protocol == 0x01:  # ICMP
            logging.warn("Generating fake ping reply")
            # reply to pings (swap src and dest but keep rest of packet unchanged)
            pingback = p[:12] + p[16:20] + p[12:16] + p[20:]
            tap.write(pingback)
        elif protocol == 0x11:  # UDP
            srcport = readnet_u16(p, subheader)
            destport = readnet_u16(p, subheader + 2)
            logging.debug(f"udp srcport={srcport}, destport={destport}")
            if destport in udpBlacklist:
                ignore = True
                logging.debug(f"ignoring blacklisted UDP port {destport}")
        elif protocol == 0x06:  # TCP
            srcport = readnet_u16(p, subheader)
            destport = readnet_u16(p, subheader + 2)
            logging.debug(f"tcp srcport={srcport}, destport={destport}")
            if destport in tcpBlacklist:
                ignore = True
                logging.debug(f"ignoring blacklisted TCP port {destport}")
        else:
            logging.warning(
                f"unexpected protocol 0x{protocol:02x}, src={ipstr(srcaddr)}, dest={ipstr(destaddr)}"
            )

        if not ignore:
            logging.debug(
                f"Forwarding packet bytelen={len(p)} src={ipstr(srcaddr)}, dest={ipstr(destaddr)}"
            )


logging.basicConfig(level=logging.DEBUG)

tun = TapDevice(mtu=200)
# tun.create()
tun.up()
tun.ifconfig(address="10.115.1.2", netmask="255.255.0.0")

start_new_thread(readtest, (tun,))
input("press return key to quit!")
tun.close()
