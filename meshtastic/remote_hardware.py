
from . import portnums_pb2, remote_hardware_pb2

"""
This is the client code to control/monitor simple hardware built into the 
meshtastic devices.  It is intended to be both a useful API/service and example
code for how you can connect to your own custom meshtastic services
"""
class RemoteHardwareClient:

    def __init__(self, iface):
        """
        Constructor

        iface is the already open MeshInterface instance
        """
        self.iface = iface


    def writeGPIOs(self, nodeid, mask, vals):
        """
        Write the specified vals bits to the device GPIOs.  Only bits in mask that
        are 1 will be changed
        """
        r = remote_hardware_pb2.HardwareMessage()
        r.typ = remote_hardware_pb2.HardwareMessage.Type.WRITE_GPIOS
        r.gpio_mask = mask
        r.gpio_value = vals
        return self.iface.sendData(r, nodeid, portnums_pb2.REMOTE_HARDWARE_APP, wantAck = True)

    def readGPIOs(self, nodeid, mask):
        """Read the specified bits from GPIO inputs on the device"""
        pass