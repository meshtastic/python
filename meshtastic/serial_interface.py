""" Serial interface class
"""
import logging
import platform
import time

from typing import Optional

import serial # type: ignore[import-untyped]

import meshtastic.util
from meshtastic.stream_interface import StreamInterface

if platform.system() != "Windows":
    import termios


class SerialInterface(StreamInterface):
    """Interface class for meshtastic devices over a serial link"""

    def __init__(self, devPath: Optional[str]=None, debugOut=None, noProto=False, connectNow=True, noNodes: bool=False):
        """Constructor, opens a connection to a specified serial port, or if unspecified try to
        find one Meshtastic device by probing

        Keyword Arguments:
            devPath {string} -- A filepath to a device, i.e. /dev/ttyUSB0 (default: {None})
            debugOut {stream} -- If a stream is provided, any debug serial output from the device will be emitted to that stream. (default: {None})
        """
        self.noProto = noProto

        self.devPath: Optional[str] = devPath

        if self.devPath is None:
            ports = meshtastic.util.findPorts(True)
            logging.debug(f"ports:{ports}")
            if len(ports) == 0:
                print("No Serial Meshtastic device detected, attempting TCP connection on localhost.")
                return
            elif len(ports) > 1:
                message = "Warning: Multiple serial ports were detected so one serial port must be specified with the '--port'.\n"
                message += f"  Ports detected:{ports}"
                meshtastic.util.our_exit(message)
            else:
                self.devPath = ports[0]

        logging.debug(f"Connecting to {self.devPath}")

        # first we need to set the HUPCL so the device will not reboot based on RTS and/or DTR
        # see https://github.com/pyserial/pyserial/issues/124
        if platform.system() != "Windows":
            with open(self.devPath, encoding="utf8") as f:
                attrs = termios.tcgetattr(f)
                attrs[2] = attrs[2] & ~termios.HUPCL
                termios.tcsetattr(f, termios.TCSAFLUSH, attrs)
                f.close()
            time.sleep(0.1)

        self.stream = serial.Serial(
            self.devPath, 115200, exclusive=True, timeout=0.5, write_timeout=0
        )
        self.stream.flush()
        time.sleep(0.1)

        StreamInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, connectNow=connectNow, noNodes=noNodes
        )

    def close(self):
        """Close a connection to the device"""
        self.stream.flush()
        time.sleep(0.1)
        self.stream.flush()
        time.sleep(0.1)
        logging.debug("Closing Serial stream")
        StreamInterface.close(self)
