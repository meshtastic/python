"""Meshtastic smoke tests a device setup with wifi.

   Need to have run the following on an esp32 device:
      meshtastic --set wifi_ssid 'foo' --set wifi_password 'sekret'
"""
import re
import subprocess

import pytest


@pytest.mark.smokewifi
def test_smokewifi_info():
    """Test --info"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --info --host meshtastic.local"
    )
    assert re.search(r"^Owner", out, re.MULTILINE)
    assert re.search(r"^My info", out, re.MULTILINE)
    assert re.search(r"^Nodes in mesh", out, re.MULTILINE)
    assert re.search(r"^Preferences", out, re.MULTILINE)
    assert re.search(r"^Channels", out, re.MULTILINE)
    assert re.search(r"^  PRIMARY", out, re.MULTILINE)
    assert re.search(r"^Primary channel URL", out, re.MULTILINE)
    assert return_value == 0
