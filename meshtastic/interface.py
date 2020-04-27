
import serial
import threading
import logging
import sys

"""

TODO: 
* use port enumeration to find ports https://pyserial.readthedocs.io/en/latest/shortintro.html

"""


class MeshInterface:
    """Interface class for meshtastic devices"""

    def __init__(self, devPath):
        """Constructor, opens a connection to a specified serial port"""
        logging.debug(f"Connecting to {devPath}")
        self.debugOut = sys.stdout
        self.rxBuf = bytes()  # empty
        self.stream = serial.Serial(devPath, 921600)
        self.rxThread = threading.Thread(target=self.__reader, args=())
        self.rxThread.start()

    def close(self):
        self.stream.close()  # This will cause our reader thread to exit

    def __reader(self):
        """The reader thread that reads bytes from our stream"""
        while True:
            b = read(1)
            self.debugOut.write(b)
