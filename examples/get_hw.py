"""Simple program to demo how to use meshtastic library.
   To run: python examples/get_hw.py
"""

import sys

import meshtastic
import meshtastic.serial_interface

# simple arg check
if len(sys.argv) != 1:
    print(f"usage: {sys.argv[0]}")
    print("Print the hardware model for the local node.")
    sys.exit(3)

iface = meshtastic.serial_interface.SerialInterface()
if iface.nodes:
    for n in iface.nodes.values():
        if n["num"] == iface.myInfo.my_node_num:
            print(n["user"]["hwModel"])
iface.close()
