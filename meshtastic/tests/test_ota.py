"""Meshtastic unit tests for ota.py"""

import hashlib
import os
import socket
import tempfile
from unittest.mock import MagicMock, mock_open, patch, call

import pytest

from meshtastic.ota import (
    _file_sha256,
    ESP32WiFiOTA,
    OTAError,
)


@pytest.mark.unit
def test_file_sha256():
    """Test _file_sha256 calculates correct hash"""
    # Create a temporary file with known content
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        test_data = b"Hello, World!"
        f.write(test_data)
        temp_file = f.name

    try:
        result = _file_sha256(temp_file)
        expected_hash = hashlib.sha256(test_data).hexdigest()
        assert result.hexdigest() == expected_hash
    finally:
        os.unlink(temp_file)


@pytest.mark.unit
def test_file_sha256_large_file():
    """Test _file_sha256 handles files larger than chunk size"""
    # Create a temporary file with more than 4096 bytes
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        test_data = b"A" * 8192  # More than 4096 bytes
        f.write(test_data)
        temp_file = f.name

    try:
        result = _file_sha256(temp_file)
        expected_hash = hashlib.sha256(test_data).hexdigest()
        assert result.hexdigest() == expected_hash
    finally:
        os.unlink(temp_file)


@pytest.mark.unit
def test_esp32_wifi_ota_init_file_not_found():
    """Test ESP32WiFiOTA raises FileNotFoundError for non-existent file"""
    with pytest.raises(FileNotFoundError, match="does not exist"):
        ESP32WiFiOTA("/nonexistent/firmware.bin", "192.168.1.1")


@pytest.mark.unit
def test_esp32_wifi_ota_init_success():
    """Test ESP32WiFiOTA initializes correctly with valid file"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"fake firmware data")
        temp_file = f.name

    try:
        ota = ESP32WiFiOTA(temp_file, "192.168.1.1", 3232)
        assert ota._filename == temp_file
        assert ota._hostname == "192.168.1.1"
        assert ota._port == 3232
        assert ota._socket is None
        # Verify hash is calculated
        assert ota._file_hash is not None
        assert len(ota.hash_hex()) == 64  # SHA256 hex is 64 chars
    finally:
        os.unlink(temp_file)


@pytest.mark.unit
def test_esp32_wifi_ota_init_default_port():
    """Test ESP32WiFiOTA uses default port 3232"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"fake firmware data")
        temp_file = f.name

    try:
        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")
        assert ota._port == 3232
    finally:
        os.unlink(temp_file)


@pytest.mark.unit
def test_esp32_wifi_ota_hash_bytes():
    """Test hash_bytes returns correct bytes"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        test_data = b"firmware data"
        f.write(test_data)
        temp_file = f.name

    try:
        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")
        hash_bytes = ota.hash_bytes()
        expected_bytes = hashlib.sha256(test_data).digest()
        assert hash_bytes == expected_bytes
        assert len(hash_bytes) == 32  # SHA256 is 32 bytes
    finally:
        os.unlink(temp_file)


@pytest.mark.unit
def test_esp32_wifi_ota_hash_hex():
    """Test hash_hex returns correct hex string"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        test_data = b"firmware data"
        f.write(test_data)
        temp_file = f.name

    try:
        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")
        hash_hex = ota.hash_hex()
        expected_hex = hashlib.sha256(test_data).hexdigest()
        assert hash_hex == expected_hex
        assert len(hash_hex) == 64  # SHA256 hex is 64 chars
    finally:
        os.unlink(temp_file)


