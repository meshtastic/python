"""Meshtastic unit tests for ble_interface.py"""
import logging
import os
from unittest.mock import patch

import pytest

from meshtastic.ble_interface import BLEClient, BLEInterface


def test_ble_client_no_addr_logs_message(caplog):
    """
    We want to see a debug message describing the error
    if we try to initialize a BLEClient with no address.
    """
    caplog.set_level(level=logging.DEBUG)
    test_ble_client = BLEClient(address=None)
    test_ble_client.close()
    assert "No address provided - only discover method will work." in caplog.text

def test_ble_interface_sanitize_address_returns_lower():
    """
    _sanitize_address should only return lower case letters
    """
    assert BLEInterface._sanitize_address("HELLO") == "hello"

def test_ble_interface_sanitize_address_returns_no_underscores():
    """
    _sanitize_address should only return strings without underscores
    """
    assert BLEInterface._sanitize_address("hello_world") == "helloworld"

def test_ble_interface_sanitize_address_returns_no_dash():
    """
    _sanitize_address should only return strings without dashes
    """
    assert BLEInterface._sanitize_address("hello-world") == "helloworld"

def test_ble_interface_sanitize_address_returns_no_colon():
    """
    _sanitize_address should only return strings without colons
    """
    assert BLEInterface._sanitize_address("hello:world") == "helloworld"

def test_linux_exit_handler():
    """
    Given a platform.system of Linux (or as I like to call it, Ganoo plus Linux), 
    we should register an exit handler.
    """
    with patch("platform.system") as fake_platform:
        fake_platform.return_value = "Linux"
        test_interface = BLEInterface(address="")
        assert test_interface._exit_handler is not None


@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Bluetooth tests are not supported in CI environment")
def test_ble_interface_bogus_addr_exits_process():
    """
    If we initialize BLEInterface with a BT address that doesn't
    exist, we should exit the process
    """
    with pytest.raises(BLEInterface.BLEError) as exc:
        BLEInterface(address="bogus")
    assert "No Meshtastic BLE peripheral with identifier or address 'bogus' found" in exc.value.args[0]
