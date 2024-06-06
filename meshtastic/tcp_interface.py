"""TCPInterface class for interfacing with http endpoint
"""
import logging
import socket
from typing import Optional

from meshtastic.stream_interface import StreamInterface


class TCPInterface(StreamInterface):
    """Interface class for meshtastic devices over a TCP link"""

    def __init__(
        self,
        hostname: str,
        debugOut=None,
        noProto=False,
        connectNow=True,
        portNumber=4403,
        noNodes:bool=False,
    ):
        """Constructor, opens a connection to a specified IP address/hostname

        Keyword Arguments:
            hostname {string} -- Hostname/IP address of the device to connect to
        """

        self.stream = None

        self.hostname = hostname
        self.portNumber = portNumber

        if connectNow:
            logging.debug(f"Connecting to {hostname}") # type: ignore[str-bytes-safe]
            server_address = (hostname, portNumber)
            sock = socket.create_connection(server_address)
            self.socket: Optional[socket.socket] = sock
        else:
            self.socket = None

        StreamInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, connectNow=connectNow, noNodes=noNodes
        )

    def _socket_shutdown(self):
        """Shutdown the socket.
        Note: Broke out this line so the exception could be unit tested.
        """
        self.socket.shutdown(socket.SHUT_RDWR)

    def myConnect(self):
        """Connect to socket"""
        server_address = (self.hostname, self.portNumber)
        sock = socket.create_connection(server_address)
        self.socket = sock

    def close(self):
        """Close a connection to the device"""
        logging.debug("Closing TCP stream")
        StreamInterface.close(self)
        # Sometimes the socket read might be blocked in the reader thread.
        # Therefore we force the shutdown by closing the socket here
        self._wantExit = True
        if not self.socket is None:
            try:
                self._socket_shutdown()
            except:
                pass  # Ignore errors in shutdown, because we might have a race with the server
            self.socket.close()

    def _writeBytes(self, b):
        """Write an array of bytes to our stream and flush"""
        self.socket.send(b)

    def _readBytes(self, length):
        """Read an array of bytes from our stream"""
        return self.socket.recv(length)
