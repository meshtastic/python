""" Serial interface class
"""
import logging
import platform
import os
import stat
import serial

import meshtastic.util
from .stream_interface import StreamInterface

class SerialInterface(StreamInterface):
    """Interface class for meshtastic devices over a serial link"""

    def __init__(self, devPath=None, debugOut=None, noProto=False, connectNow=True):
        """Constructor, opens a connection to a specified serial port, or if unspecified try to
        find one Meshtastic device by probing

        Keyword Arguments:
            devPath {string} -- A filepath to a device, i.e. /dev/ttyUSB0 (default: {None})
            debugOut {stream} -- If a stream is provided, any debug serial output from the device will be emitted to that stream. (default: {None})
        """

        if devPath is None:
            ports = meshtastic.util.findPorts()
            logging.debug(f"ports:{ports}")
            if len(ports) == 0:
                meshtastic.util.our_exit("Warning: No Meshtastic devices detected.")
            elif len(ports) > 1:
                message = "Warning: Multiple serial ports were detected so one serial port must be specified with the '--port'.\n"
                message += f"  Ports detected:{ports}"
                meshtastic.util.our_exit(message)
            else:
                devPath = ports[0]

        logging.debug(f"Connecting to {devPath}")

        # Note: we provide None for port here, because we will be opening it later
        self.stream = serial.Serial(
            None, 921600, exclusive=True, timeout=0.5, write_timeout=0)

        # rts=False Needed to prevent TBEAMs resetting on OSX, because rts is connected to reset
        self.stream.port = devPath

        # HACK: If the platform driving the serial port is unable to leave the RTS pin in high-impedance
        # mode, set RTS to false so that the device platform won't be reset spuriously.
        # Linux does this properly, so don't apply this hack on Linux (because it makes the reset button not work).
        if self._hostPlatformAlwaysDrivesUartRts():
            self.stream.rts = False
        self.stream.open()

        StreamInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, connectNow=connectNow)

    """true if platform driving the serial port is Windows Subsystem for Linux 1."""
    def _isWsl1(self):
        # WSL1 identifies itself as Linux, but has a special char device at /dev/lxss for use with session control,
        # e.g. /init.  We should treat WSL1 as Windows for the RTS-driving hack because the underlying platfrom
        # serial driver for the CP21xx still exhibits the buggy behavior.
        # WSL2 is not covered here, as it does not (as of 2021-May-25) support the appropriate functionality to
        # share or pass-through serial ports.
        try:
            # Claims to be Linux, but has /dev/lxss; must be WSL 1
            return platform.system() == 'Linux' and stat.S_ISCHR(os.stat('/dev/lxss').st_mode)
        except:
            # Couldn't stat /dev/lxss special device; not WSL1
            return False

    def _hostPlatformAlwaysDrivesUartRts(self):
        # OS-X/Windows seems to have a bug in its CP21xx serial drivers.  It ignores that we asked for no RTSCTS
        # control and will always drive RTS either high or low (rather than letting the CP102 leave
        # it as an open-collector floating pin).
        # TODO: When WSL2 supports USB passthrough, this will get messier.  If/when WSL2 gets virtual serial
        # ports that "share" the Windows serial port (and thus the Windows drivers), this code will need to be
        # updated to reflect that as well -- or if T-Beams get made with an alternate USB to UART bridge that has
        # a less buggy driver.
        return platform.system() != 'Linux' or self._isWsl1()
