"""Simple program to demo how to use meshtastic library.
   To run: python examples/pub_sub_example.py
"""

import sys

from pubsub import pub

import meshtastic
import meshtastic.tcp_interface

# simple arg check
if len(sys.argv) < 2:
    print(f"usage: {sys.argv[0]} host")
    sys.exit(1)


def onConnection(interface, topic=pub.AUTO_TOPIC):  # pylint: disable=unused-argument
    """This is called when we (re)connect to the radio."""
    print(interface.myInfo)
    interface.close()


pub.subscribe(onConnection, "meshtastic.connection.established")

try:
    iface = meshtastic.tcp_interface.TCPInterface(sys.argv[1])
except:
    print(f"Error: Could not connect to {sys.argv[1]}")
    sys.exit(1)
