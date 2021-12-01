"""Meshtastic unit tests for node.py"""
import re
import subprocess
import platform

import pytest

from meshtastic.node import pskToString

@pytest.mark.unit
def test_pskToString():
    """Test pskToString"""
    assert pskToString('') == 'unencrypted'
    assert pskToString(bytes([0x00])) == 'unencrypted'
    assert pskToString(bytes([0x01])) == 'default'
    assert pskToString(bytes([0x02, 0x01])) == 'secret'
