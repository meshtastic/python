#!/usr/bin/env python3
#
# Released Under GNU GPLv3
# Copyright 2025 Henri Shustak
#
# About :
#    This script will print messages as they arrive from a meshtastic node connected via serial port USB.
#    If you have multiple nodes attached, you will need to edit this script and specify the node to monitor.
#    https://gist.github.com/henri/a6584d55813f971e5b1a4ee940c07d25
#
# Requirements : 
#    You will need to install python meshtastic libraries : https://github.com/meshtastic/python
#
# Version History :
#    1.0 - initial release
#    1.1 - added support for sender id and bug fixs

import time
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

def onReceive(packet, interface):
    # DEBUGGING
    # print(f"message arrived")
    # print(f"{packet}")
    try:
        if packet['decoded']['portnum'] == 'TEXT_MESSAGE_APP':
            message = packet['decoded']['text']
            channel_num = packet['channel']
            sender_id = packet['fromId']
            print(f"{channel_num} : {sender_id}  :  {message}")
    except KeyError as e:
        print(f"unable to decode message")
        return

#pub.subscribe(onReceive, "meshtastic.receive.text")
pub.subscribe(onReceive, "meshtastic.receive")

# try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface = meshtastic.serial_interface.SerialInterface()

while True:
    time.sleep(10)  # wait for the next message

