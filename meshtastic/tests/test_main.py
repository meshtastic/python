"""Meshtastic unit tests for __main__.py"""

import sys
import re

from unittest.mock import patch, MagicMock
import pytest

from meshtastic.__main__ import initParser, main, Globals
import meshtastic.radioconfig_pb2
from ..serial_interface import SerialInterface
from ..node import Node
from ..channel_pb2 import Channel


@pytest.mark.unit
def test_main_init_parser_no_args(capsys, reset_globals):
    """Test no arguments"""
    sys.argv = ['']
    Globals.getInstance().set_args(sys.argv)
    initParser()
    out, err = capsys.readouterr()
    assert out == ''
    assert err == ''


@pytest.mark.unit
def test_main_init_parser_version(capsys, reset_globals):
    """Test --version"""
    sys.argv = ['', '--version']
    Globals.getInstance().set_args(sys.argv)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        initParser()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    out, err = capsys.readouterr()
    assert re.match(r'[0-9]+\.[0-9]+\.[0-9]', out)
    assert err == ''


@pytest.mark.unit
def test_main_main_version(capsys, reset_globals):
    """Test --version"""
    sys.argv = ['', '--version']
    Globals.getInstance().set_args(sys.argv)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    out, err = capsys.readouterr()
    assert re.match(r'[0-9]+\.[0-9]+\.[0-9]', out)
    assert err == ''


@pytest.mark.unit
def test_main_main_no_args(reset_globals):
    """Test with no args"""
    sys.argv = ['']
    Globals.getInstance().set_args(sys.argv)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


@pytest.mark.unit
def test_main_support(capsys, reset_globals):
    """Test --support"""
    sys.argv = ['', '--support']
    Globals.getInstance().set_args(sys.argv)

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
def test_main_ch_index_no_devices(patched_find_ports, capsys, reset_globals):
    """Test --ch-index 1"""
    sys.argv = ['', '--ch-index', '1']
    Globals.getInstance().set_args(sys.argv)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert Globals.getInstance().get_channel_index() == 1
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.search(r'Warning: No Meshtastic devices detected', out, re.MULTILINE)
    assert err == ''
    patched_find_ports.assert_called()


@pytest.mark.unit
@patch('meshtastic.util.findPorts', return_value=[])
def test_main_test_no_ports(patched_find_ports, reset_globals):
    """Test --test with no hardware"""
    sys.argv = ['', '--test']
    Globals.getInstance().set_args(sys.argv)

    assert Globals.getInstance().get_target_node() is None
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    patched_find_ports.assert_called()


@pytest.mark.unit
@patch('meshtastic.util.findPorts', return_value=['/dev/ttyFake1'])
def test_main_test_one_port(patched_find_ports, reset_globals):
    """Test --test with one fake port"""
    sys.argv = ['', '--test']
    Globals.getInstance().set_args(sys.argv)

    assert Globals.getInstance().get_target_node() is None
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    patched_find_ports.assert_called()


@pytest.mark.unit
@patch('meshtastic.test.testAll', return_value=True)
@patch('meshtastic.util.findPorts', return_value=['/dev/ttyFake1', '/dev/ttyFake2'])
def test_main_test_two_ports_success(patched_find_ports, patched_test_all, reset_globals):
    """Test --test two fake ports and testAll() is a simulated success"""
    sys.argv = ['', '--test']
    Globals.getInstance().set_args(sys.argv)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    # TODO: why does this fail? patched_find_ports.assert_called()
    patched_test_all.assert_called()


@pytest.mark.unit
@patch('meshtastic.test.testAll', return_value=False)
@patch('meshtastic.util.findPorts', return_value=['/dev/ttyFake1', '/dev/ttyFake2'])
def test_main_test_two_ports_fails(patched_find_ports, patched_test_all, reset_globals):
    """Test --test two fake ports and testAll() is a simulated failure"""
    sys.argv = ['', '--test']
    Globals.getInstance().set_args(sys.argv)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    # TODO: why does this fail? patched_find_ports.assert_called()
    patched_test_all.assert_called()


