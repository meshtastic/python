
from . import portnums_pb2, remote_hardware_pb2
from pubsub import pub

def onGPIOreceive(packet, interface):
    """Callback for received GPIO responses
    
    FIXME figure out how to do closures with methods in python"""
    pb = remote_hardware_pb2.HardwareMessage()
    pb.ParseFromString(packet["decoded"]["data"]["payload"])
    print(f"Received RemoteHardware typ={pb.typ}, gpio_value={pb.gpio_value}")

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

        pub.subscribe(onGPIOreceive, "meshtastic.receive.data.REMOTE_HARDWARE_APP")

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
        r = remote_hardware_pb2.HardwareMessage()
        r.typ = remote_hardware_pb2.HardwareMessage.Type.READ_GPIOS
        r.gpio_mask = mask
        return self.iface.sendData(r, nodeid, portnums_pb2.REMOTE_HARDWARE_APP, wantAck = True)

    def watchGPIOs(self, nodeid, mask):
        """Watch the specified bits from GPIO inputs on the device for changes"""
        r = remote_hardware_pb2.HardwareMessage()
        r.typ = remote_hardware_pb2.HardwareMessage.Type.WATCH_GPIOS
        r.gpio_mask = mask
        return self.iface.sendData(r, nodeid, portnums_pb2.REMOTE_HARDWARE_APP, wantAck = True)        
