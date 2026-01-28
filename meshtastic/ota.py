import os 
import hashlib
import socket
import logging
from typing import Optional, Callable


logger = logging.getLogger(__name__)


def _file_sha256(filename: str):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    
    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash

class ESP32WiFiOTA:
    """ESP32 WiFi Unified OTA updates."""

    def __init__(self, filename: str, hostname: str, port: int = 3232):
        self._filename = filename
        self._hostname = hostname
        self._port = port
        self._socket: Optional[socket.socket] = None

        if not os.path.exists(self._filename):
            raise Exception(f"File {self._filename} does not exist")

        self._file_hash = _file_sha256(self._filename)

    def _read_line(self) -> str:
        """Read a line from the socket."""
        if not self._socket:
            raise Exception("Socket not connected")

        line = b""
        while not line.endswith(b"\n"):
            char = self._socket.recv(1)
            
            if not char:
                raise Exception("Connection closed while waiting for response")

            line += char

        return line.decode("utf-8").strip()

    def hash_bytes(self) -> bytes:
        """Return the hash as bytes."""
        return self._file_hash.digest()

    def hash_hex(self) -> str:
        """Return the hash as a hex string."""
        return self._file_hash.hexdigest()

    def update(self, progress_callback: Optional[Callable[[int, int], None]] = None):
        """Perform the OTA update."""
        with open(self._filename, "rb") as f:
            data = f.read()
        size = len(data)

        logger.info(f"Starting OTA update with {self._filename} ({size} bytes, hash {self.hash_hex()})")

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(15)
        try:
            self._socket.connect((self._hostname, self._port))
            logger.debug(f"Connected to {self._hostname}:{self._port}")

            # Send start command
            self._socket.sendall(f"OTA {size} {self.hash_hex()}\n".encode("utf-8"))

            # Wait for OK from the device
            while True:
                response = self._read_line()
                if response == "OK":
                    break
                elif response == "ERASING":
                    logger.info("Device is erasing flash...")
                elif response.startswith("ERR "):
                    raise Exception(f"Device reported error: {response}")
                else:
                    logger.warning(f"Unexpected response: {response}")

            # Stream firmware
            sent_bytes = 0
            chunk_size = 1024
            while sent_bytes < size:
                chunk = data[sent_bytes : sent_bytes + chunk_size]
                self._socket.sendall(chunk)
                sent_bytes += len(chunk)

                if progress_callback:
                    progress_callback(sent_bytes, size)
                else:
                    print(f"[{sent_bytes / size * 100:5.1f}%] Sent {sent_bytes} of {size} bytes...", end="\r")

            if not progress_callback:
                print()

            # Wait for OK from device
            logger.info("Firmware sent, waiting for verification...")
            while True:
                response = self._read_line()

                if response == "OK":
                    logger.info("OTA update completed successfully!")
                    break
                elif response == "ACK":
                    continue
                elif response.startswith("ERR "):
                    raise Exception(f"OTA update failed: {response}")
                else:
                    logger.warning(f"Unexpected final response: {response}")

        finally:
            if self._socket:
                self._socket.close()
                self._socket = None