@pytest.mark.unit
def test_main_info(capsys, reset_globals):
    """Test --info"""
    sys.argv = ['', '--info']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    def mock_showInfo():
        print('inside mocked showInfo')
    iface.showInfo.side_effect = mock_showInfo
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'inside mocked showInfo', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_qr(capsys, reset_globals):
    """Test --qr"""
    sys.argv = ['', '--qr']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    # TODO: could mock/check url
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Primary channel URL', out, re.MULTILINE)
        # if a qr code is generated it will have lots of these
        assert re.search(r'\[7m', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_nodes(capsys, reset_globals):
    """Test --nodes"""
    sys.argv = ['', '--nodes']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    def mock_showNodes():
        print('inside mocked showNodes')
    iface.showNodes.side_effect = mock_showNodes
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'inside mocked showNodes', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_set_owner_to_bob(capsys, reset_globals):
    """Test --set-owner bob"""
    sys.argv = ['', '--set-owner', 'bob']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Setting device owner to bob', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_set_ham_to_KI123(capsys, reset_globals):
    """Test --set-ham KI123"""
    sys.argv = ['', '--set-ham', 'KI123']
    Globals.getInstance().set_args(sys.argv)

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
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Setting HAM ID to KI123', out, re.MULTILINE)
        assert re.search(r'inside mocked setOwner', out, re.MULTILINE)
        assert re.search(r'inside mocked turnOffEncryptionOnPrimaryChannel', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_reboot(capsys, reset_globals):
    """Test --reboot"""
    sys.argv = ['', '--reboot']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)
    def mock_reboot():
        print('inside mocked reboot')
    mocked_node.reboot.side_effect = mock_reboot

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'inside mocked reboot', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_sendtext(capsys, reset_globals):
    """Test --sendtext"""
    sys.argv = ['', '--sendtext', 'hello']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    def mock_sendText(text, dest, wantAck):
        print('inside mocked sendText')
    iface.sendText.side_effect = mock_sendText

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Sending text message', out, re.MULTILINE)
        assert re.search(r'inside mocked sendText', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_sendping(capsys, reset_globals):
    """Test --sendping"""
    sys.argv = ['', '--sendping']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    def mock_sendData(payload, dest, portNum, wantAck, wantResponse):
        print('inside mocked sendData')
    iface.sendData.side_effect = mock_sendData

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Sending ping message', out, re.MULTILINE)
        assert re.search(r'inside mocked sendData', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_setlat(capsys, reset_globals):
    """Test --sendlat"""
    sys.argv = ['', '--setlat', '37.5']
    Globals.getInstance().set_args(sys.argv)

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
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Fixing latitude', out, re.MULTILINE)
        assert re.search(r'Setting device position', out, re.MULTILINE)
        assert re.search(r'inside mocked sendPosition', out, re.MULTILINE)
        # TODO: Why does this not work? assert re.search(r'inside mocked writeConfig', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_setlon(capsys, reset_globals):
    """Test --setlon"""
    sys.argv = ['', '--setlon', '-122.1']
    Globals.getInstance().set_args(sys.argv)

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
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Fixing longitude', out, re.MULTILINE)
        assert re.search(r'Setting device position', out, re.MULTILINE)
        assert re.search(r'inside mocked sendPosition', out, re.MULTILINE)
        # TODO: Why does this not work? assert re.search(r'inside mocked writeConfig', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_setalt(capsys, reset_globals):
    """Test --setalt"""
    sys.argv = ['', '--setalt', '51']
    Globals.getInstance().set_args(sys.argv)

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
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Fixing altitude', out, re.MULTILINE)
        assert re.search(r'Setting device position', out, re.MULTILINE)
        assert re.search(r'inside mocked sendPosition', out, re.MULTILINE)
        # TODO: Why does this not work? assert re.search(r'inside mocked writeConfig', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_set_team_valid(capsys, reset_globals):
    """Test --set-team"""
    sys.argv = ['', '--set-team', 'CYAN']
    Globals.getInstance().set_args(sys.argv)

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
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'Setting team to', out, re.MULTILINE)
            assert err == ''
            mo.assert_called()
            mm.Name.assert_called()
            mm.Value.assert_called()


@pytest.mark.unit
def test_main_set_team_invalid(capsys, reset_globals):
    """Test --set-team using an invalid team name"""
    sys.argv = ['', '--set-team', 'NOTCYAN']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)

    def throw_an_exception(exc):
        raise ValueError("Fake exception.")

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with patch('meshtastic.mesh_pb2.Team') as mm:
            mm.Value.side_effect = throw_an_exception
            main()
            out, err = capsys.readouterr()
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'ERROR: Team', out, re.MULTILINE)
            assert err == ''
            mo.assert_called()
            mm.Value.assert_called()


