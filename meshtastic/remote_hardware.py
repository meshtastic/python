
from pubsub import pub
from . import portnums_pb2, remote_hardware_pb2


def onGPIOreceive(packet, interface):
    """Callback for received GPIO responses

    FIXME figure out how to do closures with methods in python"""
    hw = packet["decoded"]["remotehw"]
    print(f'Received RemoteHardware typ={hw["typ"]}, gpio_value={hw["gpioValue"]}')


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
            raise Exception(
                "No gpio channel found, please create on the sending and receive nodes to use this (secured) service (--ch-add gpio --info then --seturl)")
        self.channelIndex = ch.index

        pub.subscribe(
            onGPIOreceive, "meshtastic.receive.remotehw")

    def _sendHardware(self, nodeid, r, wantResponse=False, onResponse=None):
        if not nodeid:
            raise Exception(
                "You must set a destination node ID for this operation (use --dest \!xxxxxxxxx)")
        return self.iface.sendData(r, nodeid, portnums_pb2.REMOTE_HARDWARE_APP,
                                   wantAck=True, channelIndex=self.channelIndex, wantResponse=wantResponse, onResponse=onResponse)

    def writeGPIOs(self, nodeid, mask, vals):
        """
        Write the specified vals bits to the device GPIOs.  Only bits in mask that
        are 1 will be changed
        """
        r = remote_hardware_pb2.HardwareMessage()
        r.typ = remote_hardware_pb2.HardwareMessage.Type.WRITE_GPIOS
        r.gpio_mask = mask
        r.gpio_value = vals
        return self._sendHardware(nodeid, r)

    def readGPIOs(self, nodeid, mask, onResponse = None):
        """Read the specified bits from GPIO inputs on the device"""
        r = remote_hardware_pb2.HardwareMessage()
        r.typ = remote_hardware_pb2.HardwareMessage.Type.READ_GPIOS
        r.gpio_mask = mask
        return self._sendHardware(nodeid, r, wantResponse=True, onResponse=onResponse)

    def watchGPIOs(self, nodeid, mask):
        """Watch the specified bits from GPIO inputs on the device for changes"""
        r = remote_hardware_pb2.HardwareMessage()
        r.typ = remote_hardware_pb2.HardwareMessage.Type.WATCH_GPIOS
        r.gpio_mask = mask
        return self._sendHardware(nodeid, r)
