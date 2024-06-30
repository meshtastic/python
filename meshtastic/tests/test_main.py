"""Meshtastic unit tests for __main__.py"""
# pylint: disable=C0302,W0613

import logging
import os
import platform
import re
import sys
from unittest.mock import mock_open, MagicMock, patch

import pytest

from meshtastic.__main__ import (
    export_config,
    initParser,
    main,
    onConnection,
    onNode,
    onReceive,
    tunnelMain,
)
from meshtastic import mt_config

from ..protobuf.channel_pb2 import Channel # pylint: disable=E0611

# from ..ble_interface import BLEInterface
from ..node import Node

# from ..radioconfig_pb2 import UserPreferences
# import meshtastic.config_pb2
from ..serial_interface import SerialInterface
from ..tcp_interface import TCPInterface

# from ..remote_hardware import onGPIOreceive
# from ..config_pb2 import Config


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_init_parser_no_args(capsys):
    """Test no arguments"""
    sys.argv = [""]
    mt_config.args = sys.argv
    initParser()
    out, err = capsys.readouterr()
    assert out == ""
    assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_init_parser_version(capsys):
    """Test --version"""
    sys.argv = ["", "--version"]
    mt_config.args = sys.argv

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        initParser()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    out, err = capsys.readouterr()
    assert re.match(r"[0-9]+\.[0-9]+[\.a][0-9]", out)
    assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_main_version(capsys):
    """Test --version"""
    sys.argv = ["", "--version"]
    mt_config.args = sys.argv

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    out, err = capsys.readouterr()
    assert re.match(r"[0-9]+\.[0-9]+[\.a][0-9]", out)
    assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_main_no_args(capsys):
    """Test with no args"""
    sys.argv = [""]
    mt_config.args = sys.argv

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    _, err = capsys.readouterr()
    assert re.search(r"usage:", err, re.MULTILINE)


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_support(capsys):
    """Test --support"""
    sys.argv = ["", "--support"]
    mt_config.args = sys.argv

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    out, err = capsys.readouterr()
    assert re.search(r"System", out, re.MULTILINE)
    assert re.search(r"Platform", out, re.MULTILINE)
    assert re.search(r"Machine", out, re.MULTILINE)
    assert re.search(r"Executable", out, re.MULTILINE)
    assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("meshtastic.util.findPorts", return_value=[])
def test_main_ch_index_no_devices(patched_find_ports, capsys):
    """Test --ch-index 1"""
    sys.argv = ["", "--ch-index", "1"]
    mt_config.args = sys.argv

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert mt_config.channel_index == 1
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.search(r"No.*Meshtastic.*device.*detected", out, re.MULTILINE)
    assert err == ""
    patched_find_ports.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("meshtastic.util.findPorts", return_value=[])
def test_main_test_no_ports(patched_find_ports, capsys):
    """Test --test with no hardware"""
    sys.argv = ["", "--test"]
    mt_config.args = sys.argv

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    patched_find_ports.assert_called()
    out, err = capsys.readouterr()
    assert re.search(
        r"Warning: Must have at least two devices connected to USB", out, re.MULTILINE
    )
    assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("meshtastic.util.findPorts", return_value=["/dev/ttyFake1"])
def test_main_test_one_port(patched_find_ports, capsys):
    """Test --test with one fake port"""
    sys.argv = ["", "--test"]
    mt_config.args = sys.argv

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    patched_find_ports.assert_called()
    out, err = capsys.readouterr()
    assert re.search(
        r"Warning: Must have at least two devices connected to USB", out, re.MULTILINE
    )
    assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("meshtastic.test.testAll", return_value=True)
def test_main_test_two_ports_success(patched_test_all, capsys):
    """Test --test two fake ports and testAll() is a simulated success"""
    sys.argv = ["", "--test"]
    mt_config.args = sys.argv

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0
    patched_test_all.assert_called()
    out, err = capsys.readouterr()
    assert re.search(r"Test was a success.", out, re.MULTILINE)
    assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("meshtastic.test.testAll", return_value=False)
def test_main_test_two_ports_fails(patched_test_all, capsys):
    """Test --test two fake ports and testAll() is a simulated failure"""
    sys.argv = ["", "--test"]
    mt_config.args = sys.argv

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        main()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    patched_test_all.assert_called()
    out, err = capsys.readouterr()
    assert re.search(r"Test was not successful.", out, re.MULTILINE)
    assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_info(capsys, caplog):
    """Test --info"""
    sys.argv = ["", "--info"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)

    def mock_showInfo():
        print("inside mocked showInfo")

    iface.showInfo.side_effect = mock_showInfo
    with caplog.at_level(logging.DEBUG):
        with patch(
            "meshtastic.serial_interface.SerialInterface", return_value=iface
        ) as mo:
            main()
            out, err = capsys.readouterr()
            assert re.search(r"Connected to radio", out, re.MULTILINE)
            assert re.search(r"inside mocked showInfo", out, re.MULTILINE)
            assert err == ""
            mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("os.getlogin")
