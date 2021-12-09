"""Meshtastic unit tests for __main__.py"""

import sys
import argparse
import re

import pytest

from meshtastic.__main__ import initParser, Globals


@pytest.mark.unit
def test_main_no_args(capsys):
    """Test no arguments"""
    sys.argv = ['']
    args = sys.argv
    our_globals = Globals.getInstance()
    parser = argparse.ArgumentParser()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
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
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        initParser()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    out, err = capsys.readouterr()
    assert re.match(r'[0-9]+\.[0-9]+\.[0-9]', out)
    assert err == ''
