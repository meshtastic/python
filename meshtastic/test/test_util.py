"""Meshtastic unit tests for node.py"""

import pytest

from meshtastic.util import pskToString

@pytest.mark.unit
def test_pskToString_empty_string():
    """Test pskToString empty string"""
    assert pskToString('') == 'unencrypted'


@pytest.mark.unit
def test_pskToString_string():
    """Test pskToString string"""
    assert pskToString('hunter123') == 'secret'


@pytest.mark.unit
def test_pskToString_one_byte_zero_value():
    """Test pskToString one byte that is value of 0"""
    assert pskToString(bytes([0x00])) == 'unencrypted'


@pytest.mark.unit
def test_pskToString_one_byte_non_zero_value():
    """Test pskToString one byte that is non-zero"""
    assert pskToString(bytes([0x01])) == 'default'


@pytest.mark.unit
def test_pskToString_many_bytes():
    """Test pskToString many bytes"""
    assert pskToString(bytes([0x02, 0x01])) == 'secret'
