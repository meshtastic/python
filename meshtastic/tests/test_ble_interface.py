"""Meshtastic unit tests for ble_interface.py"""


import pytest

from ..ble_interface import BLEInterface

@pytest.mark.unit
def test_BLEInterface():
    """Test that we can instantiate a BLEInterface"""
    iface = BLEInterface('foo', debugOut=True, noProto=True)
    iface.close()