@pytest.mark.unit
def test_main_seturl(capsys, reset_globals):
    """Test --seturl (url used below is what is generated after a factory_reset)"""
    sys.argv = ['', '--seturl', 'https://www.meshtastic.org/d/#CgUYAyIBAQ']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_set_valid(capsys, reset_globals):
    """Test --set with valid field"""
    sys.argv = ['', '--set', 'wifi_ssid', 'foo']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Set wifi_ssid to foo', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_set_with_invalid(capsys, reset_globals):
    """Test --set with invalid field"""
    sys.argv = ['', '--set', 'foo', 'foo']
    Globals.getInstance().set_args(sys.argv)

    mocked_user_prefs = MagicMock()
    mocked_user_prefs.DESCRIPTOR.fields_by_name.get.return_value = None

    mocked_node = MagicMock(autospec=Node)
    mocked_node.radioConfig.preferences = ( mocked_user_prefs )

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'does not have an attribute called foo', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


# TODO: write some negative --configure tests
@pytest.mark.unit
def test_main_configure(capsys, reset_globals):
    """Test --configure with valid file"""
    sys.argv = ['', '--configure', 'example_config.yaml']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Setting device owner', out, re.MULTILINE)
        assert re.search(r'Setting channel url', out, re.MULTILINE)
        assert re.search(r'Fixing altitude', out, re.MULTILINE)
        assert re.search(r'Fixing latitude', out, re.MULTILINE)
        assert re.search(r'Fixing longitude', out, re.MULTILINE)
        assert re.search(r'Writing modified preferences', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_add_valid(capsys, reset_globals):
    """Test --ch-add with valid channel name, and that channel name does not already exist"""
    sys.argv = ['', '--ch-add', 'testing']
    Globals.getInstance().set_args(sys.argv)

    mocked_channel = MagicMock(autospec=Channel)
    # TODO: figure out how to get it to print the channel name instead of MagicMock

    mocked_node = MagicMock(autospec=Node)
    # set it up so we do not already have a channel named this
    mocked_node.getChannelByName.return_value = False
    # set it up so we have free channels
    mocked_node.getDisabledChannel.return_value = mocked_channel

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Writing modified channels to device', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_add_invalid_name_too_long(capsys, reset_globals):
    """Test --ch-add with invalid channel name, name too long"""
    sys.argv = ['', '--ch-add', 'testingtestingtesting']
    Globals.getInstance().set_args(sys.argv)

    mocked_channel = MagicMock(autospec=Channel)
    # TODO: figure out how to get it to print the channel name instead of MagicMock

    mocked_node = MagicMock(autospec=Node)
    # set it up so we do not already have a channel named this
    mocked_node.getChannelByName.return_value = False
    # set it up so we have free channels
    mocked_node.getDisabledChannel.return_value = mocked_channel

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Warning: Channel name must be shorter', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_add_but_name_already_exists(capsys, reset_globals):
    """Test --ch-add with a channel name that already exists"""
    sys.argv = ['', '--ch-add', 'testing']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)
    # set it up so we do not already have a channel named this
    mocked_node.getChannelByName.return_value = True

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Warning: This node already has', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_add_but_no_more_channels(capsys, reset_globals):
    """Test --ch-add with but there are no more channels"""
    sys.argv = ['', '--ch-add', 'testing']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)
    # set it up so we do not already have a channel named this
    mocked_node.getChannelByName.return_value = False
    # set it up so we have free channels
    mocked_node.getDisabledChannel.return_value = None

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Warning: No free channels were found', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_del(capsys, reset_globals):
    """Test --ch-del with valid secondary channel to be deleted"""
    sys.argv = ['', '--ch-del', '--ch-index', '1']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Deleting channel', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_del_no_ch_index_specified(capsys, reset_globals):
    """Test --ch-del without a valid ch-index"""
    sys.argv = ['', '--ch-del']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Warning: Need to specify', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_del_primary_channel(capsys, reset_globals):
    """Test --ch-del on ch-index=0"""
    sys.argv = ['', '--ch-del', '--ch-index', '0']
    Globals.getInstance().set_args(sys.argv)
    Globals.getInstance().set_channel_index(1)

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Warning: Cannot delete primary channel', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_enable_valid_secondary_channel(capsys, reset_globals):
    """Test --ch-enable with --ch-index"""
    sys.argv = ['', '--ch-enable', '--ch-index', '1']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Writing modified channels', out, re.MULTILINE)
        assert err == ''
        assert Globals.getInstance().get_channel_index() == 1
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_disable_valid_secondary_channel(capsys, reset_globals):
    """Test --ch-disable with --ch-index"""
    sys.argv = ['', '--ch-disable', '--ch-index', '1']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Writing modified channels', out, re.MULTILINE)
        assert err == ''
        assert Globals.getInstance().get_channel_index() == 1
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_enable_without_a_ch_index(capsys, reset_globals):
    """Test --ch-enable without --ch-index"""
    sys.argv = ['', '--ch-enable']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Warning: Need to specify', out, re.MULTILINE)
        assert err == ''
        assert Globals.getInstance().get_channel_index() is None
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_enable_primary_channel(capsys, reset_globals):
    """Test --ch-enable with --ch-index = 0"""
    sys.argv = ['', '--ch-enable', '--ch-index', '0']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Warning: Cannot enable/disable PRIMARY', out, re.MULTILINE)
        assert err == ''
        assert Globals.getInstance().get_channel_index() == 0
        mo.assert_called()


