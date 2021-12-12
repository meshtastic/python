"""Meshtastic unit tests for __main__.py"""

import sys
import argparse
import re

from unittest.mock import patch, MagicMock
import pytest

from meshtastic.__main__ import initParser, main, Globals

from ..serial_interface import SerialInterface
from ..node import Node


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
@patch('meshtastic.util.findPorts', return_value=[])
def test_main_ch_index_no_devices(patched_find_ports, capsys):
    """Test --ch-index 1"""
    sys.argv = ['', '--ch-index', '1']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    assert our_globals.get_target_node() is None
    assert our_globals.get_channel_index() is None
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert our_globals.get_channel_index() == 1
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.search(r'Warning: No Meshtastic devices detected', out, re.MULTILINE)
    assert err == ''
    patched_find_ports.assert_called()


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


@pytest.mark.unit
def test_main_info(capsys):
    """Test --info"""
    sys.argv = ['', '--info']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    iface = MagicMock(autospec=SerialInterface)
    def mock_showInfo():
        print('inside mocked showInfo')
    iface.showInfo.side_effect = mock_showInfo
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        print('out:', out)
        print('err:', err)
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'inside mocked showInfo', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_qr(capsys):
    """Test --qr"""
    sys.argv = ['', '--qr']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    iface = MagicMock(autospec=SerialInterface)
    # TODO: could mock/check url
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        print('out:', out)
        print('err:', err)
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Primary channel URL', out, re.MULTILINE)
        # if a qr code is generated it will have lots of these
        assert re.search(r'\[7m', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_nodes(capsys):
    """Test --nodes"""
    sys.argv = ['', '--nodes']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    iface = MagicMock(autospec=SerialInterface)
    def mock_showNodes():
        print('inside mocked showNodes')
    iface.showNodes.side_effect = mock_showNodes
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        print('out:', out)
        print('err:', err)
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'inside mocked showNodes', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_set_owner_to_bob(capsys):
    """Test --set-owner bob"""
    sys.argv = ['', '--set-owner', 'bob']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        print('out:', out)
        print('err:', err)
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Setting device owner to bob', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_set_ham_to_KI123(capsys):
    """Test --set-ham KI123"""
    sys.argv = ['', '--set-ham', 'KI123']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    our_globals.set_target_node(None)

    mocked_node = MagicMock(autospec=Node)
    def mock_turnOffEncryptionOnPrimaryChannel():
        print('inside mocked turnOffEncryptionOnPrimaryChannel')
    def mock_setOwner(name, is_licensed):
        print('inside mocked setOwner')
    mocked_node.turnOffEncryptionOnPrimaryChannel.side_effect = mock_turnOffEncryptionOnPrimaryChannel
    mocked_node.setOwner.side_effect = mock_setOwner

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        print('out:', out)
        print('err:', err)
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Setting HAM ID to KI123', out, re.MULTILINE)
        assert re.search(r'inside mocked setOwner', out, re.MULTILINE)
        assert re.search(r'inside mocked turnOffEncryptionOnPrimaryChannel', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_reboot(capsys):
    """Test --reboot"""
    sys.argv = ['', '--reboot']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    our_globals.set_target_node(None)

    mocked_node = MagicMock(autospec=Node)
    def mock_reboot():
        print('inside mocked reboot')
    mocked_node.reboot.side_effect = mock_reboot

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        print('out:', out)
        print('err:', err)
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'inside mocked reboot', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_sendtext(capsys):
    """Test --sendtext"""
    sys.argv = ['', '--sendtext', 'hello']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    our_globals.set_target_node(None)

    iface = MagicMock(autospec=SerialInterface)
    def mock_sendText(text, dest, wantAck):
        print('inside mocked sendText')
    iface.sendText.side_effect = mock_sendText

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        print('out:', out)
        print('err:', err)
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Sending text message', out, re.MULTILINE)
        assert re.search(r'inside mocked sendText', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_sendping(capsys):
    """Test --sendping"""
    sys.argv = ['', '--sendping']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    our_globals.set_target_node(None)

    iface = MagicMock(autospec=SerialInterface)
    def mock_sendData(payload, dest, portNum, wantAck, wantResponse):
        print('inside mocked sendData')
    iface.sendData.side_effect = mock_sendData

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        print('out:', out)
        print('err:', err)
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Sending ping message', out, re.MULTILINE)
        assert re.search(r'inside mocked sendData', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_setlat(capsys):
    """Test --sendlat"""
    sys.argv = ['', '--setlat', '37.5']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    our_globals.set_target_node(None)

    mocked_node = MagicMock(autospec=Node)
    def mock_writeConfig():
        print('inside mocked writeConfig')
    mocked_node.writeConfig.side_effect = mock_writeConfig

    iface = MagicMock(autospec=SerialInterface)
    def mock_sendPosition(lat, lon, alt):
        print('inside mocked sendPosition')
    iface.sendPosition.side_effect = mock_sendPosition
    iface.localNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        print('out:', out)
        print('err:', err)
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Fixing latitude', out, re.MULTILINE)
        assert re.search(r'Setting device position', out, re.MULTILINE)
        assert re.search(r'inside mocked sendPosition', out, re.MULTILINE)
        # TODO: Why does this not work? assert re.search(r'inside mocked writeConfig', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_setlon(capsys):
    """Test --setlon"""
    sys.argv = ['', '--setlon', '-122.1']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    our_globals.set_target_node(None)

    mocked_node = MagicMock(autospec=Node)
    def mock_writeConfig():
        print('inside mocked writeConfig')
    mocked_node.writeConfig.side_effect = mock_writeConfig

    iface = MagicMock(autospec=SerialInterface)
    def mock_sendPosition(lat, lon, alt):
        print('inside mocked sendPosition')
    iface.sendPosition.side_effect = mock_sendPosition
    iface.localNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        print('out:', out)
        print('err:', err)
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Fixing longitude', out, re.MULTILINE)
        assert re.search(r'Setting device position', out, re.MULTILINE)
        assert re.search(r'inside mocked sendPosition', out, re.MULTILINE)
        # TODO: Why does this not work? assert re.search(r'inside mocked writeConfig', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_setalt(capsys):
    """Test --setalt"""
    sys.argv = ['', '--setalt', '51']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    our_globals.set_target_node(None)

    mocked_node = MagicMock(autospec=Node)
    def mock_writeConfig():
        print('inside mocked writeConfig')
    mocked_node.writeConfig.side_effect = mock_writeConfig

    iface = MagicMock(autospec=SerialInterface)
    def mock_sendPosition(lat, lon, alt):
        print('inside mocked sendPosition')
    iface.sendPosition.side_effect = mock_sendPosition
    iface.localNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        print('out:', out)
        print('err:', err)
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Fixing altitude', out, re.MULTILINE)
        assert re.search(r'Setting device position', out, re.MULTILINE)
        assert re.search(r'inside mocked sendPosition', out, re.MULTILINE)
        # TODO: Why does this not work? assert re.search(r'inside mocked writeConfig', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_set_team_valid(capsys):
    """Test --set-team"""
    sys.argv = ['', '--set-team', 'CYAN']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    our_globals.set_target_node(None)

    mocked_node = MagicMock(autospec=Node)
    def mock_setOwner(team):
        print('inside mocked setOwner')
    mocked_node.setOwner.side_effect = mock_setOwner

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with patch('meshtastic.mesh_pb2.Team') as mm:
            mm.Name.return_value = 'FAKENAME'
            mm.Value.return_value = 'FAKEVAL'
            main()
            out, err = capsys.readouterr()
            print('out:', out)
            print('err:', err)
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'Setting team to', out, re.MULTILINE)
            assert err == ''
            mo.assert_called()
            mm.Name.assert_called()
            mm.Value.assert_called()


@pytest.mark.unit
def test_main_set_team_invalid(capsys):
    """Test --set-team using an invalid team name"""
    sys.argv = ['', '--set-team', 'NOTCYAN']
    args = sys.argv
    parser = None
    parser = argparse.ArgumentParser()
    our_globals = Globals.getInstance()
    our_globals.set_parser(parser)
    our_globals.set_args(args)
    our_globals.set_target_node(None)

    iface = MagicMock(autospec=SerialInterface)

    def throw_an_exception(exc):
        raise ValueError("Fake exception.")

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with patch('meshtastic.mesh_pb2.Team') as mm:
            mm.Value.side_effect = throw_an_exception
            main()
            out, err = capsys.readouterr()
            print('out:', out)
            print('err:', err)
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'ERROR: Team', out, re.MULTILINE)
            assert err == ''
            mo.assert_called()
            mm.Value.assert_called()
