"""Simple program to demo how to use meshtastic library.
   To run: python examples/hello_world_serial.py
"""

import sys

import meshtastic
import meshtastic.serial_interface

# simple arg check
if len(sys.argv) < 2:
    print(f"usage: {sys.argv[0]} message")
    sys.exit(3)

# By default will try to find a meshtastic device,
# otherwise provide a device path like /dev/ttyUSB0
iface = meshtastic.serial_interface.SerialInterface()
iface.sendText(sys.argv[1])
iface.close()
