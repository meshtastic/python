"""Meshtastic unit tests for __main__.py"""

import sys
import argparse
import re

from unittest.mock import patch
import pytest

from meshtastic.__main__ import initParser, main, Globals
#from meshtastic.serial_interface import SerialInterface


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


@pytest.mark.unit
@patch('meshtastic.util.findPorts', return_value=[])
def test_main_test_no_ports(patched_find_ports):
    """Test --test with no hardware"""
    sys.argv = ['', '--test']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    assert our_globals.get_target_node() is None
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    patched_find_ports.assert_called()


@pytest.mark.unit
@patch('meshtastic.util.findPorts', return_value=['/dev/ttyFake1'])
def test_main_test_one_port(patched_find_ports):
    """Test --test with one fake port"""
    sys.argv = ['', '--test']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    assert our_globals.get_target_node() is None
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    patched_find_ports.assert_called()


@pytest.mark.unit
@patch('meshtastic.test.testAll', return_value=True)
@patch('meshtastic.util.findPorts', return_value=['/dev/ttyFake1', '/dev/ttyFake2'])
def test_main_test_two_ports_success(patched_find_ports, patched_test_all):
    """Test --test two fake ports and testAll() is a simulated success"""
    sys.argv = ['', '--test']
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
    # TODO: why does this fail? patched_find_ports.assert_called()
    patched_test_all.assert_called()


@pytest.mark.unit
@patch('meshtastic.test.testAll', return_value=False)
@patch('meshtastic.util.findPorts', return_value=['/dev/ttyFake1', '/dev/ttyFake2'])
def test_main_test_two_ports_fails(patched_find_ports, patched_test_all):
    """Test --test two fake ports and testAll() is a simulated failure"""
    sys.argv = ['', '--test']
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
    # TODO: why does this fail? patched_find_ports.assert_called()
    patched_test_all.assert_called()
#
#
#@pytest.mark.unit
#@patch('meshtastic.stream_interface.StreamInterface.__init__')
#@patch('serial.Serial')
#@patch('meshtastic.serial_interface.SerialInterface')
#@patch('meshtastic.util.findPorts', return_value=['/dev/ttyFake1'])
#def test_main_info_one_port(patched_find_ports, patched_serial_interface,
#                            patched_serial_serial, patched_stream_interface_constructor):
#    """Test --info one fake port"""
#    iface = MagicMock()
#    patched_serial_interface.return_value = iface
#    astream = MagicMock()
#    patched_serial_serial = astream
#    siface = MagicMock()
#    patched_stream_interface_constructor = siface
#    sys.argv = ['', '--info']
#    args = sys.argv
#    parser = None
#    parser = argparse.ArgumentParser()
#    our_globals = Globals.getInstance()
#    our_globals.set_parser(parser)
#    our_globals.set_args(args)
#    main()
#    patched_find_ports.assert_called()
#    patched_serial_interface.assert_called()
#    patched_serial_serial.assert_called()
#    patched_stream_interface_constructor
