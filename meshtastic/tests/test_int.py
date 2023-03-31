"""Meshtastic integration tests"""
import re
import subprocess

import pytest


@pytest.mark.int
def test_int_meshtastic_no_args():
    """Test meshtastic without any args"""
    return_value, out = subprocess.getstatusoutput("meshtastic")
    assert re.match(r"usage: meshtastic", out)
    assert return_value == 1


@pytest.mark.int
def test_int_mesh_tunnel_no_args():
    """Test mesh-tunnel without any args"""
    return_value, out = subprocess.getstatusoutput("mesh-tunnel")
    assert re.match(r"usage: mesh-tunnel", out)
    assert return_value == 1


@pytest.mark.int
def test_int_version():
    """Test '--version'."""
    return_value, out = subprocess.getstatusoutput("meshtastic --version")
    assert re.match(r"[0-9]+\.[0-9]+\.[0-9]", out)
    assert return_value == 0


@pytest.mark.int
def test_int_help():
    """Test '--help'."""
    return_value, out = subprocess.getstatusoutput("meshtastic --help")
    assert re.match(r"usage: meshtastic ", out)
    assert return_value == 0


@pytest.mark.int
def test_int_support():
    """Test '--support'."""
    return_value, out = subprocess.getstatusoutput("meshtastic --support")
    assert re.search(r"System", out)
    assert re.search(r"Python", out)
    assert return_value == 0
