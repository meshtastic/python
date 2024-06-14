"""Meshtastic unit tests for ble_interface.py"""
import logging

import pytest

from meshtastic.ble_interface import BLEClient, BLEInterface

def test_ble_client_no_addr_logs_message(caplog):
    """
    We want to see a debug message describing the error
    if we try to initialize a BLEClient with no address.
    """
    caplog.set_level(level=logging.DEBUG)
    BLEClient(address=None)
    assert "No address provided - only discover method will work." in caplog.text

def test_ble_interface_no_addr_returns_only_basic_object():
    """
    We want BLEState to be the only property of the BLEInterface if 
    it's initialized with an address of None.
    """
    test_interface = BLEInterface(address=None)
    test_interface_dict = test_interface.__dict__
    assert len(test_interface_dict) == 1
    assert 'state' in test_interface_dict
    assert isinstance(test_interface_dict['state'], BLEInterface.BLEState)

def test_ble_interface_bogus_addr_exits_process():
    """
    If we initialize BLEInterface with a BT address that doesn't
    exist, we should exit the process
    """
    with pytest.raises(SystemExit) as exc:
        BLEInterface(address="bogus")
    assert exc.value.code == 1