def test_main_info_with_permission_error(patched_getlogin, capsys, caplog):
    """Test --info"""
    sys.argv = ["", "--info"]
    mt_config.args = sys.argv

    patched_getlogin.return_value = "me"

    iface = MagicMock(autospec=SerialInterface)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            with patch(
                "meshtastic.serial_interface.SerialInterface", return_value=iface
            ) as mo:
                mo.side_effect = PermissionError("bla bla")
                main()
            assert pytest_wrapped_e.type == SystemExit
            assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        patched_getlogin.assert_called()
        assert re.search(r"Need to add yourself", out, re.MULTILINE)
        assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_info_with_tcp_interface(capsys):
    """Test --info"""
    sys.argv = ["", "--info", "--host", "meshtastic.local"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=TCPInterface)

    def mock_showInfo():
        print("inside mocked showInfo")

    iface.showInfo.side_effect = mock_showInfo
    with patch("meshtastic.tcp_interface.TCPInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"inside mocked showInfo", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_no_proto(capsys):
    """Test --noproto (using --info for output)"""
    sys.argv = ["", "--info", "--noproto"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)

    def mock_showInfo():
        print("inside mocked showInfo")

    iface.showInfo.side_effect = mock_showInfo

    # Override the time.sleep so there is no loop
    def my_sleep(amount):
        print(f"amount:{amount}")
        sys.exit(0)

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface):
        with patch("time.sleep", side_effect=my_sleep):
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                main()
            assert pytest_wrapped_e.type == SystemExit
            assert pytest_wrapped_e.value.code == 0
            out, err = capsys.readouterr()
            assert re.search(r"Connected to radio", out, re.MULTILINE)
            assert re.search(r"inside mocked showInfo", out, re.MULTILINE)
            assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_info_with_seriallog_stdout(capsys):
    """Test --info"""
    sys.argv = ["", "--info", "--seriallog", "stdout"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)

    def mock_showInfo():
        print("inside mocked showInfo")

    iface.showInfo.side_effect = mock_showInfo
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"inside mocked showInfo", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_info_with_seriallog_output_txt(capsys):
    """Test --info"""
    sys.argv = ["", "--info", "--seriallog", "output.txt"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)

    def mock_showInfo():
        print("inside mocked showInfo")

    iface.showInfo.side_effect = mock_showInfo
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"inside mocked showInfo", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()
    # do some cleanup
    os.remove("output.txt")


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_qr(capsys):
    """Test --qr"""
    sys.argv = ["", "--qr"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)
    # TODO: could mock/check url
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Primary channel URL", out, re.MULTILINE)
        # if a qr code is generated it will have lots of these
        assert re.search(r"\[7m", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_onConnected_exception(capsys):
    """Test the exception in onConnected"""
    sys.argv = ["", "--qr"]
    mt_config.args = sys.argv

    def throw_an_exception(junk):
        raise Exception("Fake exception.") # pylint: disable=W0719

    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface):
        with patch("pyqrcode.create", side_effect=throw_an_exception):
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                main()
                out, err = capsys.readouterr()
                assert re.search("Aborting due to: Fake exception", out, re.MULTILINE)
                assert err == ""
                assert pytest_wrapped_e.type == Exception


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_nodes(capsys):
    """Test --nodes"""
    sys.argv = ["", "--nodes"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)

    def mock_showNodes():
        print("inside mocked showNodes")

    iface.showNodes.side_effect = mock_showNodes
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"inside mocked showNodes", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_set_owner_to_bob(capsys):
    """Test --set-owner bob"""
    sys.argv = ["", "--set-owner", "bob"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Setting device owner to bob", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_set_owner_short_to_bob(capsys):
    """Test --set-owner-short bob"""
    sys.argv = ["", "--set-owner-short", "bob"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Setting device owner short to bob", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_set_canned_messages(capsys):
    """Test --set-canned-message"""
    sys.argv = ["", "--set-canned-message", "foo"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Setting canned plugin message to foo", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_get_canned_messages(capsys, caplog, iface_with_nodes):
    """Test --get-canned-message"""
    sys.argv = ["", "--get-canned-message"]
    mt_config.args = sys.argv

    iface = iface_with_nodes
    iface.localNode.cannedPluginMessage = "foo"
    iface.devPath = "bar"

    with caplog.at_level(logging.DEBUG):
        with patch(
            "meshtastic.serial_interface.SerialInterface", return_value=iface
        ) as mo:
            main()
            out, err = capsys.readouterr()
            assert re.search(r"Connected to radio", out, re.MULTILINE)
            assert re.search(r"canned_plugin_message:foo", out, re.MULTILINE)
            assert err == ""
            mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_set_ham_to_KI123(capsys):
    """Test --set-ham KI123"""
    sys.argv = ["", "--set-ham", "KI123"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    def mock_turnOffEncryptionOnPrimaryChannel():
        print("inside mocked turnOffEncryptionOnPrimaryChannel")

    def mock_setOwner(name, is_licensed):
        print(f"inside mocked setOwner name:{name} is_licensed:{is_licensed}")

    mocked_node.turnOffEncryptionOnPrimaryChannel.side_effect = (
        mock_turnOffEncryptionOnPrimaryChannel
    )
    mocked_node.setOwner.side_effect = mock_setOwner

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Setting Ham ID to KI123", out, re.MULTILINE)
        assert re.search(r"inside mocked setOwner", out, re.MULTILINE)
        assert re.search(
            r"inside mocked turnOffEncryptionOnPrimaryChannel", out, re.MULTILINE
        )
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_reboot(capsys):
    """Test --reboot"""
    sys.argv = ["", "--reboot"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    def mock_reboot():
        print("inside mocked reboot")

    mocked_node.reboot.side_effect = mock_reboot

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"inside mocked reboot", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_shutdown(capsys):
    """Test --shutdown"""
    sys.argv = ["", "--shutdown"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    def mock_shutdown():
        print("inside mocked shutdown")

    mocked_node.shutdown.side_effect = mock_shutdown

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"inside mocked shutdown", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_sendtext(capsys):
    """Test --sendtext"""
    sys.argv = ["", "--sendtext", "hello"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)

    def mock_sendText(
        text, dest, wantAck=False, wantResponse=False, onResponse=None, channelIndex=0
    ):
        print("inside mocked sendText")
        print(f"{text} {dest} {wantAck} {wantResponse} {channelIndex}")

    iface.sendText.side_effect = mock_sendText

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Sending text message", out, re.MULTILINE)
        assert re.search(r"inside mocked sendText", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_sendtext_with_channel(capsys):
    """Test --sendtext"""
    sys.argv = ["", "--sendtext", "hello", "--ch-index", "1"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)

    def mock_sendText(
        text, dest, wantAck=False, wantResponse=False, onResponse=None, channelIndex=0
    ):
        print("inside mocked sendText")
        print(f"{text} {dest} {wantAck} {wantResponse} {channelIndex}")

    iface.sendText.side_effect = mock_sendText

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Sending text message", out, re.MULTILINE)
        assert re.search(r"on channelIndex:1", out, re.MULTILINE)
        assert re.search(r"inside mocked sendText", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_sendtext_with_invalid_channel(caplog, capsys):
    """Test --sendtext"""
    sys.argv = ["", "--sendtext", "hello", "--ch-index", "-1"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode.getChannelByChannelIndex.return_value = None

    with caplog.at_level(logging.DEBUG):
        with patch(
            "meshtastic.serial_interface.SerialInterface", return_value=iface
        ) as mo:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                main()
            assert pytest_wrapped_e.type == SystemExit
            assert pytest_wrapped_e.value.code == 1
            out, err = capsys.readouterr()
            assert re.search(r"is not a valid channel", out, re.MULTILINE)
            assert err == ""
            mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_sendtext_with_invalid_channel_nine(caplog, capsys):
    """Test --sendtext"""
    sys.argv = ["", "--sendtext", "hello", "--ch-index", "9"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode.getChannelByChannelIndex.return_value = None

    with caplog.at_level(logging.DEBUG):
        with patch(
            "meshtastic.serial_interface.SerialInterface", return_value=iface
        ) as mo:
            with pytest.raises(SystemExit) as pytest_wrapped_e:
                main()
            assert pytest_wrapped_e.type == SystemExit
            assert pytest_wrapped_e.value.code == 1
            out, err = capsys.readouterr()
            assert re.search(r"is not a valid channel", out, re.MULTILINE)
            assert err == ""
            mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("termios.tcsetattr")
@patch("termios.tcgetattr")
@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("serial.Serial")
@patch("meshtastic.util.findPorts", return_value=["/dev/ttyUSBfake"])
def test_main_sendtext_with_dest(mock_findPorts, mock_serial, mocked_open, mock_get, mock_set, capsys, caplog, iface_with_nodes):
    """Test --sendtext with --dest"""
    sys.argv = ["", "--sendtext", "hello", "--dest", "foo"]
    mt_config.args = sys.argv

    #iface = iface_with_nodes
    #iface.myInfo.my_node_num = 2475227164
    serialInterface = SerialInterface(noProto=True)

    mocked_channel = MagicMock(autospec=Channel)
    serialInterface.localNode.getChannelByChannelIndex = mocked_channel

    with patch("meshtastic.serial_interface.SerialInterface", return_value=serialInterface):
        with caplog.at_level(logging.DEBUG):
            #with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
            #assert pytest_wrapped_e.type == SystemExit
            #assert pytest_wrapped_e.value.code == 1
            out, err = capsys.readouterr()
            assert re.search(r"Connected to radio", out, re.MULTILINE)
            assert not re.search(
                r"Warning: 0 is not a valid channel", out, re.MULTILINE
            )
            assert not re.search(
                r"There is a SECONDARY channel named 'admin'", out, re.MULTILINE
            )
            print(out)
            assert re.search(r"Not sending packet because", caplog.text, re.MULTILINE)
            assert re.search(r"Warning: There were no self.nodes.", caplog.text, re.MULTILINE)
            assert err == ""

@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_removeposition_invalid(capsys):
    """Test --remove-position with an invalid dest"""
    sys.argv = ["", "--remove-position", "--dest", "!12345678"]
    mt_config.args = sys.argv
    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"remote nodes is not supported", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()

@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_setlat_invalid(capsys):
    """Test --setlat with an invalid dest"""
    sys.argv = ["", "--setlat", "37.5", "--dest", "!12345678"]
    mt_config.args = sys.argv
    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"remote nodes is not supported", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()

@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_removeposition(capsys):
    """Test --remove-position"""
    sys.argv = ["", "--remove-position"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    def mock_removeFixedPosition():
        print("inside mocked removeFixedPosition")

    mocked_node.removeFixedPosition.side_effect = mock_removeFixedPosition

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Removing fixed position", out, re.MULTILINE)
        assert re.search(r"inside mocked removeFixedPosition", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()

@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_setlat(capsys):
    """Test --setlat"""
    sys.argv = ["", "--setlat", "37.5"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    def mock_setFixedPosition(lat, lon, alt):
        print("inside mocked setFixedPosition")
        print(f"{lat} {lon} {alt}")

    mocked_node.setFixedPosition.side_effect = mock_setFixedPosition

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Fixing latitude", out, re.MULTILINE)
        assert re.search(r"Setting device position", out, re.MULTILINE)
        assert re.search(r"inside mocked setFixedPosition", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_setlon(capsys):
    """Test --setlon"""
    sys.argv = ["", "--setlon", "-122.1"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    def mock_setFixedPosition(lat, lon, alt):
        print("inside mocked setFixedPosition")
        print(f"{lat} {lon} {alt}")

    mocked_node.setFixedPosition.side_effect = mock_setFixedPosition

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Fixing longitude", out, re.MULTILINE)
        assert re.search(r"Setting device position", out, re.MULTILINE)
        assert re.search(r"inside mocked setFixedPosition", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_setalt(capsys):
    """Test --setalt"""
    sys.argv = ["", "--setalt", "51"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    def mock_setFixedPosition(lat, lon, alt):
        print("inside mocked setFixedPosition")
        print(f"{lat} {lon} {alt}")

    mocked_node.setFixedPosition.side_effect = mock_setFixedPosition

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Fixing altitude", out, re.MULTILINE)
        assert re.search(r"Setting device position", out, re.MULTILINE)
        assert re.search(r"inside mocked setFixedPosition", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_seturl(capsys):
    """Test --seturl (url used below is what is generated after a factory_reset)"""
    sys.argv = ["", "--seturl", "https://www.meshtastic.org/d/#CgUYAyIBAQ"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("termios.tcsetattr")
@patch("termios.tcgetattr")
@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("serial.Serial")
@patch("meshtastic.util.findPorts", return_value=["/dev/ttyUSBfake"])
def test_main_set_valid(mocked_findports, mocked_serial, mocked_open, mocked_get, mocked_set, capsys):
    """Test --set with valid field"""
    sys.argv = ["", "--set", "network.wifi_ssid", "foo"]
    mt_config.args = sys.argv

    serialInterface = SerialInterface(noProto=True)
    anode = Node(serialInterface, 1234567890, noProto=True)
    serialInterface.localNode = anode

    with patch("meshtastic.serial_interface.SerialInterface", return_value=serialInterface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Set network.wifi_ssid to foo", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("termios.tcsetattr")
@patch("termios.tcgetattr")
@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("serial.Serial")
@patch("meshtastic.util.findPorts", return_value=["/dev/ttyUSBfake"])
def test_main_set_valid_wifi_psk(mocked_findports, mocked_serial, mocked_open, mocked_get, mocked_set, capsys):
    """Test --set with valid field"""
    sys.argv = ["", "--set", "network.wifi_psk", "123456789"]
    mt_config.args = sys.argv

    serialInterface = SerialInterface(noProto=True)
    anode = Node(serialInterface, 1234567890, noProto=True)
    serialInterface.localNode = anode

    with patch("meshtastic.serial_interface.SerialInterface", return_value=serialInterface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Set network.wifi_psk to 123456789", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("termios.tcsetattr")
@patch("termios.tcgetattr")
@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("serial.Serial")
@patch("meshtastic.util.findPorts", return_value=["/dev/ttyUSBfake"])
def test_main_set_invalid_wifi_psk(mocked_findports, mocked_serial, mocked_open, mocked_get, mocked_set, capsys):
    """Test --set with an invalid value (psk must be 8 or more characters)"""
    sys.argv = ["", "--set", "network.wifi_psk", "1234567"]
    mt_config.args = sys.argv

    serialInterface = SerialInterface(noProto=True)
    anode = Node(serialInterface, 1234567890, noProto=True)
    serialInterface.localNode = anode

    with patch("meshtastic.serial_interface.SerialInterface", return_value=serialInterface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert not re.search(r"Set network.wifi_psk to 1234567", out, re.MULTILINE)
        assert re.search(
            r"Warning: network.wifi_psk must be 8 or more characters.", out, re.MULTILINE
        )
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("termios.tcsetattr")
@patch("termios.tcgetattr")
@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("serial.Serial")
@patch("meshtastic.util.findPorts", return_value=["/dev/ttyUSBfake"])
def test_main_set_valid_camel_case(mocked_findports, mocked_serial, mocked_open, mocked_get, mocked_set, capsys):
    """Test --set with valid field"""
    sys.argv = ["", "--set", "network.wifi_ssid", "foo"]
    mt_config.args = sys.argv
    mt_config.camel_case = True

    serialInterface = SerialInterface(noProto=True)
    anode = Node(serialInterface, 1234567890, noProto=True)
    serialInterface.localNode = anode

    with patch("meshtastic.serial_interface.SerialInterface", return_value=serialInterface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Set network.wifiSsid to foo", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("termios.tcsetattr")
@patch("termios.tcgetattr")
@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("serial.Serial")
@patch("meshtastic.util.findPorts", return_value=["/dev/ttyUSBfake"])
def test_main_set_with_invalid(mocked_findports, mocked_serial, mocked_open, mocked_get, mocked_set, capsys):
    """Test --set with invalid field"""
    sys.argv = ["", "--set", "foo", "foo"]
    mt_config.args = sys.argv

    serialInterface = SerialInterface(noProto=True)
    anode = Node(serialInterface, 1234567890, noProto=True)
    serialInterface.localNode = anode

    with patch("meshtastic.serial_interface.SerialInterface", return_value=serialInterface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"do not have attribute foo", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


# TODO: write some negative --configure tests
@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("termios.tcsetattr")
@patch("termios.tcgetattr")
@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("serial.Serial")
@patch("meshtastic.util.findPorts", return_value=["/dev/ttyUSBfake"])
def test_main_configure_with_snake_case(mocked_findports, mocked_serial, mocked_open, mocked_get, mocked_set, capsys):
    """Test --configure with valid file"""
    sys.argv = ["", "--configure", "example_config.yaml"]
    mt_config.args = sys.argv

    serialInterface = SerialInterface(noProto=True)
    anode = Node(serialInterface, 1234567890, noProto=True)
    serialInterface.localNode = anode

    with patch("meshtastic.serial_interface.SerialInterface", return_value=serialInterface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        # should these come back? maybe a flag?
        #assert re.search(r"Setting device owner", out, re.MULTILINE)
        #assert re.search(r"Setting device owner short", out, re.MULTILINE)
        #assert re.search(r"Setting channel url", out, re.MULTILINE)
        #assert re.search(r"Fixing altitude", out, re.MULTILINE)
        #assert re.search(r"Fixing latitude", out, re.MULTILINE)
        #assert re.search(r"Fixing longitude", out, re.MULTILINE)
        #assert re.search(r"Set location_share to LocEnabled", out, re.MULTILINE)
        assert re.search(r"Writing modified configuration to device", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("termios.tcsetattr")
@patch("termios.tcgetattr")
@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("serial.Serial")
@patch("meshtastic.util.findPorts", return_value=["/dev/ttyUSBfake"])
def test_main_configure_with_camel_case_keys(mocked_findports, mocked_serial, mocked_open, mocked_get, mocked_set, capsys):
    """Test --configure with valid file"""
    sys.argv = ["", "--configure", "exampleConfig.yaml"]
    mt_config.args = sys.argv

    serialInterface = SerialInterface(noProto=True)
    anode = Node(serialInterface, 1234567890, noProto=True)
    serialInterface.localNode = anode

    with patch("meshtastic.serial_interface.SerialInterface", return_value=serialInterface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        # should these come back? maybe a flag?
        #assert re.search(r"Setting device owner", out, re.MULTILINE)
        #assert re.search(r"Setting device owner short", out, re.MULTILINE)
        #assert re.search(r"Setting channel url", out, re.MULTILINE)
        #assert re.search(r"Fixing altitude", out, re.MULTILINE)
        #assert re.search(r"Fixing latitude", out, re.MULTILINE)
        #assert re.search(r"Fixing longitude", out, re.MULTILINE)
        assert re.search(r"Writing modified configuration to device", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_add_valid(capsys):
    """Test --ch-add with valid channel name, and that channel name does not already exist"""
    sys.argv = ["", "--ch-add", "testing"]
    mt_config.args = sys.argv

    mocked_channel = MagicMock(autospec=Channel)
    # TODO: figure out how to get it to print the channel name instead of MagicMock

    mocked_node = MagicMock(autospec=Node)
    # set it up so we do not already have a channel named this
    mocked_node.getChannelByName.return_value = False
    # set it up so we have free channels
    mocked_node.getDisabledChannel.return_value = mocked_channel

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_add_invalid_name_too_long(capsys):
    """Test --ch-add with invalid channel name, name too long"""
    sys.argv = ["", "--ch-add", "testingtestingtesting"]
    mt_config.args = sys.argv

    mocked_channel = MagicMock(autospec=Channel)
    # TODO: figure out how to get it to print the channel name instead of MagicMock

    mocked_node = MagicMock(autospec=Node)
    # set it up so we do not already have a channel named this
    mocked_node.getChannelByName.return_value = False
    # set it up so we have free channels
    mocked_node.getDisabledChannel.return_value = mocked_channel

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Warning: Channel name must be shorter", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_add_but_name_already_exists(capsys):
    """Test --ch-add with a channel name that already exists"""
    sys.argv = ["", "--ch-add", "testing"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)
    # set it up so we do not already have a channel named this
    mocked_node.getChannelByName.return_value = True

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Warning: This node already has", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_add_but_no_more_channels(capsys):
    """Test --ch-add with but there are no more channels"""
    sys.argv = ["", "--ch-add", "testing"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)
    # set it up so we do not already have a channel named this
    mocked_node.getChannelByName.return_value = False
    # set it up so we have free channels
    mocked_node.getDisabledChannel.return_value = None

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Warning: No free channels were found", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_del(capsys):
    """Test --ch-del with valid secondary channel to be deleted"""
    sys.argv = ["", "--ch-del", "--ch-index", "1"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Deleting channel", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_del_no_ch_index_specified(capsys):
    """Test --ch-del without a valid ch-index"""
    sys.argv = ["", "--ch-del"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Warning: Need to specify", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_del_primary_channel(capsys):
    """Test --ch-del on ch-index=0"""
    sys.argv = ["", "--ch-del", "--ch-index", "0"]
    mt_config.args = sys.argv
    mt_config.channel_index = 1

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Warning: Cannot delete primary channel", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_enable_valid_secondary_channel(capsys):
    """Test --ch-enable with --ch-index"""
    sys.argv = ["", "--ch-enable", "--ch-index", "1"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Writing modified channels", out, re.MULTILINE)
        assert err == ""
        assert mt_config.channel_index == 1
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_disable_valid_secondary_channel(capsys):
    """Test --ch-disable with --ch-index"""
    sys.argv = ["", "--ch-disable", "--ch-index", "1"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Writing modified channels", out, re.MULTILINE)
        assert err == ""
        assert mt_config.channel_index == 1
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_enable_without_a_ch_index(capsys):
    """Test --ch-enable without --ch-index"""
    sys.argv = ["", "--ch-enable"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Warning: Need to specify", out, re.MULTILINE)
        assert err == ""
        assert mt_config.channel_index is None
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_enable_primary_channel(capsys):
    """Test --ch-enable with --ch-index = 0"""
    sys.argv = ["", "--ch-enable", "--ch-index", "0"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Warning: Cannot enable/disable PRIMARY", out, re.MULTILINE)
        assert err == ""
        assert mt_config.channel_index == 0
        mo.assert_called()


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_ch_range_options(capsys):
#    """Test changing the various range options."""
#    range_options = ['--ch-vlongslow', '--ch-longslow', '--ch-longfast', '--ch-midslow',
#                     '--ch-midfast', '--ch-shortslow', '--ch-shortfast']
#    for range_option in range_options:
#        sys.argv = ['', f"{range_option}" ]
#        mt_config.args = sys.argv
#
#        mocked_node = MagicMock(autospec=Node)
#
#        iface = MagicMock(autospec=SerialInterface)
#        iface.getNode.return_value = mocked_node
#
#        with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#            main()
#            out, err = capsys.readouterr()
#            assert re.search(r'Connected to radio', out, re.MULTILINE)
#            assert re.search(r'Writing modified channels', out, re.MULTILINE)
#            assert err == ''
#            mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_longfast_on_non_primary_channel(capsys):
    """Test --ch-longfast --ch-index 1"""
    sys.argv = ["", "--ch-longfast", "--ch-index", "1"]
    mt_config.args = sys.argv

    mocked_node = MagicMock(autospec=Node)

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Warning: Cannot set modem preset for non-primary channel", out, re.MULTILINE)
        assert err == ""
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

# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_pos_fields_no_args(capsys):
#    """Test --pos-fields no args (which shows settings)"""
#    sys.argv = ['', '--pos-fields']
#    mt_config.args = sys.argv
#
#    pos_flags = MagicMock(autospec=meshtastic.radioconfig_pb2.PositionFlags)
#
#    with patch('meshtastic.serial_interface.SerialInterface') as mo:
#        mo().getNode().radioConfig.preferences.position_flags = 35
#        with patch('meshtastic.radioconfig_pb2.PositionFlags', return_value=pos_flags) as mrc:
#
#            mrc.values.return_value = [0, 1, 2, 4, 8, 16, 32, 64, 128, 256]
#            # Note: When you use side_effect and a list, each call will use a value from the front of the list then
#            # remove that value from the list. If there are three values in the list, we expect it to be called
#            # three times.
#            mrc.Name.side_effect = ['POS_ALTITUDE', 'POS_ALT_MSL', 'POS_BATTERY']
#
#            main()
#
#            mrc.Name.assert_called()
#            mrc.values.assert_called()
#            mo.assert_called()
#
#            out, err = capsys.readouterr()
#            assert re.search(r'Connected to radio', out, re.MULTILINE)
#            assert re.search(r'POS_ALTITUDE POS_ALT_MSL POS_BATTERY', out, re.MULTILINE)
#            assert err == ''


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_pos_fields_arg_of_zero(capsys):
#    """Test --pos-fields an arg of 0 (which shows list)"""
#    sys.argv = ['', '--pos-fields', '0']
#    mt_config.args = sys.argv
#
#    pos_flags = MagicMock(autospec=meshtastic.radioconfig_pb2.PositionFlags)
#
#    with patch('meshtastic.serial_interface.SerialInterface') as mo:
#        with patch('meshtastic.radioconfig_pb2.PositionFlags', return_value=pos_flags) as mrc:
#
#            def throw_value_error_exception(exc):
#                raise ValueError()
#            mrc.Value.side_effect = throw_value_error_exception
#            mrc.keys.return_value = [ 'POS_UNDEFINED', 'POS_ALTITUDE', 'POS_ALT_MSL',
#                                      'POS_GEO_SEP', 'POS_DOP', 'POS_HVDOP', 'POS_BATTERY',
#                                      'POS_SATINVIEW', 'POS_SEQ_NOS', 'POS_TIMESTAMP']
#
#            main()
#
#            mrc.Value.assert_called()
#            mrc.keys.assert_called()
#            mo.assert_called()
#
#            out, err = capsys.readouterr()
#            assert re.search(r'Connected to radio', out, re.MULTILINE)
#            assert re.search(r'ERROR: supported position fields are:', out, re.MULTILINE)
#            assert re.search(r"['POS_UNDEFINED', 'POS_ALTITUDE', 'POS_ALT_MSL', 'POS_GEO_SEP',"\
#                              "'POS_DOP', 'POS_HVDOP', 'POS_BATTERY', 'POS_SATINVIEW', 'POS_SEQ_NOS',"\
#                              "'POS_TIMESTAMP']", out, re.MULTILINE)
#            assert err == ''


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_pos_fields_valid_values(capsys):
#    """Test --pos-fields with valid values"""
#    sys.argv = ['', '--pos-fields', 'POS_GEO_SEP', 'POS_ALT_MSL']
#    mt_config.args = sys.argv
#
#    pos_flags = MagicMock(autospec=meshtastic.radioconfig_pb2.PositionFlags)
#
#    with patch('meshtastic.serial_interface.SerialInterface') as mo:
#        with patch('meshtastic.radioconfig_pb2.PositionFlags', return_value=pos_flags) as mrc:
#
#            mrc.Value.side_effect = [ 4, 2 ]
#
#            main()
#
#            mrc.Value.assert_called()
#            mo.assert_called()
#
#            out, err = capsys.readouterr()
#            assert re.search(r'Connected to radio', out, re.MULTILINE)
#            assert re.search(r'Setting position fields to 6', out, re.MULTILINE)
#            assert re.search(r'Set position_flags to 6', out, re.MULTILINE)
#            assert re.search(r'Writing modified preferences to device', out, re.MULTILINE)
#            assert err == ''


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_get_with_valid_values(capsys):
#    """Test --get with valid values (with string, number, boolean)"""
#    sys.argv = ['', '--get', 'ls_secs', '--get', 'wifi_ssid', '--get', 'fixed_position']
#    mt_config.args = sys.argv
#
#    with patch('meshtastic.serial_interface.SerialInterface') as mo:
#
#        mo().getNode().radioConfig.preferences.wifi_ssid = 'foo'
#        mo().getNode().radioConfig.preferences.ls_secs = 300
#        mo().getNode().radioConfig.preferences.fixed_position = False
#
#        main()
#
#        mo.assert_called()
#
#        out, err = capsys.readouterr()
#        assert re.search(r'Connected to radio', out, re.MULTILINE)
#        assert re.search(r'ls_secs: 300', out, re.MULTILINE)
#        assert re.search(r'wifi_ssid: foo', out, re.MULTILINE)
#        assert re.search(r'fixed_position: False', out, re.MULTILINE)
#        assert err == ''


# TODO
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_get_with_valid_values_camel(capsys, caplog):
#    """Test --get with valid values (with string, number, boolean)"""
#    sys.argv = ["", "--get", "lsSecs", "--get", "wifiSsid", "--get", "fixedPosition"]
#    mt_config.args = sys.argv
#    mt_config.camel_case = True
#
#    with caplog.at_level(logging.DEBUG):
#        with patch("meshtastic.serial_interface.SerialInterface") as mo:
#            mo().getNode().radioConfig.preferences.wifi_ssid = "foo"
#            mo().getNode().radioConfig.preferences.ls_secs = 300
#            mo().getNode().radioConfig.preferences.fixed_position = False
#
#            main()
#
#            mo.assert_called()
#
#            out, err = capsys.readouterr()
#            assert re.search(r"Connected to radio", out, re.MULTILINE)
#            assert re.search(r"lsSecs: 300", out, re.MULTILINE)
#            assert re.search(r"wifiSsid: foo", out, re.MULTILINE)
#            assert re.search(r"fixedPosition: False", out, re.MULTILINE)
#            assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_get_with_invalid(capsys):
    """Test --get with invalid field"""
    sys.argv = ["", "--get", "foo"]
    mt_config.args = sys.argv

    mocked_user_prefs = MagicMock()
    mocked_user_prefs.DESCRIPTOR.fields_by_name.get.return_value = None

    mocked_node = MagicMock(autospec=Node)
    mocked_node.localConfig = mocked_user_prefs
    mocked_node.moduleConfig = mocked_user_prefs

    iface = MagicMock(autospec=SerialInterface)
    iface.getNode.return_value = mocked_node

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"do not have attribute foo", out, re.MULTILINE)
        assert re.search(r"Choices are...", out, re.MULTILINE)
        assert err == ""
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_onReceive_empty(caplog, capsys):
    """Test onReceive"""
    args = MagicMock()
    mt_config.args = args
    iface = MagicMock(autospec=SerialInterface)
    packet = {}
    with caplog.at_level(logging.DEBUG):
        onReceive(packet, iface)
    assert re.search(r"in onReceive", caplog.text, re.MULTILINE)
    out, err = capsys.readouterr()
    assert re.search(
        r"Warning: There is no field 'to' in the packet.", out, re.MULTILINE
    )
    assert err == ""


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
@pytest.mark.usefixtures("reset_mt_config")
def test_main_onReceive_with_sendtext(caplog, capsys):
    """Test onReceive with sendtext
    The entire point of this test is to make sure the interface.close() call
    is made in onReceive().
    """
    sys.argv = ["", "--sendtext", "hello"]
    mt_config.args = sys.argv

    # Note: 'TEXT_MESSAGE_APP' value is 1
    packet = {
        "to": 4294967295,
        "decoded": {"portnum": 1, "payload": "hello"},
        "id": 334776977,
        "hop_limit": 3,
        "want_ack": True,
    }

    iface = MagicMock(autospec=SerialInterface)
    iface.myInfo.my_node_num = 4294967295

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        with caplog.at_level(logging.DEBUG):
            main()
            onReceive(packet, iface)
        assert re.search(r"in onReceive", caplog.text, re.MULTILINE)
        mo.assert_called()
        out, err = capsys.readouterr()
        assert re.search(r"Sending text message hello to", out, re.MULTILINE)
        assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_onReceive_with_text(caplog, capsys):
    """Test onReceive with text"""
    args = MagicMock()
    args.sendtext.return_value = "foo"
    mt_config.args = args

    # Note: 'TEXT_MESSAGE_APP' value is 1
    # Note: Some of this is faked below.
    packet = {
        "to": 4294967295,
        "decoded": {"portnum": 1, "payload": "hello", "text": "faked"},
        "id": 334776977,
        "hop_limit": 3,
        "want_ack": True,
        "rxSnr": 6.0,
        "hopLimit": 3,
        "raw": "faked",
        "fromId": "!28b5465c",
        "toId": "^all",
    }

    iface = MagicMock(autospec=SerialInterface)
    iface.myInfo.my_node_num = 4294967295

    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface):
        with caplog.at_level(logging.DEBUG):
            onReceive(packet, iface)
        assert re.search(r"in onReceive", caplog.text, re.MULTILINE)
        out, err = capsys.readouterr()
        assert re.search(r"Sending reply", out, re.MULTILINE)
        assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_onConnection(capsys):
    """Test onConnection"""
    sys.argv = [""]
    mt_config.args = sys.argv
    iface = MagicMock(autospec=SerialInterface)

    class TempTopic:
        """temp class for topic"""

        def getName(self):
            """return the fake name of a topic"""
            return "foo"

    mytopic = TempTopic()
    onConnection(iface, mytopic)
    out, err = capsys.readouterr()
    assert re.search(r"Connection changed: foo", out, re.MULTILINE)
    assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_export_config(capsys):
    """Test export_config() function directly"""
    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        mo.getLongName.return_value = "foo"
        mo.getShortName.return_value = "oof"
        mo.localNode.getURL.return_value = "bar"
        mo.getMyNodeInfo().get.return_value = {
            "latitudeI": 1100000000,
            "longitudeI": 1200000000,
            "altitude": 100,
            "batteryLevel": 34,
            "latitude": 110.0,
            "longitude": 120.0,
        }
        mo.localNode.radioConfig.preferences = """phone_timeout_secs: 900
ls_secs: 300
position_broadcast_smart: true
fixed_position: true
position_flags: 35"""
        export_config(mo)
    out, err = capsys.readouterr()

    # ensure we do not output this line
    assert not re.search(r"Connected to radio", out, re.MULTILINE)

    assert re.search(r"owner: foo", out, re.MULTILINE)
    assert re.search(r"owner_short: oof", out, re.MULTILINE)
    assert re.search(r"channel_url: bar", out, re.MULTILINE)
    assert re.search(r"location:", out, re.MULTILINE)
    assert re.search(r"lat: 110.0", out, re.MULTILINE)
    assert re.search(r"lon: 120.0", out, re.MULTILINE)
    assert re.search(r"alt: 100", out, re.MULTILINE)
    # TODO: rework above config to test the following
    #assert re.search(r"user_prefs:", out, re.MULTILINE)
    #assert re.search(r"phone_timeout_secs: 900", out, re.MULTILINE)
    #assert re.search(r"ls_secs: 300", out, re.MULTILINE)
    #assert re.search(r"position_broadcast_smart: 'true'", out, re.MULTILINE)
    #assert re.search(r"fixed_position: 'true'", out, re.MULTILINE)
    #assert re.search(r"position_flags: 35", out, re.MULTILINE)
    assert err == ""


# TODO
# recursion depth exceeded error
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_export_config_use_camel(capsys):
#    """Test export_config() function directly"""
#    mt_config.camel_case = True
#    iface = MagicMock(autospec=SerialInterface)
#    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
#        mo.getLongName.return_value = "foo"
#        mo.localNode.getURL.return_value = "bar"
#        mo.getMyNodeInfo().get.return_value = {
#            "latitudeI": 1100000000,
#            "longitudeI": 1200000000,
#            "altitude": 100,
#            "batteryLevel": 34,
#            "latitude": 110.0,
#            "longitude": 120.0,
#        }
#        mo.localNode.radioConfig.preferences = """phone_timeout_secs: 900
#ls_secs: 300
#position_broadcast_smart: true
#fixed_position: true
#position_flags: 35"""
#        export_config(mo)
#    out, err = capsys.readouterr()
#
#    # ensure we do not output this line
#    assert not re.search(r"Connected to radio", out, re.MULTILINE)
#
#    assert re.search(r"owner: foo", out, re.MULTILINE)
#    assert re.search(r"channelUrl: bar", out, re.MULTILINE)
#    assert re.search(r"location:", out, re.MULTILINE)
#    assert re.search(r"lat: 110.0", out, re.MULTILINE)
#    assert re.search(r"lon: 120.0", out, re.MULTILINE)
#    assert re.search(r"alt: 100", out, re.MULTILINE)
#    assert re.search(r"userPrefs:", out, re.MULTILINE)
#    assert re.search(r"phoneTimeoutSecs: 900", out, re.MULTILINE)
#    assert re.search(r"lsSecs: 300", out, re.MULTILINE)
#    # TODO: should True be capitalized here?
#    assert re.search(r"positionBroadcastSmart: 'True'", out, re.MULTILINE)
#    assert re.search(r"fixedPosition: 'True'", out, re.MULTILINE)
#    assert re.search(r"positionFlags: 35", out, re.MULTILINE)
#    assert err == ""


# TODO
# maximum recursion depth error
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_export_config_called_from_main(capsys):
#    """Test --export-config"""
#    sys.argv = ["", "--export-config"]
#    mt_config.args = sys.argv
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
#        main()
#        out, err = capsys.readouterr()
#        assert not re.search(r"Connected to radio", out, re.MULTILINE)
#        assert re.search(r"# start of Meshtastic configure yaml", out, re.MULTILINE)
#        assert err == ""
#        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_gpio_rd_no_gpio_channel(capsys):
    """Test --gpio_rd with no named gpio channel"""
    sys.argv = ["", "--gpio-rd", "0x10", "--dest", "!foo"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode.getChannelByName.return_value = None
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"Warning: No channel named", out)
        assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_gpio_rd_no_dest(capsys):
    """Test --gpio_rd with a named gpio channel but no dest was specified"""
    sys.argv = ["", "--gpio-rd", "0x2000"]
    mt_config.args = sys.argv

    channel = Channel(index=2, role=2)
    channel.settings.psk = b"\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84"
    channel.settings.name = "gpio"

    iface = MagicMock(autospec=SerialInterface)
    iface.localNode.getChannelByName.return_value = channel
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"Warning: Must use a destination node ID", out)
        assert err == ""


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# @patch('time.sleep')
# def test_main_gpio_rd(caplog, capsys):
#    """Test --gpio_rd with a named gpio channel"""
#    # Note: On the Heltec v2.1, there is a GPIO pin GPIO 13 that does not have a
#    # red arrow (meaning ok to use for our purposes)
#    # See https://resource.heltec.cn/download/WiFi_LoRa_32/WIFI_LoRa_32_V2.pdf
#    # To find out the mask for GPIO 13, let us assign n as 13.
#    # 1. Find the 2^n or 2^13 (8192)
#    # 2. Convert 8192 decimal to hex (0x2000)
#    # You can use python:
#    # >>> print(hex(2**13))
#    # 0x2000
#    sys.argv = ['', '--gpio-rd', '0x1000', '--dest', '!1234']
#    mt_config.args = sys.argv
#
#    channel = Channel(index=1, role=1)
#    channel.settings.modem_config = 3
#    channel.settings.psk = b'\x01'
#
#    packet = {
#
#            'from': 682968668,
#            'to': 682968612,
#            'channel': 1,
#            'decoded': {
#                'portnum': 'REMOTE_HARDWARE_APP',
#                'payload': b'\x08\x05\x18\x80 ',
#                'requestId': 1629980484,
#                'remotehw': {
#                    'typ': 'READ_GPIOS_REPLY',
#                    'gpioValue': '4096',
#                    'raw': 'faked',
#                    'id': 1693085229,
#                    'rxTime': 1640294262,
#                    'rxSnr': 4.75,
#                    'hopLimit': 3,
#                    'wantAck': True,
#                    }
#                }
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    iface.localNode.getChannelByName.return_value = channel
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        with caplog.at_level(logging.DEBUG):
#            main()
#            onGPIOreceive(packet, mo)
#    out, err = capsys.readouterr()
#    assert re.search(r'Connected to radio', out, re.MULTILINE)
#    assert re.search(r'Reading GPIO mask 0x1000 ', out, re.MULTILINE)
#    assert re.search(r'Received RemoteHardware typ=READ_GPIOS_REPLY, gpio_value=4096', out, re.MULTILINE)
#    assert err == ''


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# @patch('time.sleep')
# def test_main_gpio_rd_with_no_gpioMask(caplog, capsys):
#    """Test --gpio_rd with a named gpio channel"""
#    sys.argv = ['', '--gpio-rd', '0x1000', '--dest', '!1234']
#    mt_config.args = sys.argv
#
#    channel = Channel(index=1, role=1)
#    channel.settings.modem_config = 3
#    channel.settings.psk = b'\x01'
#
#    # Note: Intentionally do not have gpioValue in response as that is the
#    # default value
#    packet = {
#            'from': 682968668,
#            'to': 682968612,
#            'channel': 1,
#            'decoded': {
#                'portnum': 'REMOTE_HARDWARE_APP',
#                'payload': b'\x08\x05\x18\x80 ',
#                'requestId': 1629980484,
#                'remotehw': {
#                    'typ': 'READ_GPIOS_REPLY',
#                    'raw': 'faked',
#                    'id': 1693085229,
#                    'rxTime': 1640294262,
#                    'rxSnr': 4.75,
#                    'hopLimit': 3,
#                    'wantAck': True,
#                    }
#                }
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    iface.localNode.getChannelByName.return_value = channel
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        with caplog.at_level(logging.DEBUG):
#            main()
#            onGPIOreceive(packet, mo)
#    out, err = capsys.readouterr()
#    assert re.search(r'Connected to radio', out, re.MULTILINE)
#    assert re.search(r'Reading GPIO mask 0x1000 ', out, re.MULTILINE)
#    assert re.search(r'Received RemoteHardware typ=READ_GPIOS_REPLY, gpio_value=0', out, re.MULTILINE)
#    assert err == ''


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_gpio_watch(caplog, capsys):
#    """Test --gpio_watch with a named gpio channel"""
#    sys.argv = ['', '--gpio-watch', '0x1000', '--dest', '!1234']
#    mt_config.args = sys.argv
#
#    def my_sleep(amount):
#        print(f'{amount}')
#        sys.exit(3)
#
#    channel = Channel(index=1, role=1)
#    channel.settings.modem_config = 3
#    channel.settings.psk = b'\x01'
#
#    packet = {
#
#            'from': 682968668,
#            'to': 682968612,
#            'channel': 1,
#            'decoded': {
#                'portnum': 'REMOTE_HARDWARE_APP',
#                'payload': b'\x08\x05\x18\x80 ',
#                'requestId': 1629980484,
#                'remotehw': {
#                    'typ': 'READ_GPIOS_REPLY',
#                    'gpioValue': '4096',
#                    'raw': 'faked',
#                    'id': 1693085229,
#                    'rxTime': 1640294262,
#                    'rxSnr': 4.75,
#                    'hopLimit': 3,
#                    'wantAck': True,
#                    }
#                }
#            }
#
#    with patch('time.sleep', side_effect=my_sleep):
#        with pytest.raises(SystemExit) as pytest_wrapped_e:
#            iface = MagicMock(autospec=SerialInterface)
#            iface.localNode.getChannelByName.return_value = channel
#            with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#                with caplog.at_level(logging.DEBUG):
#                    main()
#                    onGPIOreceive(packet, mo)
#        assert pytest_wrapped_e.type == SystemExit
#        assert pytest_wrapped_e.value.code == 3
#        out, err = capsys.readouterr()
#        assert re.search(r'Connected to radio', out, re.MULTILINE)
#        assert re.search(r'Watching GPIO mask 0x1000 ', out, re.MULTILINE)
#        assert err == ''


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_gpio_wrb(caplog, capsys):
#    """Test --gpio_wrb with a named gpio channel"""
#    sys.argv = ['', '--gpio-wrb', '4', '1', '--dest', '!1234']
#    mt_config.args = sys.argv
#
#    channel = Channel(index=1, role=1)
#    channel.settings.modem_config = 3
#    channel.settings.psk = b'\x01'
#
#    packet = {
#
#            'from': 682968668,
#            'to': 682968612,
#            'channel': 1,
#            'decoded': {
#                'portnum': 'REMOTE_HARDWARE_APP',
#                'payload': b'\x08\x05\x18\x80 ',
#                'requestId': 1629980484,
#                'remotehw': {
#                    'typ': 'READ_GPIOS_REPLY',
#                    'gpioValue': '16',
#                    'raw': 'faked',
#                    'id': 1693085229,
#                    'rxTime': 1640294262,
#                    'rxSnr': 4.75,
#                    'hopLimit': 3,
#                    'wantAck': True,
#                    }
#                }
#            }
#
#
#    iface = MagicMock(autospec=SerialInterface)
#    iface.localNode.getChannelByName.return_value = channel
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        with caplog.at_level(logging.DEBUG):
#            main()
#            onGPIOreceive(packet, mo)
#    out, err = capsys.readouterr()
#    assert re.search(r'Connected to radio', out, re.MULTILINE)
#    assert re.search(r'Writing GPIO mask 0x10 with value 0x10 to !1234', out, re.MULTILINE)
#    assert re.search(r'Received RemoteHardware typ=READ_GPIOS_REPLY, gpio_value=16 value=0', out, re.MULTILINE)
#    assert err == ''


# TODO
# need to restructure these for nested configs
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_getPref_valid_field(capsys):
#    """Test getPref() with a valid field"""
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = "ls_secs"
#    prefs.wifi_ssid = "foo"
#    prefs.ls_secs = 300
#    prefs.fixed_position = False
#
#    getPref(prefs, "ls_secs")
#    out, err = capsys.readouterr()
#    assert re.search(r"ls_secs: 300", out, re.MULTILINE)
#    assert err == ""
#
#
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_getPref_valid_field_camel(capsys):
#    """Test getPref() with a valid field"""
#    mt_config.camel_case = True
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = "ls_secs"
#    prefs.wifi_ssid = "foo"
#    prefs.ls_secs = 300
#    prefs.fixed_position = False
#
#    getPref(prefs, "ls_secs")
#    out, err = capsys.readouterr()
#    assert re.search(r"lsSecs: 300", out, re.MULTILINE)
#    assert err == ""
#
#
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_getPref_valid_field_string(capsys):
#    """Test getPref() with a valid field and value as a string"""
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = "wifi_ssid"
#    prefs.wifi_ssid = "foo"
#    prefs.ls_secs = 300
#    prefs.fixed_position = False
#
#    getPref(prefs, "wifi_ssid")
#    out, err = capsys.readouterr()
#    assert re.search(r"wifi_ssid: foo", out, re.MULTILINE)
#    assert err == ""
#
#
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_getPref_valid_field_string_camel(capsys):
#    """Test getPref() with a valid field and value as a string"""
#    mt_config.camel_case = True
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = "wifi_ssid"
#    prefs.wifi_ssid = "foo"
#    prefs.ls_secs = 300
#    prefs.fixed_position = False
#
#    getPref(prefs, "wifi_ssid")
#    out, err = capsys.readouterr()
#    assert re.search(r"wifiSsid: foo", out, re.MULTILINE)
#    assert err == ""
#
#
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_getPref_valid_field_bool(capsys):
#    """Test getPref() with a valid field and value as a bool"""
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = "fixed_position"
#    prefs.wifi_ssid = "foo"
#    prefs.ls_secs = 300
#    prefs.fixed_position = False
#
#    getPref(prefs, "fixed_position")
#    out, err = capsys.readouterr()
#    assert re.search(r"fixed_position: False", out, re.MULTILINE)
#    assert err == ""
#
#
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_getPref_valid_field_bool_camel(capsys):
#    """Test getPref() with a valid field and value as a bool"""
#    mt_config.camel_case = True
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = "fixed_position"
#    prefs.wifi_ssid = "foo"
#    prefs.ls_secs = 300
#    prefs.fixed_position = False
#
#    getPref(prefs, "fixed_position")
#    out, err = capsys.readouterr()
#    assert re.search(r"fixedPosition: False", out, re.MULTILINE)
#    assert err == ""
#
#
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_getPref_invalid_field(capsys):
#    """Test getPref() with an invalid field"""
#
#    class Field:
#        """Simple class for testing."""
#
#        def __init__(self, name):
#            """constructor"""
#            self.name = name
#
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = None
#
#    # Note: This is a subset of the real fields
#    ls_secs_field = Field("ls_secs")
#    is_router = Field("is_router")
#    fixed_position = Field("fixed_position")
#
#    fields = [ls_secs_field, is_router, fixed_position]
#    prefs.DESCRIPTOR.fields = fields
#
#    getPref(prefs, "foo")
#
#    out, err = capsys.readouterr()
#    assert re.search(r"does not have an attribute called foo", out, re.MULTILINE)
#    # ensure they are sorted
#    assert re.search(r"fixed_position\s+is_router\s+ls_secs", out, re.MULTILINE)
#    assert err == ""
#
#
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_getPref_invalid_field_camel(capsys):
#    """Test getPref() with an invalid field"""
#    mt_config.camel_case = True
#
#    class Field:
#        """Simple class for testing."""
#
#        def __init__(self, name):
#            """constructor"""
#            self.name = name
#
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = None
#
#    # Note: This is a subset of the real fields
#    ls_secs_field = Field("ls_secs")
#    is_router = Field("is_router")
#    fixed_position = Field("fixed_position")
#
#    fields = [ls_secs_field, is_router, fixed_position]
#    prefs.DESCRIPTOR.fields = fields
#
#    getPref(prefs, "foo")
#
#    out, err = capsys.readouterr()
#    assert re.search(r"does not have an attribute called foo", out, re.MULTILINE)
#    # ensure they are sorted
#    assert re.search(r"fixedPosition\s+isRouter\s+lsSecs", out, re.MULTILINE)
#    assert err == ""
#
#
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_setPref_valid_field_int_as_string(capsys):
#    """Test setPref() with a valid field"""
#
#    class Field:
#        """Simple class for testing."""
#
#        def __init__(self, name, enum_type):
#            """constructor"""
#            self.name = name
#            self.enum_type = enum_type
#
#    ls_secs_field = Field("ls_secs", "int")
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = ls_secs_field
#
#    setPref(prefs, "ls_secs", "300")
#    out, err = capsys.readouterr()
#    assert re.search(r"Set ls_secs to 300", out, re.MULTILINE)
#    assert err == ""


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_setPref_valid_field_invalid_enum(capsys, caplog):
#    """Test setPref() with a valid field but invalid enum value"""
#
#    radioConfig = RadioConfig()
#    prefs = radioConfig.preferences
#
#    with caplog.at_level(logging.DEBUG):
#        setPref(prefs, 'charge_current', 'foo')
#        out, err = capsys.readouterr()
#        assert re.search(r'charge_current does not have an enum called foo', out, re.MULTILINE)
#        assert re.search(r'Choices in sorted order are', out, re.MULTILINE)
#        assert re.search(r'MA100', out, re.MULTILINE)
#        assert re.search(r'MA280', out, re.MULTILINE)
#        assert err == ''


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_setPref_valid_field_invalid_enum_where_enums_are_camel_cased_values(capsys, caplog):
#    """Test setPref() with a valid field but invalid enum value"""
#
#    radioConfig = RadioConfig()
#    prefs = radioConfig.preferences
#
#    with caplog.at_level(logging.DEBUG):
#        setPref(prefs, 'region', 'foo')
#        out, err = capsys.readouterr()
#        assert re.search(r'region does not have an enum called foo', out, re.MULTILINE)
#        assert re.search(r'Choices in sorted order are', out, re.MULTILINE)
#        assert re.search(r'ANZ', out, re.MULTILINE)
#        assert re.search(r'CN', out, re.MULTILINE)
#        assert err == ''


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_setPref_valid_field_invalid_enum_camel(capsys, caplog):
#    """Test setPref() with a valid field but invalid enum value"""
#    mt_config.camel_case = True
#
#    radioConfig = RadioConfig()
#    prefs = radioConfig.preferences
#
#    with caplog.at_level(logging.DEBUG):
#        setPref(prefs, 'charge_current', 'foo')
#        out, err = capsys.readouterr()
#        assert re.search(r'chargeCurrent does not have an enum called foo', out, re.MULTILINE)
#        assert err == ''


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_setPref_valid_field_valid_enum(capsys, caplog):
#    """Test setPref() with a valid field and valid enum value"""
#
#    # charge_current
#    # some valid values:   MA100 MA1000 MA1080
#
#    radioConfig = RadioConfig()
#    prefs = radioConfig.preferences
#
#    with caplog.at_level(logging.DEBUG):
#        setPref(prefs, 'charge_current', 'MA100')
#        out, err = capsys.readouterr()
#        assert re.search(r'Set charge_current to MA100', out, re.MULTILINE)
#        assert err == ''


# TODO
# @pytest.mark.unit
# @pytest.mark.usefixtures("reset_mt_config")
# def test_main_setPref_valid_field_valid_enum_camel(capsys, caplog):
#    """Test setPref() with a valid field and valid enum value"""
#    mt_config.camel_case = True
#
#    # charge_current
#    # some valid values:   MA100 MA1000 MA1080
#
#    radioConfig = RadioConfig()
#    prefs = radioConfig.preferences
#
#    with caplog.at_level(logging.DEBUG):
#        setPref(prefs, 'charge_current', 'MA100')
#        out, err = capsys.readouterr()
#        assert re.search(r'Set chargeCurrent to MA100', out, re.MULTILINE)
#        assert err == ''

# TODO
# need to update for nested configs
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_setPref_invalid_field(capsys):
#    """Test setPref() with a invalid field"""
#
#    class Field:
#        """Simple class for testing."""
#
#        def __init__(self, name):
#            """constructor"""
#            self.name = name
#
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = None
#
#    # Note: This is a subset of the real fields
#    ls_secs_field = Field("ls_secs")
#    is_router = Field("is_router")
#    fixed_position = Field("fixed_position")
#
#    fields = [ls_secs_field, is_router, fixed_position]
#    prefs.DESCRIPTOR.fields = fields
#
#    setPref(prefs, "foo", "300")
#    out, err = capsys.readouterr()
#    assert re.search(r"does not have an attribute called foo", out, re.MULTILINE)
#    # ensure they are sorted
#    assert re.search(r"fixed_position\s+is_router\s+ls_secs", out, re.MULTILINE)
#    assert err == ""
#
#
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_setPref_invalid_field_camel(capsys):
#    """Test setPref() with a invalid field"""
#    mt_config.camel_case = True
#
#    class Field:
#        """Simple class for testing."""
#
#        def __init__(self, name):
#            """constructor"""
#            self.name = name
#
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = None
#
#    # Note: This is a subset of the real fields
#    ls_secs_field = Field("ls_secs")
#    is_router = Field("is_router")
#    fixed_position = Field("fixed_position")
#
#    fields = [ls_secs_field, is_router, fixed_position]
#    prefs.DESCRIPTOR.fields = fields
#
#    setPref(prefs, "foo", "300")
#    out, err = capsys.readouterr()
#    assert re.search(r"does not have an attribute called foo", out, re.MULTILINE)
#    # ensure they are sorted
#    assert re.search(r"fixedPosition\s+isRouter\s+lsSecs", out, re.MULTILINE)
#    assert err == ""
#
#
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_setPref_ignore_incoming_123(capsys):
#    """Test setPref() with ignore_incoming"""
#
#    class Field:
#        """Simple class for testing."""
#
#        def __init__(self, name, enum_type):
#            """constructor"""
#            self.name = name
#            self.enum_type = enum_type
#
#    ignore_incoming_field = Field("ignore_incoming", "list")
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = ignore_incoming_field
#
#    setPref(prefs, "ignore_incoming", "123")
#    out, err = capsys.readouterr()
#    assert re.search(r"Adding '123' to the ignore_incoming list", out, re.MULTILINE)
#    assert re.search(r"Set ignore_incoming to 123", out, re.MULTILINE)
#    assert err == ""
#
#
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_setPref_ignore_incoming_0(capsys):
#    """Test setPref() with ignore_incoming"""
#
#    class Field:
#        """Simple class for testing."""
#
#        def __init__(self, name, enum_type):
#            """constructor"""
#            self.name = name
#            self.enum_type = enum_type
#
#    ignore_incoming_field = Field("ignore_incoming", "list")
#    prefs = MagicMock()
#    prefs.DESCRIPTOR.fields_by_name.get.return_value = ignore_incoming_field
#
#    setPref(prefs, "ignore_incoming", "0")
#    out, err = capsys.readouterr()
#    assert re.search(r"Clearing ignore_incoming list", out, re.MULTILINE)
#    assert re.search(r"Set ignore_incoming to 0", out, re.MULTILINE)
#    assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_set_psk_no_ch_index(capsys):
    """Test --ch-set psk"""
    sys.argv = ["", "--ch-set", "psk", "foo", "--host", "meshtastic.local"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=TCPInterface)
    with patch("meshtastic.tcp_interface.TCPInterface", return_value=iface) as mo:
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"Warning: Need to specify '--ch-index'", out, re.MULTILINE)
        assert err == ""
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_ch_set_psk_with_ch_index(capsys):
    """Test --ch-set psk"""
    sys.argv = [
        "",
        "--ch-set",
        "psk",
        "foo",
        "--host",
        "meshtastic.local",
        "--ch-index",
        "0",
    ]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=TCPInterface)
    with patch("meshtastic.tcp_interface.TCPInterface", return_value=iface) as mo:
        main()
    out, err = capsys.readouterr()
    assert re.search(r"Connected to radio", out, re.MULTILINE)
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert err == ""
    mo.assert_called()


# TODO
# doesn't work properly with nested/module config stuff
#@pytest.mark.unit
#@pytest.mark.usefixtures("reset_mt_config")
#def test_main_ch_set_name_with_ch_index(capsys):
#    """Test --ch-set setting other than psk"""
#    sys.argv = [
#        "",
#        "--ch-set",
#        "name",
#        "foo",
#        "--host",
#        "meshtastic.local",
#        "--ch-index",
#        "0",
#    ]
#    mt_config.args = sys.argv
#
#    iface = MagicMock(autospec=TCPInterface)
#    with patch("meshtastic.tcp_interface.TCPInterface", return_value=iface) as mo:
#        main()
#    out, err = capsys.readouterr()
#    assert re.search(r"Connected to radio", out, re.MULTILINE)
#    assert re.search(r"Set name to foo", out, re.MULTILINE)
#    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
#    assert err == ""
#    mo.assert_called()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_onNode(capsys):
    """Test onNode"""
    onNode("foo")
    out, err = capsys.readouterr()
    assert re.search(r"Node changed", out, re.MULTILINE)
    assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_tunnel_no_args(capsys):
    """Test tunnel no arguments"""
    sys.argv = [""]
    mt_config.args = sys.argv
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        tunnelMain()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    _, err = capsys.readouterr()
    assert re.search(r"usage: ", err, re.MULTILINE)


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("meshtastic.util.findPorts", return_value=[])
@patch("platform.system")
def test_tunnel_tunnel_arg_with_no_devices(mock_platform_system, caplog, capsys):
    """Test tunnel with tunnel arg (act like we are on a linux system)"""
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    sys.argv = ["", "--tunnel"]
    mt_config.args = sys.argv
    print(f"platform.system():{platform.system()}")
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            tunnelMain()
        mock_platform_system.assert_called()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"No.*Meshtastic.*device.*detected", out, re.MULTILINE)
        assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("meshtastic.util.findPorts", return_value=[])
@patch("platform.system")
def test_tunnel_subnet_arg_with_no_devices(mock_platform_system, caplog, capsys):
    """Test tunnel with subnet arg (act like we are on a linux system)"""
    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    sys.argv = ["", "--subnet", "foo"]
    mt_config.args = sys.argv
    print(f"platform.system():{platform.system()}")
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            tunnelMain()
        mock_platform_system.assert_called()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.search(r"No.*Meshtastic.*device.*detected", out, re.MULTILINE)
        assert err == ""


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@patch("platform.system")
@patch("termios.tcsetattr")
@patch("termios.tcgetattr")
@patch("builtins.open", new_callable=mock_open, read_data="data")
@patch("serial.Serial")
@patch("meshtastic.util.findPorts", return_value=["/dev/ttyUSBfake"])
def test_tunnel_tunnel_arg(
    mocked_findPorts, mocked_serial, mocked_open, mock_get, mock_set, mock_platform_system, caplog, iface_with_nodes, capsys
):
    """Test tunnel with tunnel arg (act like we are on a linux system)"""

    # Override the time.sleep so there is no loop
    def my_sleep(amount):
        print(f"{amount}")
        sys.exit(3)

    a_mock = MagicMock()
    a_mock.return_value = "Linux"
    mock_platform_system.side_effect = a_mock
    sys.argv = ["", "--tunnel"]
    mt_config.args = sys.argv

    serialInterface = SerialInterface(noProto=True)

    with caplog.at_level(logging.DEBUG):
        with patch("meshtastic.serial_interface.SerialInterface", return_value=serialInterface):
            with patch("time.sleep", side_effect=my_sleep):
                with pytest.raises(SystemExit) as pytest_wrapped_e:
                    tunnelMain()
                    mock_platform_system.assert_called()
                assert pytest_wrapped_e.type == SystemExit
                assert pytest_wrapped_e.value.code == 3
                assert re.search(r"Not starting Tunnel", caplog.text, re.MULTILINE)
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert err == ""
