#!/usr/bin/env python3
#
# Released Under GNU GPLv3
# Copyright 2025 Henri Shustak
#
# About :
#    This script will print messages as they arrive from a meshtastic node connected via serial port USB.
#    If you have multiple nodes attached, you will need to edit this script and specify the node to monitor.
#
# Requirements :
#    You will need to install python meshtastic libraries : https://github.com/meshtastic/python
#
# Version History :
#    1.0 - initial release
#    1.1 - added support for sender id and bug fixes
#    1.2 - added date and time reporting to each message
#    1.3 - bug fixes and improved error handling

import time
from datetime import datetime, timezone
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

def onReceive(packet, interface):
    # DEBUGGING
    # print(f"message arrived")
    # print(f"{packet}")
    # print(f"-----------------------------------------------------------------")
    try:
        if packet['decoded']['portnum'] == 'TEXT_MESSAGE_APP':
            try:
                message = packet['decoded']['text']
                try:
                    channel_num = packet['channel']
                except KeyError as e1:
                    channel_num = 0
                sender_id = packet['fromId']
                message_time = datetime.now().strftime(f"%a %b %d %Y %H:%M:%S {tz_name}")
                print(f"{message_time} : {channel_num} : {sender_id}  :  {message}")
            except KeyError as e2:
                print(f"unable to decode message")
                return
    except KeyError as e3:
        return

# configure the local time zone
tz_name = time.tzname[time.localtime().tm_isdst > 0]

# registrer for incomming messages
#pub.subscribe(onReceive, "meshtastic.receive.text")
pub.subscribe(onReceive, "meshtastic.receive")

# attempt to locate a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface = meshtastic.serial_interface.SerialInterface()

while True:
    time.sleep(10)  # wait for the next message
