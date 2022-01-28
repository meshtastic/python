"""Remote hardware
"""
import logging
from pubsub import pub
from meshtastic import portnums_pb2, remote_hardware_pb2
from meshtastic.util import our_exit


def onGPIOreceive(packet, interface):
    """Callback for received GPIO responses
    """
    logging.debug(f"packet:{packet} interface:{interface}")
    gpioValue = 0
    hw = packet["decoded"]["remotehw"]
    if "gpioValue" in hw:
        gpioValue = hw["gpioValue"]
    else:
        if not "gpioMask" in hw:
            # we did get a reply, but due to protobufs, 0 for numeric value is not sent
            # see https://developers.google.com/protocol-buffers/docs/proto3#default
            # so, we set it here
            gpioValue = 0

    #print(f'mask:{interface.mask}')
    value = int(gpioValue) & int(interface.mask)
    print(f'Received RemoteHardware typ={hw["typ"]}, gpio_value={gpioValue} value={value}')
    interface.gotResponse = True


class RemoteHardwareClient:
    """
    This is the client code to control/monitor simple hardware built into the
    meshtastic devices.  It is intended to be both a useful API/service and example
    code for how you can connect to your own custom meshtastic services
    """

    def __init__(self, iface):
        """
        Constructor

        iface is the already open MeshInterface instance
        """
        self.iface = iface
        ch = iface.localNode.getChannelByName("gpio")
        if not ch:
            our_exit(
                "Warning: No channel named 'gpio' was found.\n"\
                "On the sending and receive nodes create a channel named 'gpio'.\n"\
                "For example, run '--ch-add gpio' on one device, then '--seturl' on\n"\
                "the other devices using the url from the device where the channel was added.")
        self.channelIndex = ch.index

        pub.subscribe(onGPIOreceive, "meshtastic.receive.remotehw")

    def _sendHardware(self, nodeid, r, wantResponse=False, onResponse=None):
        if not nodeid:
            our_exit(r"Warning: Must use a destination node ID for this operation (use --dest \!xxxxxxxxx)")
        return self.iface.sendData(r, nodeid, portnums_pb2.REMOTE_HARDWARE_APP,
                                   wantAck=True, channelIndex=self.channelIndex,
                                   wantResponse=wantResponse, onResponse=onResponse)

    def writeGPIOs(self, nodeid, mask, vals):
        """
        Write the specified vals bits to the device GPIOs.  Only bits in mask that
        are 1 will be changed
        """
        logging.debug(f'writeGPIOs nodeid:{nodeid} mask:{mask} vals:{vals}')
        r = remote_hardware_pb2.HardwareMessage()
        r.typ = remote_hardware_pb2.HardwareMessage.Type.WRITE_GPIOS
        r.gpio_mask = mask
        r.gpio_value = vals
        return self._sendHardware(nodeid, r)

    def readGPIOs(self, nodeid, mask, onResponse = None):
        """Read the specified bits from GPIO inputs on the device"""
        logging.debug(f'readGPIOs nodeid:{nodeid} mask:{mask}')
        r = remote_hardware_pb2.HardwareMessage()
        r.typ = remote_hardware_pb2.HardwareMessage.Type.READ_GPIOS
        r.gpio_mask = mask
        return self._sendHardware(nodeid, r, wantResponse=True, onResponse=onResponse)

    def watchGPIOs(self, nodeid, mask):
        """Watch the specified bits from GPIO inputs on the device for changes"""
        logging.debug(f'watchGPIOs nodeid:{nodeid} mask:{mask}')
        r = remote_hardware_pb2.HardwareMessage()
        r.typ = remote_hardware_pb2.HardwareMessage.Type.WATCH_GPIOS
        r.gpio_mask = mask
        self.iface.mask = mask
        return self._sendHardware(nodeid, r)
