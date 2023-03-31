import time

import meshtastic

interface = (
    meshtastic.SerialInterface()
)  # By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface.sendText("hello mesh")
interface.close()