@pytest.mark.unit
def test_esp32_wifi_ota_read_line_not_connected():
    """Test _read_line raises ConnectionError when not connected"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"firmware")
        temp_file = f.name

    try:
        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")
        with pytest.raises(ConnectionError, match="Socket not connected"):
            ota._read_line()
    finally:
        os.unlink(temp_file)


@pytest.mark.unit
def test_esp32_wifi_ota_read_line_connection_closed():
    """Test _read_line raises ConnectionError when connection closed"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"firmware")
        temp_file = f.name

    try:
        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")
        mock_socket = MagicMock()
        # Simulate connection closed
        mock_socket.recv.return_value = b""
        ota._socket = mock_socket

        with pytest.raises(ConnectionError, match="Connection closed"):
            ota._read_line()
    finally:
        os.unlink(temp_file)


@pytest.mark.unit
def test_esp32_wifi_ota_read_line_success():
    """Test _read_line successfully reads a line"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"firmware")
        temp_file = f.name

    try:
        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")
        mock_socket = MagicMock()
        # Simulate receiving "OK\n"
        mock_socket.recv.side_effect = [b"O", b"K", b"\n"]
        ota._socket = mock_socket

        result = ota._read_line()
        assert result == "OK"
    finally:
        os.unlink(temp_file)


@pytest.mark.unit
@patch("meshtastic.ota.socket.socket")
def test_esp32_wifi_ota_update_success(mock_socket_class):
    """Test update() with successful OTA"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        test_data = b"A" * 1024  # 1KB of data
        f.write(test_data)
        temp_file = f.name

    try:
        # Setup mock socket
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")

        # Mock _read_line to return appropriate responses
        # First call: ERASING, Second call: OK (ready), Third call: OK (complete)
        with patch.object(ota, "_read_line") as mock_read_line:
            mock_read_line.side_effect = [
                "ERASING",  # Device is erasing flash
                "OK",  # Device ready for firmware
                "OK",  # Device finished successfully
            ]

            ota.update()

            # Verify socket was created and connected
            mock_socket_class.assert_called_once_with(
                socket.AF_INET, socket.SOCK_STREAM
            )
            mock_socket.settimeout.assert_called_once_with(15)
            mock_socket.connect.assert_called_once_with(("192.168.1.1", 3232))

            # Verify start command was sent
            start_cmd = f"OTA {len(test_data)} {ota.hash_hex()}\n".encode("utf-8")
            mock_socket.sendall.assert_any_call(start_cmd)

            # Verify firmware was sent (at least one chunk)
            assert mock_socket.sendall.call_count >= 2

            # Verify socket was closed
            mock_socket.close.assert_called_once()

    finally:
        os.unlink(temp_file)


@pytest.mark.unit
@patch("meshtastic.ota.socket.socket")
def test_esp32_wifi_ota_update_with_progress_callback(mock_socket_class):
    """Test update() with progress callback"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        test_data = b"A" * 1024  # 1KB of data
        f.write(test_data)
        temp_file = f.name

    try:
        # Setup mock socket
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")

        # Track progress callback calls
        progress_calls = []

        def progress_callback(sent, total):
            progress_calls.append((sent, total))

        # Mock _read_line
        with patch.object(ota, "_read_line") as mock_read_line:
            mock_read_line.side_effect = [
                "OK",  # Device ready
                "OK",  # Device finished
            ]

            ota.update(progress_callback=progress_callback)

            # Verify progress callback was called
            assert len(progress_calls) > 0
            # First call should show some progress
            assert progress_calls[0][0] > 0
            # Total should be the firmware size
            assert progress_calls[0][1] == len(test_data)
            # Last call should show all bytes sent
            assert progress_calls[-1][0] == len(test_data)

    finally:
        os.unlink(temp_file)


@pytest.mark.unit
@patch("meshtastic.ota.socket.socket")
def test_esp32_wifi_ota_update_device_error_on_start(mock_socket_class):
    """Test update() raises OTAError when device reports error during start"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"firmware")
        temp_file = f.name

    try:
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")

        with patch.object(ota, "_read_line") as mock_read_line:
            mock_read_line.return_value = "ERR BAD_HASH"

            with pytest.raises(OTAError, match="Device reported error"):
                ota.update()

    finally:
        os.unlink(temp_file)


