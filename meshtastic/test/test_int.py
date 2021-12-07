"""Meshtastic integration tests"""
import re
import subprocess

import pytest


@pytest.mark.int
def test_int_no_args():
    """Test without any args"""
    return_value, out = subprocess.getstatusoutput('meshtastic')
    assert re.match(r'usage: meshtastic', out)
    assert return_value == 1


@pytest.mark.int
def test_int_version():
    """Test '--version'."""
    return_value, out = subprocess.getstatusoutput('meshtastic --version')
    assert re.match(r'[0-9]+\.[0-9]+\.[0-9]', out)
    assert return_value == 0


@pytest.mark.int
def test_int_help():
    """Test '--help'."""
    return_value, out = subprocess.getstatusoutput('meshtastic --help')
    assert re.match(r'usage: meshtastic ', out)
    assert return_value == 0