@pytest.mark.unit
def test_main_ch_range_options(capsys, reset_globals):
    """Test changing the various range options."""
    range_options = ['--ch-longslow', '--ch-longfast', '--ch-mediumslow',
                     '--ch-mediumfast', '--ch-shortslow', '--ch-shortfast']
    for range_option in range_options:
        sys.argv = ['', f"{range_option}" ]
        Globals.getInstance().set_args(sys.argv)

        mocked_node = MagicMock(autospec=Node)

        iface = MagicMock(autospec=SerialInterface)
        iface.getNode.return_value = mocked_node

        with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
            main()
            out, err = capsys.readouterr()
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'Writing modified channels', out, re.MULTILINE)
            assert err == ''
            mo.assert_called()


@pytest.mark.unit
def test_main_ch_longsfast_on_non_primary_channel(capsys, reset_globals):
    """Test --ch-longfast --ch-index 1"""
    sys.argv = ['', '--ch-longfast', '--ch-index', '1']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Warning: Standard channel settings', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


# PositionFlags:
# Misc info that might be helpful (this info will grow stale, just
# a snapshot of the values.) The radioconfig_pb2.PositionFlags.Name and bit values are:
# POS_UNDEFINED 0
# POS_ALTITUDE 1
# POS_ALT_MSL 2
# POS_GEO_SEP 4
# POS_DOP 8
# POS_HVDOP 16
# POS_BATTERY 32
# POS_SATINVIEW 64
# POS_SEQ_NOS 128
# POS_TIMESTAMP 256

