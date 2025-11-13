""" Serial interface class
"""
# pylint: disable=R0917
import logging
import sys
import time
from io import TextIOWrapper

from typing import List, Optional

import serial # type: ignore[import-untyped]

import meshtastic.util
from meshtastic.stream_interface import StreamInterface

logger = logging.getLogger(__name__)

class SerialInterface(StreamInterface):
    """Interface class for meshtastic devices over a serial link"""

    def __init__(
        self,
        devPath: Optional[str] = None,
        debugOut=None,
        noProto: bool = False,
        connectNow: bool = True,
        noNodes: bool = False,
        timeout: int = 300
    ) -> None:
        """Constructor, opens a connection to a specified serial port, or if unspecified try to
        find one Meshtastic device by probing

        Keyword Arguments:
            devPath {string} -- A filepath to a device, i.e. /dev/ttyUSB0 (default: {None})
            debugOut {stream} -- If a stream is provided, any debug serial output from the device will be emitted to that stream. (default: {None})
            timeout -- How long to wait for replies (default: 300 seconds)
        """
        self.noProto = noProto

        self.devPath: Optional[str] = devPath

        if self.devPath is None:
            ports: List[str] = meshtastic.util.findPorts(True)
            logger.debug(f"ports:{ports}")
            if len(ports) == 0:
                print("No Serial Meshtastic device detected, attempting TCP connection on localhost.")
                return
            elif len(ports) > 1:
                message: str = "Warning: Multiple serial ports were detected so one serial port must be specified with the '--port'.\n"
                message += f"  Ports detected:{ports}"
                meshtastic.util.our_exit(message)
            else:
                self.devPath = ports[0]

        logger.debug(f"Connecting to {self.devPath}")

        if sys.platform != "win32":
            with open(self.devPath, encoding="utf8") as f:
                self._set_hupcl_with_termios(f)
            time.sleep(0.1)

        self.stream = serial.Serial(
            self.devPath, 115200, exclusive=True, timeout=0.5, write_timeout=0
        )
        self.stream.flush()	# type: ignore[attr-defined]
        time.sleep(0.1)

        StreamInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, connectNow=connectNow, noNodes=noNodes, timeout=timeout
        )

    def _set_hupcl_with_termios(self, f: TextIOWrapper):
        """first we need to set the HUPCL so the device will not reboot based on RTS and/or DTR
        see https://github.com/pyserial/pyserial/issues/124
        """
        if sys.platform == "win32":
            return

        import termios  # pylint: disable=C0415,E0401
        attrs = termios.tcgetattr(f)
        attrs[2] = attrs[2] & ~termios.HUPCL
        termios.tcsetattr(f, termios.TCSAFLUSH, attrs)

    def __repr__(self):
        rep = f"SerialInterface(devPath={self.devPath!r}"
        if hasattr(self, 'debugOut') and self.debugOut is not None:
            rep += f", debugOut={self.debugOut!r}"
        if self.noProto:
            rep += ", noProto=True"
        if hasattr(self, 'noNodes') and self.noNodes:
            rep += ", noNodes=True"
        rep += ")"
        return rep

    def close(self) -> None:
        """Close a connection to the device"""
        if self.stream:  # Stream can be null if we were already closed
            self.stream.flush()  # FIXME: why are there these  two flushes with 100ms sleeps?  This shouldn't be necessary
            time.sleep(0.1)
            self.stream.flush()
            time.sleep(0.1)
        logger.debug("Closing Serial stream")
        StreamInterface.close(self)
