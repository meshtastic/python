"""Meshtastic unit tests for ble_interface.py"""
import logging
from unittest.mock import patch

import pytest

from meshtastic.ble_interface import BLEClient, BLEInterface

def test_ble_client_no_addr_logs_message(caplog):
    caplog.set_level(level=logging.DEBUG)
    test_client = BLEClient(address=None)
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
    # with patch('meshtastic.util.our_exit') as patch_exit:
    #     patch_exit.return_value = None
    #     test_interface = BLEInterface(address="bogus")
    #     patch_exit.assert_called_once()
    with pytest.raises(SystemExit) as exc:
        test_interface = BLEInterface(address="bogus")
    assert exc.value.code == 1