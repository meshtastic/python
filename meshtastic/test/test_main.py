"""Meshtastic unit tests for __main__.py"""

import sys
import argparse
import re

import pytest

from meshtastic.__main__ import initParser, main, Globals


@pytest.mark.unit
def test_main_init_parser_no_args(capsys):
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
def test_main_init_parser_version(capsys):
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


@pytest.mark.unit
def test_main_main_version(capsys):
    """Test --version"""
    sys.argv = ['', '--version']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    out, err = capsys.readouterr()
    assert re.match(r'[0-9]+\.[0-9]+\.[0-9]', out)
    assert err == ''


@pytest.mark.unit
def test_main_main_no_args():
    """Test with no args"""
    sys.argv = ['']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


@pytest.mark.unit
def test_main_support(capsys):
    """Test --support"""
    sys.argv = ['', '--support']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    out, err = capsys.readouterr()
    assert re.search(r'System', out, re.MULTILINE)
    assert re.search(r'Platform', out, re.MULTILINE)
    assert re.search(r'Machine', out, re.MULTILINE)
    assert re.search(r'Executable', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
def test_main_ch_index_no_devices(capsys):
    """Test --ch-index 1"""
    sys.argv = ['', '--ch-index', '1']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    assert our_globals.get_target_node() is None
    assert our_globals.get_channel_index() == 0
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert our_globals.get_channel_index() == 1
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.search(r'Warning: No Meshtastic devices detected', out, re.MULTILINE)
    assert err == ''
