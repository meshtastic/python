
from collections import defaultdict
import serial
import serial.tools.list_ports

"""Some devices such as a seger jlink we never want to accidentally open"""
blacklistVids = dict.fromkeys([0x1366])


def findPorts():
    """Find all ports that might have meshtastic devices

    Returns:
        list -- a list of device paths
    """
    l = list(map(lambda port: port.device,
                 filter(lambda port: port.vid != None and port.vid not in blacklistVids,
                        serial.tools.list_ports.comports())))
    l.sort()
    return l


class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
