"""Meshtastic unit tests for supported_device.py"""

import pytest

from meshtastic.supported_device import SupportedDevice


@pytest.mark.unit
def test_usb_ids_are_normalized():
    """VID/PID are stored lower case, without 0x, padded to 4 digits"""
    sd = SupportedDevice(name="x", usb_vendor_id_in_hex="0x2E8A", usb_product_id_in_hex="F")
    assert sd.usb_vendor_id_in_hex == "2e8a"
    assert sd.usb_product_id_in_hex == "000f"
    assert SupportedDevice(name="y").usb_vendor_id_in_hex is None
