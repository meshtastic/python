"""Simple program to demo how to use meshtastic library.
   To run: python examples/set_owner.py Bobby 333
"""

import sys

import meshtastic
import meshtastic.serial_interface

# simple arg check
if len(sys.argv) < 2:
    print(f"usage: {sys.argv[0]} long_name [short_name]")
    sys.exit(3)

iface = meshtastic.serial_interface.SerialInterface()
long_name = sys.argv[1]
short_name = None
if len(sys.argv) > 2:
    short_name = sys.argv[2]
iface.localNode.setOwner(long_name, short_name)
iface.close()
