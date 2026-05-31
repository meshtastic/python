"""Simple program to demo how to use meshtastic library.
   To run: python examples/pub_sub_example2.py
"""

import sys
import time

from meshtastic.tcp_interface import TCPInterface

from pubsub import pub

# simple arg check
if len(sys.argv) < 2:
    print(f"usage: {sys.argv[0]} host")
    sys.exit(1)


def onReceive(packet, interface):  # pylint: disable=unused-argument
    """called when a packet arrives"""
    print(f"Received: {packet}")


def onConnection(interface, topic=pub.AUTO_TOPIC):  # pylint: disable=unused-argument
    """called when we (re)connect to the radio"""
    # defaults to broadcast, specify a destination ID if you wish
    interface.sendText("hello mesh")


pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")

iface=None
try:
    iface = TCPInterface(hostname=sys.argv[1])
    while True:
        time.sleep(1000)
except Exception as ex:
    print(f"Error: Could not connect to {sys.argv[1]} {ex}")
    raise
finally:
    if iface:
        iface.close()
