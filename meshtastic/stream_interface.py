"""Stream Interface base class
"""
import io
import logging
import threading
import time
import traceback

from typing import Optional, cast

import serial # type: ignore[import-untyped]

from meshtastic.mesh_interface import MeshInterface
from meshtastic.util import is_windows11, stripnl

START1 = 0x94
START2 = 0xC3
HEADER_LEN = 4
MAX_TO_FROM_RADIO_SIZE = 512


class StreamInterface(MeshInterface):
    """Interface class for meshtastic devices over a stream link (serial, TCP, etc)"""

    def __init__(self, debugOut: Optional[io.TextIOWrapper]=None, noProto: bool=False, connectNow: bool=True, noNodes: bool=False) -> None:
        """Constructor, opens a connection to self.stream

        Keyword Arguments:
            debugOut {stream} -- If a stream is provided, any debug serial output from the
                                 device will be emitted to that stream. (default: {None})

        Raises:
            Exception: [description]
            Exception: [description]
        """

        if not hasattr(self, "stream") and not noProto:
            raise Exception( # pylint: disable=W0719
                "StreamInterface is now abstract (to update existing code create SerialInterface instead)"
            )
        self.stream: Optional[serial.Serial] # only serial uses this, TCPInterface overrides the relevant methods instead
        self._rxBuf = bytes()  # empty
        self._wantExit = False

        self.is_windows11 = is_windows11()
        self.cur_log_line = ""

        # FIXME, figure out why daemon=True causes reader thread to exit too early
        self._rxThread = threading.Thread(target=self.__reader, args=(), daemon=True, name="stream reader")

        MeshInterface.__init__(self, debugOut=debugOut, noProto=noProto, noNodes=noNodes)

        # Start the reader thread after superclass constructor completes init
        if connectNow:
            self.connect()
            if not noProto:
                self.waitForConfig()

    def connect(self) -> None:
        """Connect to our radio

        Normally this is called automatically by the constructor, but if you
        passed in connectNow=False you can manually start the reading thread later.
        """

        # Send some bogus UART characters to force a sleeping device to wake, and
        # if the reading statemachine was parsing a bad packet make sure
        # we write enough start bytes to force it to resync (we don't use START1
        # because we want to ensure it is looking for START1)
        p: bytes = bytearray([START2] * 32)
        self._writeBytes(p)
        time.sleep(0.1)  # wait 100ms to give device time to start running

        self._rxThread.start()

        self._startConfig()

        if not self.noProto:  # Wait for the db download if using the protocol
            self._waitConnected()

    def _disconnected(self) -> None:
        """We override the superclass implementation to close our port"""
        MeshInterface._disconnected(self)

        logging.debug("Closing our port")
        # pylint: disable=E0203
        if not self.stream is None:
            # pylint: disable=E0203
            self.stream.close()
            # pylint: disable=W0201
            self.stream = None

    def _writeBytes(self, b: bytes) -> None:
        """Write an array of bytes to our stream and flush"""
        if self.stream:  # ignore writes when stream is closed
            self.stream.write(b)
            self.stream.flush()
            # win11 might need a bit more time, too
            if self.is_windows11:
                time.sleep(1.0)
            else:
                # we sleep here to give the TBeam a chance to work
                time.sleep(0.1)

    def _readBytes(self, length) -> Optional[bytes]:
        """Read an array of bytes from our stream"""
        if self.stream:
            return self.stream.read(length)
        else:
            return None

    def _sendToRadioImpl(self, toRadio) -> None:
        """Send a ToRadio protobuf to the device"""
        logging.debug(f"Sending: {stripnl(toRadio)}")
        b: bytes = toRadio.SerializeToString()
        bufLen: int = len(b)
        # We convert into a string, because the TCP code doesn't work with byte arrays
        header: bytes = bytes([START1, START2, (bufLen >> 8) & 0xFF, bufLen & 0xFF])
        logging.debug(f"sending header:{header!r} b:{b!r}")
        self._writeBytes(header + b)

    def close(self) -> None:
        """Close a connection to the device"""
        logging.debug("Closing stream")
        MeshInterface.close(self)
        # pyserial cancel_read doesn't seem to work, therefore we ask the
        # reader thread to close things for us
        self._wantExit = True
        if self._rxThread != threading.current_thread():
            self._rxThread.join()  # wait for it to exit

    def _handleLogByte(self, b):
        """Handle a byte that is part of a log message from the device."""

        utf = "?"  # assume we might fail
        try:
            utf = b.decode("utf-8")
        except:
            pass

        if utf == "\r":
            pass    # ignore
        elif utf == "\n":
            self._handleLogLine(self.cur_log_line)
            self.cur_log_line = ""
        else:
            self.cur_log_line += utf

    def __reader(self) -> None:
        """The reader thread that reads bytes from our stream"""
        logging.debug("in __reader()")
        empty = bytes()

        try:
            while not self._wantExit:
                # logging.debug("reading character")
                b: Optional[bytes] = self._readBytes(1)
                # logging.debug("In reader loop")
                # logging.debug(f"read returned {b}")
                if b is not None and len(cast(bytes, b)) > 0:
                    c: int = b[0]
                    # logging.debug(f'c:{c}')
                    ptr: int = len(self._rxBuf)

                    # Assume we want to append this byte, fixme use bytearray instead
                    self._rxBuf = self._rxBuf + b

                    if ptr == 0:  # looking for START1
                        if c != START1:
                            self._rxBuf = empty  # failed to find start
                            # This must be a log message from the device

                            self._handleLogByte(b)

                    elif ptr == 1:  # looking for START2
                        if c != START2:
                            self._rxBuf = empty  # failed to find start2
                    elif ptr >= HEADER_LEN - 1:  # we've at least got a header
                        # logging.debug('at least we received a header')
                        # big endian length follows header
                        packetlen = (self._rxBuf[2] << 8) + self._rxBuf[3]

                        if (
                            ptr == HEADER_LEN - 1
                        ):  # we _just_ finished reading the header, validate length
                            if packetlen > MAX_TO_FROM_RADIO_SIZE:
                                self._rxBuf = (
                                    empty  # length was out out bounds, restart
                                )

                        if len(self._rxBuf) != 0 and ptr + 1 >= packetlen + HEADER_LEN:
                            try:
                                self._handleFromRadio(self._rxBuf[HEADER_LEN:])
                            except Exception as ex:
                                logging.error(
                                    f"Error while handling message from radio {ex}"
                                )
                                traceback.print_exc()
                            self._rxBuf = empty
                else:
                    # logging.debug(f"timeout")
                    pass
        except serial.SerialException as ex:
            if (
                not self._wantExit
            ):  # We might intentionally get an exception during shutdown
                logging.warning(
                    f"Meshtastic serial port disconnected, disconnecting... {ex}"
                )
        except OSError as ex:
            if (
                not self._wantExit
            ):  # We might intentionally get an exception during shutdown
                logging.error(
                    f"Unexpected OSError, terminating meshtastic reader... {ex}"
                )
        except Exception as ex:
            logging.error(
                f"Unexpected exception, terminating meshtastic reader... {ex}"
            )
        finally:
            logging.debug("reader is exiting")
            self._disconnected()
