"""Meshtastic unit tests for ble_interface.py"""


from unittest.mock import patch
import pytest

from ..ble_interface import BLEInterface

@pytest.mark.unit
@patch('platform.system', return_value='Linux')
def test_BLEInterface(mock_platform):
    """Test that we can instantiate a BLEInterface"""
    iface = BLEInterface('foo', debugOut=True, noProto=True)
    iface.close()
    mock_platform.assert_called()
