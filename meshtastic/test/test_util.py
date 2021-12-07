"""Meshtastic unit tests for node.py"""

import pytest

from meshtastic.util import pskToString, our_exit

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


@pytest.mark.unit
def test_our_exit_zero_return_value():
    """Test our_exit with a zero return value"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        our_exit("Warning: Some message", 0)
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0


@pytest.mark.unit
def test_our_exit_non_zero_return_value():
    """Test our_exit with a non-zero return value"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        our_exit("Error: Some message", 1)
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
