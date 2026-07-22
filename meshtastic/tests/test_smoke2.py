"""Meshtastic smoke tests with 2 devices connected via USB"""
import re
import subprocess

import pytest


@pytest.mark.smoke2
def test_smoke2_info():
    """Test --info with 2 devices connected serially"""
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.search(r"Warning: Multiple", out, re.MULTILINE)
    assert return_value == 1


@pytest.mark.smoke2
def test_smoke2_test():
    """Test --test"""
    return_value, out = subprocess.getstatusoutput("meshtastic --test")
    assert re.search(r"Writing serial debugging", out, re.MULTILINE)
    assert re.search(r"Ports opened", out, re.MULTILINE)
    assert re.search(r"Running 5 tests", out, re.MULTILINE)
    assert return_value == 0
