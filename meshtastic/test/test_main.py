"""Meshtastic unit tests for __main__.py"""

import sys
import argparse
import re

import pytest

from meshtastic.__main__ import initParser, Settings


"""The command line arguments"""
#args = None

"""The parser for arguments"""
#parser = None

#@pytest.fixture
#def patched_env(monkeypatch):
#    monkeypatch.args = None
#    #monkeypatch.sys.argv = ['']
#    monkeypatch.parser = None

@pytest.mark.unit
def test_main_no_args(capsys):
    """Test no arguments"""
    sys.argv = ['']
    args = sys.argv
    settings = Settings.getInstance()
    parser = argparse.ArgumentParser()
    settings.set_parser(parser)
    settings.set_args(args)
    initParser()
    out, err = capsys.readouterr()
    assert out == ''
    assert err == ''


@pytest.mark.unit
def test_main_version(capsys):
    """Test --version"""
    sys.argv = ['', '--version']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    settings = Settings.getInstance()
    settings.set_parser(parser)
    settings.set_args(args)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        initParser()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    out, err = capsys.readouterr()
    assert re.match(r'[0-9]+\.[0-9]+\.[0-9]', out)
    assert err == ''
