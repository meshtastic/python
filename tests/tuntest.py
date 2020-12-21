# delete me eventually
# pip install python-pytuntap
# sudo ip tuntap del mode tun tun0

from tuntap import TunTap,Packet
import logging
from _thread import start_new_thread

"""A list of chatty UDP services we should never accidentally
forward to our slow network"""
udpBlacklist = {
    1900, # SSDP
    5353, # multicast DNS
}

def hexstr(barray):
    return ":".join('{:02x}'.format(x) for x in barray)

def readnet_u16(p, offset):
    """Read big endian u16 (network byte order)"""
    return p[offset] * 256 + p[offset + 1]

def readtest(tap):
    while not tap.quitting:
        p = tap.read()
        if not p:
            continue
        packet = Packet(data=p)
        if not packet.get_version()==4: # only consider IPV4 for now
            continue

        protocol = p[8 + 1]
        srcaddr = p[12:16]
        destaddr = p[16:20]
        subheader = 20
        ignore = False # Assume we will be forwarding the packet
        if protocol == 0x02: # IGMP
            ignore = True
            logging.debug("Ignoring IGMP packet")
        elif protocol == 0x11: # UDP
            srcport = readnet_u16(p, subheader)
            destport = readnet_u16(p, subheader + 2)
            logging.debug(f"udp srcport={srcport}, destport={destport}")
            if destport in udpBlacklist:
                ignore = True
                logging.debug(f"ignoring blacklisted UDP port {destport}")
        else:
            logging.warn(f"unexpected protocol 0x{protocol:02x}, srcadddr {hexstr(srcaddr)}")

        if not ignore:
            logging.debug(f"Forwarding packet bytes={hexstr(p)}")

        # reply to pings
        #pingback = p[:12]+p[16:20]+p[12:16]+p[20:]
        #tap.write(pingback)

logging.basicConfig(level=logging.DEBUG)

tun = TunTap(nic_type="Tun") # nic_name="tun0"
# tun.create()
tun.config(ip="10.115.1.2",mask="255.255.0.0")

start_new_thread(readtest,(tun,))
input("press return key to quit!")
tun.close()


