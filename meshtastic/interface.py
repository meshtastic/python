
import serial
import threading
import logging
import sys

"""

TODO: 
* use port enumeration to find ports https://pyserial.readthedocs.io/en/latest/shortintro.html


Contains a reader thread that is always trying to read on the serial port.

methods:

- constructor(serialPort)
- sendData(destinationId, bytes, variant)
- sendPacket(destinationId, meshPacket) - throws errors if we have errors talking to the device
- close() - shuts down the interface
- init() - starts the enumeration process to download NodeDB etc... - we will not publish to topics until this enumeration completes
- radioConfig - getter/setter syntax: https://www.python-course.eu/python3_properties.php
- nodes - the database of received nodes
- myNodeInfo
- myNodeId

## PubSub topics

Use a pubsub model to communicate events [https://pypubsub.readthedocs.io/en/v4.0.3/ ]

- meshtastic.send(MeshPacket) - Not implemented, instead call send(packet) on MeshInterface
- meshtastic.connection.established - published once we've successfully connected to the radio and downloaded the node DB
- meshtastic.connection.lost - published once we've lost our link to the radio
- meshtastic.receive.position(MeshPacket)
- meshtastic.receive.user(MeshPacket)
- meshtastic.receive.data(MeshPacket)
- meshtastic.node.updated(NodeInfo) - published when a node in the DB changes (appears, location changed, username changed, etc...)
- meshtastic.debug(string)

"""


class MeshInterface:
    """Interface class for meshtastic devices"""

    def __init__(self):
        self.debugOut = sys.stdout
        self.nodes = None  # FIXME

    def __handleReceived(fromradio):
        """
        Handle a packet that arrived from the radio (update model and publish events)

        Called by subclasses."""


class StreamInterface(MeshInterface):
    """Interface class for meshtastic devices over a stream link (serial, TCP, etc)"""

    def __init__(self, devPath):
        """Constructor, opens a connection to a specified serial port"""
        MeshInterface.__init__(self)
        logging.debug(f"Connecting to {devPath}")
        self.rxBuf = bytes()  # empty
        self.stream = serial.Serial(devPath, 921600)
        self.rxThread = threading.Thread(target=self.__reader, args=())
        self.rxThread.start()

    def close(self):
        self.stream.close()  # This will cause our reader thread to exit

    def __reader(self):
        """The reader thread that reads bytes from our stream"""
        while True:
            b = self.stream.read(1)
            self.debugOut.write(b.decode("utf-8"))