@pytest.mark.unit
def test_main_pos_fields_no_args(capsys, reset_globals):
    """Test --pos-fields no args (which shows settings)"""
    sys.argv = ['', '--pos-fields']
    Globals.getInstance().set_args(sys.argv)

    pos_flags = MagicMock(autospec=meshtastic.radioconfig_pb2.PositionFlags)

    with patch('meshtastic.serial_interface.SerialInterface') as mo:
        with patch('meshtastic.radioconfig_pb2.PositionFlags', return_value=pos_flags) as mrc:
            # kind of cheating here, we are setting up the node
            mocked_node = MagicMock(autospec=Node)
            anode = mocked_node()
            anode.radioConfig.preferences.position_flags = 35
            Globals.getInstance().set_target_node(anode)

            mrc.values.return_value = [0, 1, 2, 4, 8, 16, 32, 64, 128, 256]
            # Note: When you use side_effect and a list, each call will use a value from the front of the list then
            # remove that value from the list. If there are three values in the list, we expect it to be called
            # three times.
            mrc.Name.side_effect = [ 'POS_ALTITUDE', 'POS_ALT_MSL', 'POS_BATTERY' ]

            main()

            mrc.Name.assert_called()
            mrc.values.assert_called()
            mo.assert_called()

            out, err = capsys.readouterr()
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'POS_ALTITUDE POS_ALT_MSL POS_BATTERY', out, re.MULTILINE)
            assert err == ''


@pytest.mark.unit
def test_main_pos_fields_arg_of_zero(capsys, reset_globals):
    """Test --pos-fields an arg of 0 (which shows list)"""
    sys.argv = ['', '--pos-fields', '0']
    Globals.getInstance().set_args(sys.argv)

    pos_flags = MagicMock(autospec=meshtastic.radioconfig_pb2.PositionFlags)

    with patch('meshtastic.serial_interface.SerialInterface') as mo:
        with patch('meshtastic.radioconfig_pb2.PositionFlags', return_value=pos_flags) as mrc:

            def throw_value_error_exception(exc):
                raise ValueError()
            mrc.Value.side_effect = throw_value_error_exception
            mrc.keys.return_value = [ 'POS_UNDEFINED', 'POS_ALTITUDE', 'POS_ALT_MSL',
                                      'POS_GEO_SEP', 'POS_DOP', 'POS_HVDOP', 'POS_BATTERY',
                                      'POS_SATINVIEW', 'POS_SEQ_NOS', 'POS_TIMESTAMP']

            main()

            mrc.Value.assert_called()
            mrc.keys.assert_called()
            mo.assert_called()

            out, err = capsys.readouterr()
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'ERROR: supported position fields are:', out, re.MULTILINE)
            assert re.search(r"['POS_UNDEFINED', 'POS_ALTITUDE', 'POS_ALT_MSL', 'POS_GEO_SEP',"\
                              "'POS_DOP', 'POS_HVDOP', 'POS_BATTERY', 'POS_SATINVIEW', 'POS_SEQ_NOS',"\
                              "'POS_TIMESTAMP']", out, re.MULTILINE)
            assert err == ''


@pytest.mark.unit
def test_main_pos_fields_valid_values(capsys, reset_globals):
    """Test --pos-fields with valid values"""
    sys.argv = ['', '--pos-fields', 'POS_GEO_SEP', 'POS_ALT_MSL']
    Globals.getInstance().set_args(sys.argv)

    pos_flags = MagicMock(autospec=meshtastic.radioconfig_pb2.PositionFlags)

    with patch('meshtastic.serial_interface.SerialInterface') as mo:
        with patch('meshtastic.radioconfig_pb2.PositionFlags', return_value=pos_flags) as mrc:

            mrc.Value.side_effect = [ 4, 2 ]

            main()

            mrc.Value.assert_called()
            mo.assert_called()

            out, err = capsys.readouterr()
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'Setting position fields to 6', out, re.MULTILINE)
            assert re.search(r'Set position_flags to 6', out, re.MULTILINE)
            assert re.search(r'Writing modified preferences to device', out, re.MULTILINE)
            assert err == ''
