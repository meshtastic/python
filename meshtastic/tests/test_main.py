"""Meshtastic unit tests for __main__.py"""
# pylint: disable=C0302

import sys
import os
import re
import logging
import platform

from unittest.mock import patch, MagicMock
import pytest

from meshtastic.__main__ import initParser, main, Globals, onReceive, onConnection, export_config, getPref, setPref, onNode, tunnelMain
#from ..radioconfig_pb2 import UserPreferences
import meshtastic.radioconfig_pb2
from ..serial_interface import SerialInterface
from ..tcp_interface import TCPInterface
#from ..ble_interface import BLEInterface
from ..node import Node
from ..channel_pb2 import Channel
from ..remote_hardware import onGPIOreceive
from ..radioconfig_pb2 import RadioConfig


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_init_parser_no_args(capsys):
    """Test no arguments"""
    sys.argv = ['']
    Globals.getInstance().set_args(sys.argv)
    initParser()
    out, err = capsys.readouterr()
    assert out == ''
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_init_parser_version(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_main_version(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_main_no_args(capsys):
    """Test with no args"""
    sys.argv = ['']
    Globals.getInstance().set_args(sys.argv)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    _, err = capsys.readouterr()
    assert re.search(r'usage:', err, re.MULTILINE)


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_support(capsys):
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
@pytest.mark.usefixtures("reset_globals")
@patch('meshtastic.util.findPorts', return_value=[])
def test_main_ch_index_no_devices(patched_find_ports, capsys):
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
@pytest.mark.usefixtures("reset_globals")
@patch('meshtastic.util.findPorts', return_value=[])
def test_main_test_no_ports(patched_find_ports, capsys):
    """Test --test with no hardware"""
    sys.argv = ['', '--test']
    Globals.getInstance().set_args(sys.argv)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    patched_find_ports.assert_called()
    out, err = capsys.readouterr()
    assert re.search(r'Warning: Must have at least two devices connected to USB', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
@patch('meshtastic.util.findPorts', return_value=['/dev/ttyFake1'])
def test_main_test_one_port(patched_find_ports, capsys):
    """Test --test with one fake port"""
    sys.argv = ['', '--test']
    Globals.getInstance().set_args(sys.argv)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    patched_find_ports.assert_called()
    out, err = capsys.readouterr()
    assert re.search(r'Warning: Must have at least two devices connected to USB', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
@patch('meshtastic.test.testAll', return_value=True)
def test_main_test_two_ports_success(patched_test_all, capsys):
    """Test --test two fake ports and testAll() is a simulated success"""
    sys.argv = ['', '--test']
    Globals.getInstance().set_args(sys.argv)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    patched_test_all.assert_called()
    out, err = capsys.readouterr()
    assert re.search(r'Test was a success.', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
@patch('meshtastic.test.testAll', return_value=False)
def test_main_test_two_ports_fails(patched_test_all, capsys):
    """Test --test two fake ports and testAll() is a simulated failure"""
    sys.argv = ['', '--test']
    Globals.getInstance().set_args(sys.argv)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    patched_test_all.assert_called()
    out, err = capsys.readouterr()
    assert re.search(r'Test was not successful.', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_info(capsys, caplog):
    """Test --info"""
    sys.argv = ['', '--info']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    def mock_showInfo():
        print('inside mocked showInfo')
    iface.showInfo.side_effect = mock_showInfo
    with caplog.at_level(logging.DEBUG):
        with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
            main()
            out, err = capsys.readouterr()
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'inside mocked showInfo', out, re.MULTILINE)
            assert err == ''
            mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
@patch('os.getlogin')
def test_main_info_with_permission_error(patched_getlogin, capsys, caplog):
    """Test --info"""
    sys.argv = ['', '--info']
    Globals.getInstance().set_args(sys.argv)

    patched_getlogin.return_value = 'me'

    iface = MagicMock(autospec=SerialInterface)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
                mo.side_effect = PermissionError('bla bla')
                main()
            assert pytest_wrapped_e.type == SystemExit
            assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        patched_getlogin.assert_called()
        assert re.search(r'Need to add yourself', out, re.MULTILINE)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_info_with_tcp_interface(capsys):
    """Test --info"""
    sys.argv = ['', '--info', '--host', 'meshtastic.local']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=TCPInterface)
    def mock_showInfo():
        print('inside mocked showInfo')
    iface.showInfo.side_effect = mock_showInfo
    with patch('meshtastic.tcp_interface.TCPInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'inside mocked showInfo', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


# TODO: comment out ble (for now)
#@pytest.mark.unit
#def test_main_info_with_ble_interface(capsys):
#    """Test --info"""
#    sys.argv = ['', '--info', '--ble', 'foo']
#    Globals.getInstance().set_args(sys.argv)
#
#    iface = MagicMock(autospec=BLEInterface)
#    def mock_showInfo():
#        print('inside mocked showInfo')
#    iface.showInfo.side_effect = mock_showInfo
#    with patch('meshtastic.ble_interface.BLEInterface', return_value=iface) as mo:
#        main()
#        out, err = capsys.readouterr()
#        assert re.search(r'Connected to radio', out, re.MULTILINE)
#        assert re.search(r'inside mocked showInfo', out, re.MULTILINE)
#        assert err == ''
#        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_no_proto(capsys):
    """Test --noproto (using --info for output)"""
    sys.argv = ['', '--info', '--noproto']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    def mock_showInfo():
        print('inside mocked showInfo')
    iface.showInfo.side_effect = mock_showInfo

    # Override the time.sleep so there is no loop
    def my_sleep(amount):
        print(f'amount:{amount}')
        sys.exit(0)

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface):
        with patch('time.sleep', side_effect=my_sleep):
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                main()
            assert pytest_wrapped_e.type == SystemExit
            assert pytest_wrapped_e.value.code == 0
            out, err = capsys.readouterr()
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'inside mocked showInfo', out, re.MULTILINE)
            assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_info_with_seriallog_stdout(capsys):
    """Test --info"""
    sys.argv = ['', '--info', '--seriallog', 'stdout']
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
@pytest.mark.usefixtures("reset_globals")
def test_main_info_with_seriallog_output_txt(capsys):
    """Test --info"""
    sys.argv = ['', '--info', '--seriallog', 'output.txt']
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
    # do some cleanup
    os.remove('output.txt')


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_qr(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_onConnected_exception(capsys):
    """Test the exception in onConnected"""
    sys.argv = ['', '--qr']
    Globals.getInstance().set_args(sys.argv)

    def throw_an_exception(junk):
        raise Exception("Fake exception.")

    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface):
        with patch('pyqrcode.create', side_effect=throw_an_exception):
            with pytest.raises(Exception) as pytest_wrapped_e:
                main()
                out, err = capsys.readouterr()
                assert re.search('Aborting due to: Fake exception', out, re.MULTILINE)
                assert err == ''
                assert pytest_wrapped_e.type == Exception


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_nodes(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_set_owner_to_bob(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_set_ham_to_KI123(capsys):
    """Test --set-ham KI123"""
    sys.argv = ['', '--set-ham', 'KI123']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)
    def mock_turnOffEncryptionOnPrimaryChannel():
        print('inside mocked turnOffEncryptionOnPrimaryChannel')
    def mock_setOwner(name, is_licensed):
        print(f'inside mocked setOwner name:{name} is_licensed:{is_licensed}')
    mocked_node.turnOffEncryptionOnPrimaryChannel.side_effect = mock_turnOffEncryptionOnPrimaryChannel
    mocked_node.setOwner.side_effect = mock_setOwner

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Setting Ham ID to KI123', out, re.MULTILINE)
        assert re.search(r'inside mocked setOwner', out, re.MULTILINE)
        assert re.search(r'inside mocked turnOffEncryptionOnPrimaryChannel', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_reboot(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_shutdown(capsys):
    """Test --shutdown"""
    sys.argv = ['', '--shutdown']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)
    def mock_shutdown():
        print('inside mocked shutdown')
    mocked_node.shutdown.side_effect = mock_shutdown

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'inside mocked shutdown', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_sendtext(capsys):
    """Test --sendtext"""
    sys.argv = ['', '--sendtext', 'hello']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    def mock_sendText(text, dest, wantAck, channelIndex):
        print('inside mocked sendText')
        print(f'{text} {dest} {wantAck} {channelIndex}')
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
@pytest.mark.usefixtures("reset_globals")
def test_main_sendtext_with_channel(capsys):
    """Test --sendtext"""
    sys.argv = ['', '--sendtext', 'hello', '--ch-index', '1']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    def mock_sendText(text, dest, wantAck, channelIndex):
        print('inside mocked sendText')
        print(f'{text} {dest} {wantAck} {channelIndex}')
    iface.sendText.side_effect = mock_sendText

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Sending text message', out, re.MULTILINE)
        assert re.search(r'on channelIndex:1', out, re.MULTILINE)
        assert re.search(r'inside mocked sendText', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_sendtext_with_invalid_channel(caplog, capsys):
    """Test --sendtext"""
    sys.argv = ['', '--sendtext', 'hello', '--ch-index', '-1']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode.getChannelByChannelIndex.return_value = None

    with caplog.at_level(logging.DEBUG):
        with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                main()
            assert pytest_wrapped_e.type == SystemExit
            assert pytest_wrapped_e.value.code == 1
            out, err = capsys.readouterr()
            assert re.search(r'is not a valid channel', out, re.MULTILINE)
            assert err == ''
            mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_sendtext_with_invalid_channel_nine(caplog, capsys):
    """Test --sendtext"""
    sys.argv = ['', '--sendtext', 'hello', '--ch-index', '9']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode.getChannelByChannelIndex.return_value = None

    with caplog.at_level(logging.DEBUG):
        with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                main()
            assert pytest_wrapped_e.type == SystemExit
            assert pytest_wrapped_e.value.code == 1
            out, err = capsys.readouterr()
            assert re.search(r'is not a valid channel', out, re.MULTILINE)
            assert err == ''
            mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_sendtext_with_dest(capsys, caplog, iface_with_nodes):
    """Test --sendtext with --dest"""
    sys.argv = ['', '--sendtext', 'hello', '--dest', 'foo']
    Globals.getInstance().set_args(sys.argv)

    iface = iface_with_nodes
    iface.myInfo.my_node_num = 2475227164
    mocked_channel = MagicMock(autospec=Channel)
    iface.localNode.getChannelByChannelIndex = mocked_channel

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface):
        with caplog.at_level(logging.DEBUG):

            with pytest.raises(SystemExit) as pytest_wrapped_e:
                main()
            assert pytest_wrapped_e.type == SystemExit
            assert pytest_wrapped_e.value.code == 1
            out, err = capsys.readouterr()
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert not re.search(r"Warning: 0 is not a valid channel", out, re.MULTILINE)
            assert not re.search(r"There is a SECONDARY channel named 'admin'", out, re.MULTILINE)
            assert re.search(r'Warning: NodeId foo not found in DB', out, re.MULTILINE)
            assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_sendping(capsys):
    """Test --sendping"""
    sys.argv = ['', '--sendping']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    def mock_sendData(payload, dest, portNum, wantAck, wantResponse):
        print('inside mocked sendData')
        print(f'{payload} {dest} {portNum} {wantAck} {wantResponse}')
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
@pytest.mark.usefixtures("reset_globals")
def test_main_setlat(capsys):
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
        print(f'{lat} {lon} {alt}')
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
@pytest.mark.usefixtures("reset_globals")
def test_main_setlon(capsys):
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
        print(f'{lat} {lon} {alt}')
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
@pytest.mark.usefixtures("reset_globals")
def test_main_setalt(capsys):
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
        print(f'{lat} {lon} {alt}')
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
@pytest.mark.usefixtures("reset_globals")
def test_main_set_team_valid(capsys):
    """Test --set-team"""
    sys.argv = ['', '--set-team', 'CYAN']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)
    def mock_setOwner(team):
        print('inside mocked setOwner')
        print(f'{team}')
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
@pytest.mark.usefixtures("reset_globals")
def test_main_set_team_invalid(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_seturl(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_set_valid(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_set_valid_wifi_passwd(capsys):
    """Test --set with valid field"""
    sys.argv = ['', '--set', 'wifi_password', '123456789']
    Globals.getInstance().set_args(sys.argv)

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Set wifi_password to 123456789', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_set_valid_camel_case(capsys):
    """Test --set with valid field"""
    sys.argv = ['', '--set', 'wifi_ssid', 'foo']
    Globals.getInstance().set_args(sys.argv)
    Globals.getInstance().set_camel_case()

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'Set wifiSsid to foo', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_set_with_invalid(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_configure_with_snake_case(capsys):
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
        assert re.search(r'Set location_share to LocEnabled', out, re.MULTILINE)
        assert re.search(r'Writing modified preferences', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_configure_with_camel_case_keys(capsys):
    """Test --configure with valid file"""
    sys.argv = ['', '--configure', 'exampleConfig.yaml']
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_add_valid(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_add_invalid_name_too_long(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_add_but_name_already_exists(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_add_but_no_more_channels(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_del(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_del_no_ch_index_specified(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_del_primary_channel(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_enable_valid_secondary_channel(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_disable_valid_secondary_channel(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_enable_without_a_ch_index(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_enable_primary_channel(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_range_options(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_longsfast_on_non_primary_channel(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_pos_fields_no_args(capsys):
    """Test --pos-fields no args (which shows settings)"""
    sys.argv = ['', '--pos-fields']
    Globals.getInstance().set_args(sys.argv)

    pos_flags = MagicMock(autospec=meshtastic.radioconfig_pb2.PositionFlags)

    with patch('meshtastic.serial_interface.SerialInterface') as mo:
        mo().getNode().radioConfig.preferences.position_flags = 35
        with patch('meshtastic.radioconfig_pb2.PositionFlags', return_value=pos_flags) as mrc:

            mrc.values.return_value = [0, 1, 2, 4, 8, 16, 32, 64, 128, 256]
            # Note: When you use side_effect and a list, each call will use a value from the front of the list then
            # remove that value from the list. If there are three values in the list, we expect it to be called
            # three times.
            mrc.Name.side_effect = ['POS_ALTITUDE', 'POS_ALT_MSL', 'POS_BATTERY']

            main()

            mrc.Name.assert_called()
            mrc.values.assert_called()
            mo.assert_called()

            out, err = capsys.readouterr()
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'POS_ALTITUDE POS_ALT_MSL POS_BATTERY', out, re.MULTILINE)
            assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_pos_fields_arg_of_zero(capsys):
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
@pytest.mark.usefixtures("reset_globals")
def test_main_pos_fields_valid_values(capsys):
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


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_get_with_valid_values(capsys):
    """Test --get with valid values (with string, number, boolean)"""
    sys.argv = ['', '--get', 'ls_secs', '--get', 'wifi_ssid', '--get', 'fixed_position']
    Globals.getInstance().set_args(sys.argv)

    with patch('meshtastic.serial_interface.SerialInterface') as mo:

        mo().getNode().radioConfig.preferences.wifi_ssid = 'foo'
        mo().getNode().radioConfig.preferences.ls_secs = 300
        mo().getNode().radioConfig.preferences.fixed_position = False

        main()

        mo.assert_called()

        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'ls_secs: 300', out, re.MULTILINE)
        assert re.search(r'wifi_ssid: foo', out, re.MULTILINE)
        assert re.search(r'fixed_position: False', out, re.MULTILINE)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_get_with_valid_values_camel(capsys, caplog):
    """Test --get with valid values (with string, number, boolean)"""
    sys.argv = ['', '--get', 'lsSecs', '--get', 'wifiSsid', '--get', 'fixedPosition']
    Globals.getInstance().set_args(sys.argv)
    Globals.getInstance().set_camel_case()

    with caplog.at_level(logging.DEBUG):
        with patch('meshtastic.serial_interface.SerialInterface') as mo:

            mo().getNode().radioConfig.preferences.wifi_ssid = 'foo'
            mo().getNode().radioConfig.preferences.ls_secs = 300
            mo().getNode().radioConfig.preferences.fixed_position = False

            main()

            mo.assert_called()

            out, err = capsys.readouterr()
            assert re.search(r'Connected to radio', out, re.MULTILINE)
            assert re.search(r'lsSecs: 300', out, re.MULTILINE)
            assert re.search(r'wifiSsid: foo', out, re.MULTILINE)
            assert re.search(r'fixedPosition: False', out, re.MULTILINE)
            assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_get_with_invalid(capsys):
    """Test --get with invalid field"""
    sys.argv = ['', '--get', 'foo']
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
        assert re.search(r'Choices in sorted order are', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_setchan(capsys):
    """Test --setchan (deprecated)"""
    sys.argv = ['', '--setchan', 'a', 'b']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        _, err = capsys.readouterr()
        assert re.search(r'usage:', err, re.MULTILINE)


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_onReceive_empty(caplog, capsys):
    """Test onReceive"""
    args = MagicMock()
    Globals.getInstance().set_args(args)
    iface = MagicMock(autospec=SerialInterface)
    packet = {}
    with caplog.at_level(logging.DEBUG):
        onReceive(packet, iface)
    assert re.search(r'in onReceive', caplog.text, re.MULTILINE)
    out, err = capsys.readouterr()
    assert re.search(r"Warning: There is no field 'to' in the packet.", out, re.MULTILINE)
    assert err == ''


#    TODO: use this captured position app message (might want/need in the future)
#    packet = {
#            'to': 4294967295,
#            'decoded': {
#                'portnum': 'POSITION_APP',
#                'payload': "M69\306a"
#                },
#            'id': 334776976,
#            'hop_limit': 3
#            }

@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_onReceive_with_sendtext(caplog, capsys):
    """Test onReceive with sendtext
       The entire point of this test is to make sure the interface.close() call
       is made in onReceive().
    """
    sys.argv = ['', '--sendtext', 'hello']
    Globals.getInstance().set_args(sys.argv)

    # Note: 'TEXT_MESSAGE_APP' value is 1
    packet = {
            'to': 4294967295,
            'decoded': {
                'portnum': 1,
                'payload': "hello"
                },
            'id': 334776977,
            'hop_limit': 3,
            'want_ack': True
            }

    iface = MagicMock(autospec=SerialInterface)
    iface.myInfo.my_node_num = 4294967295

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with caplog.at_level(logging.DEBUG):
            main()
            onReceive(packet, iface)
        assert re.search(r'in onReceive', caplog.text, re.MULTILINE)
        mo.assert_called()
        out, err = capsys.readouterr()
        assert re.search(r'Sending text message hello to', out, re.MULTILINE)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_onReceive_with_text(caplog, capsys):
    """Test onReceive with text
    """
    args = MagicMock()
    args.sendtext.return_value = 'foo'
    Globals.getInstance().set_args(args)

    # Note: 'TEXT_MESSAGE_APP' value is 1
    # Note: Some of this is faked below.
    packet = {
            'to': 4294967295,
            'decoded': {
                'portnum': 1,
                'payload': "hello",
                'text': "faked"
                },
            'id': 334776977,
            'hop_limit': 3,
            'want_ack': True,
            'rxSnr': 6.0,
            'hopLimit': 3,
            'raw': 'faked',
            'fromId': '!28b5465c',
            'toId': '^all'
            }

    iface = MagicMock(autospec=SerialInterface)
    iface.myInfo.my_node_num = 4294967295

    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface):
        with caplog.at_level(logging.DEBUG):
            onReceive(packet, iface)
        assert re.search(r'in onReceive', caplog.text, re.MULTILINE)
        out, err = capsys.readouterr()
        assert re.search(r'Sending reply', out, re.MULTILINE)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_onConnection(capsys):
    """Test onConnection"""
    sys.argv = ['']
    Globals.getInstance().set_args(sys.argv)
    iface = MagicMock(autospec=SerialInterface)
    class TempTopic:
        """ temp class for topic """
        def getName(self):
            """ return the fake name of a topic"""
            return 'foo'
    mytopic = TempTopic()
    onConnection(iface, mytopic)
    out, err = capsys.readouterr()
    assert re.search(r'Connection changed: foo', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_export_config(capsys):
    """Test export_config() function directly"""
    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        mo.getLongName.return_value = 'foo'
        mo.localNode.getURL.return_value = 'bar'
        mo.getMyNodeInfo().get.return_value = { 'latitudeI': 1100000000, 'longitudeI': 1200000000,
                                                'altitude': 100, 'batteryLevel': 34, 'latitude': 110.0,
                                                'longitude': 120.0}
        mo.localNode.radioConfig.preferences = """phone_timeout_secs: 900
ls_secs: 300
position_broadcast_smart: true
fixed_position: true
position_flags: 35"""
        export_config(mo)
    out, err = capsys.readouterr()

    # ensure we do not output this line
    assert not re.search(r'Connected to radio', out, re.MULTILINE)

    assert re.search(r'owner: foo', out, re.MULTILINE)
    assert re.search(r'channel_url: bar', out, re.MULTILINE)
    assert re.search(r'location:', out, re.MULTILINE)
    assert re.search(r'lat: 110.0', out, re.MULTILINE)
    assert re.search(r'lon: 120.0', out, re.MULTILINE)
    assert re.search(r'alt: 100', out, re.MULTILINE)
    assert re.search(r'user_prefs:', out, re.MULTILINE)
    assert re.search(r'phone_timeout_secs: 900', out, re.MULTILINE)
    assert re.search(r'ls_secs: 300', out, re.MULTILINE)
    assert re.search(r"position_broadcast_smart: 'true'", out, re.MULTILINE)
    assert re.search(r"fixed_position: 'true'", out, re.MULTILINE)
    assert re.search(r"position_flags: 35", out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_export_config_use_camel(capsys):
    """Test export_config() function directly"""
    Globals.getInstance().set_camel_case()
    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        mo.getLongName.return_value = 'foo'
        mo.localNode.getURL.return_value = 'bar'
        mo.getMyNodeInfo().get.return_value = { 'latitudeI': 1100000000, 'longitudeI': 1200000000,
                                                'altitude': 100, 'batteryLevel': 34, 'latitude': 110.0,
                                                'longitude': 120.0}
        mo.localNode.radioConfig.preferences = """phone_timeout_secs: 900
ls_secs: 300
position_broadcast_smart: true
fixed_position: true
position_flags: 35"""
        export_config(mo)
    out, err = capsys.readouterr()

    # ensure we do not output this line
    assert not re.search(r'Connected to radio', out, re.MULTILINE)

    assert re.search(r'owner: foo', out, re.MULTILINE)
    assert re.search(r'channelUrl: bar', out, re.MULTILINE)
    assert re.search(r'location:', out, re.MULTILINE)
    assert re.search(r'lat: 110.0', out, re.MULTILINE)
    assert re.search(r'lon: 120.0', out, re.MULTILINE)
    assert re.search(r'alt: 100', out, re.MULTILINE)
    assert re.search(r'userPrefs:', out, re.MULTILINE)
    assert re.search(r'phoneTimeoutSecs: 900', out, re.MULTILINE)
    assert re.search(r'lsSecs: 300', out, re.MULTILINE)
    # TODO: should True be capitalized here?
    assert re.search(r"positionBroadcastSmart: 'True'", out, re.MULTILINE)
    assert re.search(r"fixedPosition: 'True'", out, re.MULTILINE)
    assert re.search(r"positionFlags: 35", out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_export_config_called_from_main(capsys):
    """Test --export-config"""
    sys.argv = ['', '--export-config']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert not re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r'# start of Meshtastic configure yaml', out, re.MULTILINE)
        assert err == ''
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_gpio_rd_no_gpio_channel(capsys):
    """Test --gpio_rd with no named gpio channel"""
    sys.argv = ['', '--gpio-rd', '0x10', '--dest', '!foo']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode.getChannelByName.return_value = None
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Warning: No channel named', out)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_gpio_rd_no_dest(capsys):
    """Test --gpio_rd with a named gpio channel but no dest was specified"""
    sys.argv = ['', '--gpio-rd', '0x2000']
    Globals.getInstance().set_args(sys.argv)

    channel = Channel(index=2, role=2)
    channel.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
    channel.settings.name = 'gpio'

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode.getChannelByName.return_value = channel
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Warning: Must use a destination node ID', out)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_gpio_rd(caplog, capsys):
    """Test --gpio_rd with a named gpio channel"""
    # Note: On the Heltec v2.1, there is a GPIO pin GPIO 13 that does not have a
    # red arrow (meaning ok to use for our purposes)
    # See https://resource.heltec.cn/download/WiFi_LoRa_32/WIFI_LoRa_32_V2.pdf
    # To find out the mask for GPIO 13, let us assign n as 13.
    # 1. Subtract 1 from n (n is now 12)
    # 2. Find the 2^n or 2^12 (4096)
    # 3. Convert 4096 decimal to hex (0x1000)
    # You can use python:
    # >>> print(hex(2**12))
    # 0x1000
    sys.argv = ['', '--gpio-rd', '0x1000', '--dest', '!1234']
    Globals.getInstance().set_args(sys.argv)

    channel = Channel(index=1, role=1)
    channel.settings.modem_config = 3
    channel.settings.psk = b'\x01'

    packet = {

            'from': 682968668,
            'to': 682968612,
            'channel': 1,
            'decoded': {
                'portnum': 'REMOTE_HARDWARE_APP',
                'payload': b'\x08\x05\x18\x80 ',
                'requestId': 1629980484,
                'remotehw': {
                    'typ': 'READ_GPIOS_REPLY',
                    'gpioValue': '4096',
                    'raw': 'faked',
                    'id': 1693085229,
                    'rxTime': 1640294262,
                    'rxSnr': 4.75,
                    'hopLimit': 3,
                    'wantAck': True,
                    }
                }
            }


    iface = MagicMock(autospec=SerialInterface)
    iface.localNode.getChannelByName.return_value = channel
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with caplog.at_level(logging.DEBUG):
            main()
            onGPIOreceive(packet, mo)
    assert re.search(r'readGPIOs nodeid:!1234 mask:4096', caplog.text, re.MULTILINE)
    out, err = capsys.readouterr()
    assert re.search(r'Connected to radio', out, re.MULTILINE)
    assert re.search(r'Reading GPIO mask 0x1000 ', out, re.MULTILINE)
    assert re.search(r'Received RemoteHardware typ=READ_GPIOS_REPLY, gpio_value=4096', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_getPref_valid_field(capsys):
    """Test getPref() with a valid field"""
    prefs = MagicMock()
    prefs.DESCRIPTOR.fields_by_name.get.return_value = 'ls_secs'
    prefs.wifi_ssid = 'foo'
    prefs.ls_secs = 300
    prefs.fixed_position = False

    getPref(prefs, 'ls_secs')
    out, err = capsys.readouterr()
    assert re.search(r'ls_secs: 300', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_getPref_valid_field_camel(capsys):
    """Test getPref() with a valid field"""
    Globals.getInstance().set_camel_case()
    prefs = MagicMock()
    prefs.DESCRIPTOR.fields_by_name.get.return_value = 'ls_secs'
    prefs.wifi_ssid = 'foo'
    prefs.ls_secs = 300
    prefs.fixed_position = False

    getPref(prefs, 'ls_secs')
    out, err = capsys.readouterr()
    assert re.search(r'lsSecs: 300', out, re.MULTILINE)
    assert err == ''

@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_getPref_valid_field_string(capsys):
    """Test getPref() with a valid field and value as a string"""
    prefs = MagicMock()
    prefs.DESCRIPTOR.fields_by_name.get.return_value = 'wifi_ssid'
    prefs.wifi_ssid = 'foo'
    prefs.ls_secs = 300
    prefs.fixed_position = False

    getPref(prefs, 'wifi_ssid')
    out, err = capsys.readouterr()
    assert re.search(r'wifi_ssid: foo', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_getPref_valid_field_string_camel(capsys):
    """Test getPref() with a valid field and value as a string"""
    Globals.getInstance().set_camel_case()
    prefs = MagicMock()
    prefs.DESCRIPTOR.fields_by_name.get.return_value = 'wifi_ssid'
    prefs.wifi_ssid = 'foo'
    prefs.ls_secs = 300
    prefs.fixed_position = False

    getPref(prefs, 'wifi_ssid')
    out, err = capsys.readouterr()
    assert re.search(r'wifiSsid: foo', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_getPref_valid_field_bool(capsys):
    """Test getPref() with a valid field and value as a bool"""
    prefs = MagicMock()
    prefs.DESCRIPTOR.fields_by_name.get.return_value = 'fixed_position'
    prefs.wifi_ssid = 'foo'
    prefs.ls_secs = 300
    prefs.fixed_position = False

    getPref(prefs, 'fixed_position')
    out, err = capsys.readouterr()
    assert re.search(r'fixed_position: False', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_getPref_valid_field_bool_camel(capsys):
    """Test getPref() with a valid field and value as a bool"""
    Globals.getInstance().set_camel_case()
    prefs = MagicMock()
    prefs.DESCRIPTOR.fields_by_name.get.return_value = 'fixed_position'
    prefs.wifi_ssid = 'foo'
    prefs.ls_secs = 300
    prefs.fixed_position = False

    getPref(prefs, 'fixed_position')
    out, err = capsys.readouterr()
    assert re.search(r'fixedPosition: False', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_getPref_invalid_field(capsys):
    """Test getPref() with an invalid field"""

    class Field:
        """Simple class for testing."""

        def __init__(self, name):
            """constructor"""
            self.name = name

    prefs = MagicMock()
    prefs.DESCRIPTOR.fields_by_name.get.return_value = None

    # Note: This is a subset of the real fields
    ls_secs_field = Field('ls_secs')
    is_router = Field('is_router')
    fixed_position = Field('fixed_position')

    fields = [ ls_secs_field, is_router, fixed_position ]
    prefs.DESCRIPTOR.fields = fields

    getPref(prefs, 'foo')

    out, err = capsys.readouterr()
    assert re.search(r'does not have an attribute called foo', out, re.MULTILINE)
    # ensure they are sorted
    assert re.search(r'fixed_position\s+is_router\s+ls_secs', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_getPref_invalid_field_camel(capsys):
    """Test getPref() with an invalid field"""
    Globals.getInstance().set_camel_case()

    class Field:
        """Simple class for testing."""

        def __init__(self, name):
            """constructor"""
            self.name = name

    prefs = MagicMock()
    prefs.DESCRIPTOR.fields_by_name.get.return_value = None

    # Note: This is a subset of the real fields
    ls_secs_field = Field('ls_secs')
    is_router = Field('is_router')
    fixed_position = Field('fixed_position')

    fields = [ ls_secs_field, is_router, fixed_position ]
    prefs.DESCRIPTOR.fields = fields

    getPref(prefs, 'foo')

    out, err = capsys.readouterr()
    assert re.search(r'does not have an attribute called foo', out, re.MULTILINE)
    # ensure they are sorted
    assert re.search(r'fixedPosition\s+isRouter\s+lsSecs', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_setPref_valid_field_int_as_string(capsys):
    """Test setPref() with a valid field"""

    class Field:
        """Simple class for testing."""

        def __init__(self, name, enum_type):
            """constructor"""
            self.name = name
            self.enum_type = enum_type

    ls_secs_field = Field('ls_secs', 'int')
    prefs = MagicMock()
    prefs.DESCRIPTOR.fields_by_name.get.return_value = ls_secs_field

    setPref(prefs, 'ls_secs', '300')
    out, err = capsys.readouterr()
    assert re.search(r'Set ls_secs to 300', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_setPref_valid_field_invalid_enum(capsys, caplog):
    """Test setPref() with a valid field but invalid enum value"""

    radioConfig = RadioConfig()
    prefs = radioConfig.preferences

    with caplog.at_level(logging.DEBUG):
        setPref(prefs, 'charge_current', 'foo')
        out, err = capsys.readouterr()
        assert re.search(r'charge_current does not have an enum called foo', out, re.MULTILINE)
        assert re.search(r'Choices in sorted order are', out, re.MULTILINE)
        assert re.search(r'MA100', out, re.MULTILINE)
        assert re.search(r'MA280', out, re.MULTILINE)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_setPref_valid_field_invalid_enum_where_enums_are_camel_cased_values(capsys, caplog):
    """Test setPref() with a valid field but invalid enum value"""

    radioConfig = RadioConfig()
    prefs = radioConfig.preferences

    with caplog.at_level(logging.DEBUG):
        setPref(prefs, 'location_share', 'foo')
        out, err = capsys.readouterr()
        assert re.search(r'location_share does not have an enum called foo', out, re.MULTILINE)
        assert re.search(r'Choices in sorted order are', out, re.MULTILINE)
        assert re.search(r'LocDisabled', out, re.MULTILINE)
        assert re.search(r'LocEnabled', out, re.MULTILINE)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_setPref_valid_field_invalid_enum_camel(capsys, caplog):
    """Test setPref() with a valid field but invalid enum value"""
    Globals.getInstance().set_camel_case()

    radioConfig = RadioConfig()
    prefs = radioConfig.preferences

    with caplog.at_level(logging.DEBUG):
        setPref(prefs, 'charge_current', 'foo')
        out, err = capsys.readouterr()
        assert re.search(r'chargeCurrent does not have an enum called foo', out, re.MULTILINE)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_setPref_valid_field_valid_enum(capsys, caplog):
    """Test setPref() with a valid field and valid enum value"""

    # charge_current
    # some valid values:   MA100 MA1000 MA1080

    radioConfig = RadioConfig()
    prefs = radioConfig.preferences

    with caplog.at_level(logging.DEBUG):
        setPref(prefs, 'charge_current', 'MA100')
        out, err = capsys.readouterr()
        assert re.search(r'Set charge_current to MA100', out, re.MULTILINE)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_setPref_valid_field_valid_enum_camel(capsys, caplog):
    """Test setPref() with a valid field and valid enum value"""
    Globals.getInstance().set_camel_case()

    # charge_current
    # some valid values:   MA100 MA1000 MA1080

    radioConfig = RadioConfig()
    prefs = radioConfig.preferences

    with caplog.at_level(logging.DEBUG):
        setPref(prefs, 'charge_current', 'MA100')
        out, err = capsys.readouterr()
        assert re.search(r'Set chargeCurrent to MA100', out, re.MULTILINE)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_setPref_invalid_field(capsys):
    """Test setPref() with a invalid field"""


    class Field:
        """Simple class for testing."""

        def __init__(self, name):
            """constructor"""
            self.name = name

    prefs = MagicMock()
    prefs.DESCRIPTOR.fields_by_name.get.return_value = None

    # Note: This is a subset of the real fields
    ls_secs_field = Field('ls_secs')
    is_router = Field('is_router')
    fixed_position = Field('fixed_position')

    fields = [ ls_secs_field, is_router, fixed_position ]
    prefs.DESCRIPTOR.fields = fields

    setPref(prefs, 'foo', '300')
    out, err = capsys.readouterr()
    assert re.search(r'does not have an attribute called foo', out, re.MULTILINE)
    # ensure they are sorted
    assert re.search(r'fixed_position\s+is_router\s+ls_secs', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_setPref_invalid_field_camel(capsys):
    """Test setPref() with a invalid field"""
    Globals.getInstance().set_camel_case()

    class Field:
        """Simple class for testing."""

        def __init__(self, name):
            """constructor"""
            self.name = name

    prefs = MagicMock()
    prefs.DESCRIPTOR.fields_by_name.get.return_value = None

    # Note: This is a subset of the real fields
    ls_secs_field = Field('ls_secs')
    is_router = Field('is_router')
    fixed_position = Field('fixed_position')

    fields = [ ls_secs_field, is_router, fixed_position ]
    prefs.DESCRIPTOR.fields = fields

    setPref(prefs, 'foo', '300')
    out, err = capsys.readouterr()
    assert re.search(r'does not have an attribute called foo', out, re.MULTILINE)
    # ensure they are sorted
    assert re.search(r'fixedPosition\s+isRouter\s+lsSecs', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_set_psk_no_ch_index(capsys):
    """Test --ch-set psk """
    sys.argv = ['', '--ch-set', 'psk', 'foo', '--host', 'meshtastic.local']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=TCPInterface)
    with patch('meshtastic.tcp_interface.TCPInterface', return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert re.search(r"Warning: Need to specify '--ch-index'", out, re.MULTILINE)
        assert err == ''
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_set_psk_with_ch_index(capsys):
    """Test --ch-set psk """
    sys.argv = ['', '--ch-set', 'psk', 'foo', '--host', 'meshtastic.local', '--ch-index', '0']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=TCPInterface)
    with patch('meshtastic.tcp_interface.TCPInterface', return_value=iface) as mo:
        main()
    out, err = capsys.readouterr()
    assert re.search(r'Connected to radio', out, re.MULTILINE)
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert err == ''
    mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_main_ch_set_name_with_ch_index(capsys):
    """Test --ch-set setting other than psk"""
    sys.argv = ['', '--ch-set', 'name', 'foo', '--host', 'meshtastic.local', '--ch-index', '0']
    Globals.getInstance().set_args(sys.argv)

    iface = MagicMock(autospec=TCPInterface)
    with patch('meshtastic.tcp_interface.TCPInterface', return_value=iface) as mo:
        main()
    out, err = capsys.readouterr()
    assert re.search(r'Connected to radio', out, re.MULTILINE)
    assert re.search(r'Set name to foo', out, re.MULTILINE)
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert err == ''
    mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_onNode(capsys):
    """Test onNode"""
    onNode('foo')
    out, err = capsys.readouterr()
    assert re.search(r'Node changed', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
def test_tunnel_no_args(capsys):
    """Test tunnel no arguments"""
    sys.argv = ['']
    Globals.getInstance().set_args(sys.argv)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        tunnelMain()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    _, err = capsys.readouterr()
    assert re.search(r'usage: ', err, re.MULTILINE)


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
@patch('meshtastic.util.findPorts', return_value=[])
@patch('platform.system')
def test_tunnel_tunnel_arg_with_no_devices(mock_platform_system, caplog, capsys):
    """Test tunnel with tunnel arg (act like we are on a linux system)"""
    a_mock = MagicMock()
    a_mock.return_value = 'Linux'
    mock_platform_system.side_effect = a_mock
    sys.argv = ['', '--tunnel']
    Globals.getInstance().set_args(sys.argv)
    print(f'platform.system():{platform.system()}')
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            tunnelMain()
        mock_platform_system.assert_called()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Warning: No Meshtastic devices detected', out, re.MULTILINE)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
@patch('meshtastic.util.findPorts', return_value=[])
@patch('platform.system')
def test_tunnel_subnet_arg_with_no_devices(mock_platform_system, caplog, capsys):
    """Test tunnel with subnet arg (act like we are on a linux system)"""
    a_mock = MagicMock()
    a_mock.return_value = 'Linux'
    mock_platform_system.side_effect = a_mock
    sys.argv = ['', '--subnet', 'foo']
    Globals.getInstance().set_args(sys.argv)
    print(f'platform.system():{platform.system()}')
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            tunnelMain()
        mock_platform_system.assert_called()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r'Warning: No Meshtastic devices detected', out, re.MULTILINE)
        assert err == ''


@pytest.mark.unit
@pytest.mark.usefixtures("reset_globals")
@patch('platform.system')
def test_tunnel_tunnel_arg(mock_platform_system, caplog, iface_with_nodes, capsys):
    """Test tunnel with tunnel arg (act like we are on a linux system)"""
    # Override the time.sleep so there is no loop
    def my_sleep(amount):
        print(f'{amount}')
        sys.exit(3)

    a_mock = MagicMock()
    a_mock.return_value = 'Linux'
    mock_platform_system.side_effect = a_mock
    sys.argv = ['', '--tunnel']
    Globals.getInstance().set_args(sys.argv)

    iface = iface_with_nodes
    iface.myInfo.my_node_num = 2475227164

    with caplog.at_level(logging.DEBUG):
        with patch('meshtastic.serial_interface.SerialInterface', return_value=iface):
            with patch('time.sleep', side_effect=my_sleep):
                with pytest.raises(SystemExit) as pytest_wrapped_e:
                    tunnelMain()
                    mock_platform_system.assert_called()
                assert pytest_wrapped_e.type == SystemExit
                assert pytest_wrapped_e.value.code == 3
                assert re.search(r'Not starting Tunnel', caplog.text, re.MULTILINE)
        out, err = capsys.readouterr()
        assert re.search(r'Connected to radio', out, re.MULTILINE)
        assert err == ''
