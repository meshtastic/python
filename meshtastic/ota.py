"""Meshtastic ESP32 Unified OTA
"""
import os
import hashlib
import socket
import logging
from typing import Optional, Callable
import meshtastic
import queue

logger = logging.getLogger(__name__)


def _file_sha256(filename: str):
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()

    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash


class OTAError(Exception):
    """Exception for OTA errors."""


class ESP32WiFiOTA:
    """ESP32 WiFi Unified OTA updates."""

    def __init__(self, filename: str, hostname: str, port: int = 3232):
        self._filename = filename
        self._hostname = hostname
        self._port = port
        self._socket: Optional[socket.socket] = None

        if not os.path.exists(self._filename):
            raise FileNotFoundError(f"File {self._filename} does not exist")

        self._file_hash = _file_sha256(self._filename)

    def _read_line(self) -> str:
        """Read a line from the socket."""
        if not self._socket:
            raise ConnectionError("Socket not connected")

        line = b""
        while not line.endswith(b"\n"):
            char = self._socket.recv(1)

            if not char:
                raise ConnectionError("Connection closed while waiting for response")

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

                if response == "ERASING":
                    logger.info("Device is erasing flash...")
                elif response.startswith("ERR "):
                    raise OTAError(f"Device reported error: {response}")
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

                if response.startswith("ERR "):
                    raise OTAError(f"OTA update failed: {response}")
                elif response != "ACK":
                    logger.warning(f"Unexpected final response: {response}")

        finally:
            if self._socket:
                self._socket.close()
                self._socket = None

class ESP32BLEOTA:
    """ESP32 BLE Unified OTA updates."""

    SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
    DEVICE_NAME_UUID = "00002a00-0000-1000-8000-00805f9b34fb"
    WRITE_UUID = "62ec0272-3ec5-11eb-b378-0242ac130005"
    NOTIFY_UUID = "62ec0272-3ec5-11eb-b378-0242ac130003"

    class NotificationReceiver:
        """Thread-safe queue receiver for BLE notifications."""
        def __init__(self) -> None:
            self._queue: queue.Queue[str] = queue.Queue()

        def on_notify(self, _, data: bytearray) -> None:
            """Callback passed to Bleak client.start_notify."""
            text = bytes(data).decode("utf-8", errors="replace").strip("\r\n")
            self._queue.put(text)

        def wait_for_next(self, timeout: Optional[float] = 10.0) -> Optional[str]:
            """Block until a notification arrives, or return None if timeout expires."""
            try:
                return self._queue.get(timeout=timeout)
            except queue.Empty:
                return None

    def __init__(self, filename: str):
        self._filename = filename

        if not os.path.exists(self._filename):
            raise FileNotFoundError(f"File {self._filename} does not exist")

        self._file_hash = _file_sha256(self._filename)

    def hash_bytes(self) -> bytes:
        """Return the hash as bytes."""
        return self._file_hash.digest()

    def hash_hex(self) -> str:
        """Return the hash as a hex string."""
        return self._file_hash.hexdigest()

    def _read_device_name(self, address: str) -> Optional[str]:
        """Read the device name"""
        device_name = None
        client = meshtastic.ble_interface.BLEClient(address)
        try:
            client.connect()
            if client.has_characteristic(self.DEVICE_NAME_UUID):
                raw_bytes = client.read_gatt_char(self.DEVICE_NAME_UUID)
                device_name = raw_bytes.decode("utf-8").strip("\x00\r\n ")
        except Exception:
            pass
        finally:
            try:
                client.disconnect()
            except Exception:
                pass
            client.close()
        return device_name

    def update(self, progress_callback: Optional[Callable[[int, int], None]] = None):
        """Perform the OTA update."""
        with open(self._filename, "rb") as f:
            data = f.read()
        size = len(data)

        logger.info(f"Starting OTA update with {self._filename} ({size} bytes, hash {self.hash_hex()})")

        logger.info("Scanning for BLE devices in OTA mode (takes 10 seconds)...")
        with meshtastic.ble_interface.BLEClient() as client:
            response = client.discover(
                timeout=10, return_adv=True, service_uuids=[self.SERVICE_UUID.lower()], scanning_mode="active"
            )

            devices = [d[0] for d in response.values() if self.SERVICE_UUID in (u.lower() for u in d[1].service_uuids)]
        if not devices:
            raise OTAError("Could not find any device in OTA mode")
        print("Found devices in OTA mode:")
        for idx, device in enumerate(devices):
            device.name = self._read_device_name(device.address)
            print(f"\t[{idx}] {device.name} ({device.address})")

        # We have to let the user choose because the Bluetooth address changes
        # in OTA bootloader compared to meshtastic firmware
        selected_device = None
        while not selected_device:
            user_selection = input("Please select number of device you want to update (q to quit): ")
            if user_selection.isdigit():
                idx = int(user_selection)
                if 0 <= idx < len(devices):
                    selected_device = devices[idx]
            if user_selection == "q":
                return

        # Establishing Bluetooth connection
        client = meshtastic.ble_interface.BLEClient(selected_device.address)
        try:
            client.connect()

            logger.info(f"Connected to {selected_device.name or selected_device.address}")

            # Register callback for BLE notify (Messages from the device)
            notification_receiver = self.NotificationReceiver()
            client.start_notify(self.NOTIFY_UUID, callback=notification_receiver.on_notify)

            # Send start command
            client.write_gatt_char(self.WRITE_UUID, f"OTA {size} {self.hash_hex()}\n".encode("utf-8"), response=True)

            # Wait for OK from the device
            while True:
                response = notification_receiver.wait_for_next(timeout=10.0)
                if response:
                    if response == "OK":
                        break
                    elif response == "ERASING":
                        logger.info("Device is erasing flash...")
                    elif response.startswith("ERR "):
                        raise OTAError(f"Device reported error: {response}")
                    else:
                        logger.warning(f"Unexpected response: {response}")
                else:
                    raise OTAError("Timeout waiting for response")

            # Streaming firmware data in chunks of 512 bytes (or MTU size)
            sent_bytes = 0
            chunk_size = min(512, client.bleak_client.mtu_size - 3)
            while sent_bytes < size:
                chunk = data[sent_bytes : sent_bytes + chunk_size]
                client.write_gatt_char(self.WRITE_UUID, chunk, response=True)

                sent_bytes += len(chunk)

                if sent_bytes < size:
                    while True:
                        response = notification_receiver.wait_for_next(timeout=10.0)
                        if response:
                            if response == "ACK":
                                break
                            elif response.startswith("ERR "):
                                raise OTAError(f"Device reported error: {response}")
                            else:
                                logger.warning(f"Unexpected response: {response}")
                        else:
                            raise OTAError("Timeout waiting for response")

                if progress_callback:
                    progress_callback(sent_bytes, size)
                else:
                    print(f"[{sent_bytes / size * 100:5.1f}%] Sent {sent_bytes} of {size} bytes...", end="\r")

            if not progress_callback:
                print()

            # Wait for OK from device
            logger.info("Firmware sent, waiting for verification...")
            while True:
                response = notification_receiver.wait_for_next(timeout=10.0)
                if response:
                    if response == "OK":
                        logger.info("OTA update completed successfully!")
                        break
                    if response.startswith("ERR "):
                        raise OTAError(f"OTA update failed: {response}")
                    else:
                        logger.warning(f"Unexpected final response: {response}")
                else:
                    raise OTAError("Timeout waiting for response")

        finally:
            # Terminating Bluetooth connection
            try:
                client.disconnect()
            except Exception:
                pass
            client.close()
