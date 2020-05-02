
import serial
import serial.tools.list_ports


def findPorts():
    """Find all ports that might have meshtastic devices

    Returns:
        list -- a list of device paths
    """
    l = list(map(lambda port: port.device,
                 filter(lambda port: port.vid != None,
                        serial.tools.list_ports.comports())))
    l.sort()
    return l
