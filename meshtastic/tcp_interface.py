"""TCPInterface class for interfacing with http endpoint
"""
# pylint: disable=R0917
import logging
import socket
from typing import Optional, cast

from meshtastic.stream_interface import StreamInterface

DEFAULT_TCP_PORT = 4403

class TCPInterface(StreamInterface):
    """Interface class for meshtastic devices over a TCP link"""

    def __init__(
        self,
        hostname: str,
        debugOut=None,
        noProto: bool=False,
        connectNow: bool=True,
        portNumber: int=DEFAULT_TCP_PORT,
        noNodes:bool=False,
    ):
        """Constructor, opens a connection to a specified IP address/hostname

        Keyword Arguments:
            hostname {string} -- Hostname/IP address of the device to connect to
        """

        self.stream = None

        self.hostname: str = hostname
        self.portNumber: int = portNumber

        self.socket: Optional[socket.socket] = None

        if connectNow:
            logging.debug(f"Connecting to {hostname}") # type: ignore[str-bytes-safe]
            server_address: tuple[str, int] = (hostname, portNumber)
            sock: Optional[socket.socket] = socket.create_connection(server_address)
            self.socket = sock
        else:
            self.socket = None

        StreamInterface.__init__(
            self, debugOut=debugOut, noProto=noProto, connectNow=connectNow, noNodes=noNodes
        )

    def _socket_shutdown(self) -> None:
        """Shutdown the socket.
        Note: Broke out this line so the exception could be unit tested.
        """
        if self.socket:		#mian: please check that this should be "if self.socket:"
            cast(socket.socket, self.socket).shutdown(socket.SHUT_RDWR)

    def myConnect(self) -> None:
        """Connect to socket"""
        server_address: tuple[str, int] = (self.hostname, self.portNumber)
        sock: Optional[socket.socket] = socket.create_connection(server_address)
        self.socket = sock

    def close(self) -> None:
        """Close a connection to the device"""
        logging.debug("Closing TCP stream")
        StreamInterface.close(self)
        # Sometimes the socket read might be blocked in the reader thread.
        # Therefore we force the shutdown by closing the socket here
        self._wantExit: bool = True
        if not self.socket is None:
            try:
                self._socket_shutdown()
            except:
                pass  # Ignore errors in shutdown, because we might have a race with the server
            self.socket.close()

    def _writeBytes(self, b: bytes) -> None:
        """Write an array of bytes to our stream and flush"""
        if self.socket:
            self.socket.send(b)

    def _readBytes(self, length) -> Optional[bytes]:
        """Read an array of bytes from our stream"""
        if self.socket:
            return self.socket.recv(length)
        else:
            return None
