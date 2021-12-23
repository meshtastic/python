"""Meshtastic unit tests for util.py"""

import re
import logging

import pytest

from meshtastic.util import (fixme, stripnl, pskToString, our_exit,
                             support_info, genPSK256, fromStr, fromPSK,
                             quoteBooleans, catchAndIgnore)


@pytest.mark.unit
def test_genPSK256():
    """Test genPSK256"""
    assert genPSK256() != ''


@pytest.mark.unit
def test_fromStr():
    """Test fromStr"""
    assert fromStr('') == b''
    assert fromStr('0x12') == b'\x12'
    assert fromStr('t')
    assert fromStr('T')
    assert fromStr('true')
    assert fromStr('True')
    assert fromStr('yes')
    assert fromStr('Yes')
    assert fromStr('f') is False
    assert fromStr('F') is False
    assert fromStr('false') is False
    assert fromStr('False') is False
    assert fromStr('no') is False
    assert fromStr('No') is False
    assert fromStr('100.01') == 100.01
    assert fromStr('123') == 123
    assert fromStr('abc') == 'abc'


@pytest.mark.unit
def test_quoteBooleans():
    """Test quoteBooleans"""
    assert quoteBooleans('') == ''
    assert quoteBooleans('foo') == 'foo'
    assert quoteBooleans('true') == 'true'
    assert quoteBooleans('false') == 'false'
    assert quoteBooleans(': true') == ": 'true'"
    assert quoteBooleans(': false') == ": 'false'"

@pytest.mark.unit
def test_fromPSK():
    """Test fromPSK"""
    assert fromPSK('random') != ''
    assert fromPSK('none') == b'\x00'
    assert fromPSK('default') == b'\x01'
    assert fromPSK('simple22') == b'\x17'
    assert fromPSK('trash') == 'trash'


@pytest.mark.unit
def test_stripnl():
    """Test stripnl"""
    assert stripnl('') == ''
    assert stripnl('a\n') == 'a'
    assert stripnl(' a \n ') == 'a'
    assert stripnl('a\nb') == 'a b'


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
def test_pskToString_simple():
    """Test pskToString simple"""
    assert pskToString(bytes([0x03])) == 'simple2'


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


@pytest.mark.unit
def test_fixme():
    """Test fixme()"""
    with pytest.raises(Exception) as pytest_wrapped_e:
        fixme("some exception")
    assert pytest_wrapped_e.type == Exception


@pytest.mark.unit
def test_support_info(capsys):
    """Test support_info"""
    support_info()
    out, err = capsys.readouterr()
    assert re.search(r'System', out, re.MULTILINE)
    assert re.search(r'Platform', out, re.MULTILINE)
    assert re.search(r'Machine', out, re.MULTILINE)
    assert re.search(r'Executable', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
def test_catchAndIgnore(caplog):
    """Test catchAndIgnore() does not actually throw an exception, but just logs"""
    def some_closure():
        raise Exception('foo')
    with caplog.at_level(logging.DEBUG):
        catchAndIgnore("something", some_closure)
    assert re.search(r'Exception thrown in something', caplog.text, re.MULTILINE)
