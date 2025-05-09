"""TCPInterface class for interfacing with http endpoint
"""
# pylint: disable=R0917
import contextlib
import logging
import socket
import time
from typing import Optional

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
            self.myConnect()
        else:
            self.socket = None

        super().__init__(debugOut=debugOut, noProto=noProto, connectNow=connectNow, noNodes=noNodes)

    def __repr__(self):
        rep = f"TCPInterface({self.hostname!r}"
        if self.debugOut is not None:
            rep += f", debugOut={self.debugOut!r}"
        if self.noProto:
            rep += ", noProto=True"
        if self.socket is None:
            rep += ", connectNow=False"
        if self.portNumber != DEFAULT_TCP_PORT:
            rep += f", portNumber={self.portNumber!r}"
        if self.noNodes:
            rep += ", noNodes=True"
        rep += ")"
        return rep

    def _socket_shutdown(self) -> None:
        """Shutdown the socket.
        Note: Broke out this line so the exception could be unit tested.
        """
        if self.socket is not None:
            self.socket.shutdown(socket.SHUT_RDWR)

    def myConnect(self) -> None:
        """Connect to socket"""
        logging.debug(f"Connecting to {self.hostname}") # type: ignore[str-bytes-safe]
        server_address = (self.hostname, self.portNumber)
        self.socket = socket.create_connection(server_address)

    def close(self) -> None:
        """Close a connection to the device"""
        logging.debug("Closing TCP stream")
        super().close()
        # Sometimes the socket read might be blocked in the reader thread.
        # Therefore we force the shutdown by closing the socket here
        self._wantExit = True
        if self.socket is not None:
            with contextlib.suppress(Exception):  # Ignore errors in shutdown, because we might have a race with the server
                self._socket_shutdown()
            self.socket.close()

        self.socket = None

    def _writeBytes(self, b: bytes) -> None:
        """Write an array of bytes to our stream and flush"""
        if self.socket is not None:
            self.socket.send(b)

    def _readBytes(self, length) -> Optional[bytes]:
        """Read an array of bytes from our stream"""
        if self.socket is not None:
            data = self.socket.recv(length)
            # empty byte indicates a disconnected socket,
            # we need to handle it to avoid an infinite loop reading from null socket
            if data == b'':
                logging.debug("dead socket, re-connecting")
                # cleanup and reconnect socket without breaking reader thread
                with contextlib.suppress(Exception):
                    self._socket_shutdown()
                self.socket.close()
                self.socket = None
                time.sleep(1)
                self.myConnect()
                self._startConfig()
                return None
            return data

        # no socket, break reader thread
        self._wantExit = True
        return None