@pytest.mark.unit
@patch("meshtastic.ota.socket.socket")
def test_esp32_wifi_ota_update_device_error_on_finish(mock_socket_class):
    """Test update() raises OTAError when device reports error after firmware sent"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"firmware")
        temp_file = f.name

    try:
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")

        with patch.object(ota, "_read_line") as mock_read_line:
            mock_read_line.side_effect = [
                "OK",  # Device ready
                "ERR FLASH_ERR",  # Error after firmware sent
            ]

            with pytest.raises(OTAError, match="OTA update failed"):
                ota.update()

    finally:
        os.unlink(temp_file)


@pytest.mark.unit
@patch("meshtastic.ota.socket.socket")
def test_esp32_wifi_ota_update_socket_cleanup_on_error(mock_socket_class):
    """Test that socket is properly cleaned up on error"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"firmware")
        temp_file = f.name

    try:
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")

        # Simulate connection error
        mock_socket.connect.side_effect = ConnectionRefusedError("Connection refused")

        with pytest.raises(ConnectionRefusedError):
            ota.update()

        # Verify socket was closed even on error
        mock_socket.close.assert_called_once()
        assert ota._socket is None

    finally:
        os.unlink(temp_file)


@pytest.mark.unit
@patch("meshtastic.ota.socket.socket")
def test_esp32_wifi_ota_update_large_firmware(mock_socket_class):
    """Test update() correctly chunks large firmware files"""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        # Create a file larger than chunk_size (1024)
        test_data = b"B" * 3000
        f.write(test_data)
        temp_file = f.name

    try:
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")

        with patch.object(ota, "_read_line") as mock_read_line:
            mock_read_line.side_effect = [
                "OK",  # Device ready
                "OK",  # Device finished
            ]

            ota.update()

            # Verify that all data was sent in chunks
            # 3000 bytes should be sent in ~3 chunks of 1024 bytes
            sendall_calls = [
                call
                for call in mock_socket.sendall.call_args_list
                if call[0][0]
                != f"OTA {len(test_data)} {ota.hash_hex()}\n".encode("utf-8")
            ]
            # Calculate total data sent (excluding the start command)
            total_sent = sum(len(call[0][0]) for call in sendall_calls)
            assert total_sent == len(test_data)

    finally:
        os.unlink(temp_file)


@pytest.mark.unit
@patch("meshtastic.ota.socket.socket")
def test_esp32_wifi_ota_update_unexpected_response_warning(mock_socket_class, caplog):
    """Test update() logs warning on unexpected response during startup"""
    import logging

    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"firmware")
        temp_file = f.name

    try:
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")

        with patch.object(ota, "_read_line") as mock_read_line:
            mock_read_line.side_effect = [
                "UNKNOWN",  # Unexpected response
                "OK",  # Then proceed
                "OK",  # Device finished
            ]

            with caplog.at_level(logging.WARNING):
                ota.update()

                # Check that warning was logged for unexpected response
                assert "Unexpected response" in caplog.text

    finally:
        os.unlink(temp_file)


@pytest.mark.unit
@patch("meshtastic.ota.socket.socket")
def test_esp32_wifi_ota_update_unexpected_final_response(mock_socket_class, caplog):
    """Test update() logs warning on unexpected final response after firmware upload"""
    import logging

    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"firmware")
        temp_file = f.name

    try:
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        ota = ESP32WiFiOTA(temp_file, "192.168.1.1")

        with patch.object(ota, "_read_line") as mock_read_line:
            mock_read_line.side_effect = [
                "OK",  # Device ready for firmware
                "UNKNOWN",  # Unexpected final response (not OK, not ERR, not ACK)
                "OK",  # Then succeed
            ]

            with caplog.at_level(logging.WARNING):
                ota.update()

                # Check that warning was logged for unexpected final response
                assert "Unexpected final response" in caplog.text

    finally:
        os.unlink(temp_file)
