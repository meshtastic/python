"""Meshtastic unit tests for node.py"""

import logging
import re
from unittest.mock import MagicMock, patch

import pytest

from ..protobuf import localonly_pb2, config_pb2
from ..protobuf.channel_pb2 import Channel # pylint: disable=E0611
from ..node import Node
from ..serial_interface import SerialInterface
from ..mesh_interface import MeshInterface

# from ..config_pb2 import Config
# from ..cannedmessages_pb2 import (CannedMessagePluginMessagePart1, CannedMessagePluginMessagePart2,
#                                  CannedMessagePluginMessagePart3, CannedMessagePluginMessagePart4,
#                                  CannedMessagePluginMessagePart5)
# from ..util import Timeout


@pytest.mark.unit
def test_node(capsys):
    """Test that we can instantiate a Node"""
    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        mo.localNode.getChannelByName.return_value = None
        mo.myInfo.max_channels = 8
        anode = Node(mo, "bar", noProto=True)
        lc = localonly_pb2.LocalConfig()
        anode.localConfig = lc
        lc.lora.CopyFrom(config_pb2.Config.LoRaConfig())
        anode.moduleConfig = localonly_pb2.LocalModuleConfig()
        anode.showInfo()
        out, err = capsys.readouterr()
        assert re.search(r'Preferences', out)
        assert re.search(r'Module preferences', out)
        assert re.search(r'Channels', out)
        assert re.search(r'Primary channel URL', out)
        assert not re.search(r'remote node', out)
        assert err == ''

# TODO
# @pytest.mark.unit
# def test_node_requestConfig(capsys):
#    """Test run requestConfig"""
#    iface = MagicMock(autospec=SerialInterface)
#    amesg = MagicMock(autospec=AdminMessage)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        with patch('meshtastic.admin_pb2.AdminMessage', return_value=amesg):
#            anode = Node(mo, 'bar')
#            anode.requestConfig()
#    out, err = capsys.readouterr()
#    assert re.search(r'Requesting preferences from remote node', out, re.MULTILINE)
#    assert err == ''


# @pytest.mark.unit
# def test_node_get_canned_message_with_all_parts(capsys):
#    """Test run get_canned_message()"""
#    iface = MagicMock(autospec=SerialInterface)
#    amesg = MagicMock(autospec=AdminMessage)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        with patch('meshtastic.admin_pb2.AdminMessage', return_value=amesg):
#            # we have a sleep in this method, so override it so it goes fast
#            with patch('time.sleep'):
#                anode = Node(mo, 'bar')
#                anode.cannedPluginMessagePart1 = 'a'
#                anode.cannedPluginMessagePart2 = 'b'
#                anode.cannedPluginMessagePart3 = 'c'
#                anode.cannedPluginMessagePart4 = 'd'
#                anode.cannedPluginMessagePart5 = 'e'
#                anode.get_canned_message()
#    out, err = capsys.readouterr()
#    assert re.search(r'canned_plugin_message:abcde', out, re.MULTILINE)
#    assert err == ''
#
#
# @pytest.mark.unit
# def test_node_get_canned_message_with_some_parts(capsys):
#    """Test run get_canned_message()"""
#    iface = MagicMock(autospec=SerialInterface)
#    amesg = MagicMock(autospec=AdminMessage)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        with patch('meshtastic.admin_pb2.AdminMessage', return_value=amesg):
#            # we have a sleep in this method, so override it so it goes fast
#            with patch('time.sleep'):
#                anode = Node(mo, 'bar')
#                anode.cannedPluginMessagePart1 = 'a'
#                anode.get_canned_message()
#    out, err = capsys.readouterr()
#    assert re.search(r'canned_plugin_message:a', out, re.MULTILINE)
#    assert err == ''
#
#
# @pytest.mark.unit
# def test_node_set_canned_message_one_part(caplog):
#    """Test run set_canned_message()"""
#    iface = MagicMock(autospec=SerialInterface)
#    amesg = MagicMock(autospec=AdminMessage)
#    with caplog.at_level(logging.DEBUG):
#        with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#            with patch('meshtastic.admin_pb2.AdminMessage', return_value=amesg):
#                anode = Node(mo, 'bar')
#                anode.set_canned_message('foo')
#    assert re.search(r"Setting canned message 'foo' part 1", caplog.text, re.MULTILINE)
#    assert not re.search(r"Setting canned message '' part 2", caplog.text, re.MULTILINE)
#
#
# @pytest.mark.unit
# def test_node_set_canned_message_200(caplog):
#    """Test run set_canned_message() 200 characters long"""
#    iface = MagicMock(autospec=SerialInterface)
#    amesg = MagicMock(autospec=AdminMessage)
#    with caplog.at_level(logging.DEBUG):
#        with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#            with patch('meshtastic.admin_pb2.AdminMessage', return_value=amesg):
#                anode = Node(mo, 'bar')
#                message_200_chars_long = 'a' * 200
#                anode.set_canned_message(message_200_chars_long)
#    assert re.search(r" part 1", caplog.text, re.MULTILINE)
#    assert not re.search(r"Setting canned message '' part 2", caplog.text, re.MULTILINE)
#
#
# @pytest.mark.unit
# def test_node_set_canned_message_201(caplog):
#    """Test run set_canned_message() 201 characters long"""
#    iface = MagicMock(autospec=SerialInterface)
#    amesg = MagicMock(autospec=AdminMessage)
#    with caplog.at_level(logging.DEBUG):
#        with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#            with patch('meshtastic.admin_pb2.AdminMessage', return_value=amesg):
#                anode = Node(mo, 'bar')
#                message_201_chars_long = 'a' * 201
#                anode.set_canned_message(message_201_chars_long)
#    assert re.search(r" part 1", caplog.text, re.MULTILINE)
#    assert re.search(r"Setting canned message 'a' part 2", caplog.text, re.MULTILINE)
#
#
# @pytest.mark.unit
# def test_node_set_canned_message_1000(caplog):
#    """Test run set_canned_message() 1000 characters long"""
#    iface = MagicMock(autospec=SerialInterface)
#    amesg = MagicMock(autospec=AdminMessage)
#    with caplog.at_level(logging.DEBUG):
#        with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#            with patch('meshtastic.admin_pb2.AdminMessage', return_value=amesg):
#                anode = Node(mo, 'bar')
#                message_1000_chars_long = 'a' * 1000
#                anode.set_canned_message(message_1000_chars_long)
#    assert re.search(r" part 1", caplog.text, re.MULTILINE)
#    assert re.search(r" part 2", caplog.text, re.MULTILINE)
#    assert re.search(r" part 3", caplog.text, re.MULTILINE)
#    assert re.search(r" part 4", caplog.text, re.MULTILINE)
#    assert re.search(r" part 5", caplog.text, re.MULTILINE)
#
#
# @pytest.mark.unit
# def test_node_set_canned_message_1001(capsys):
#    """Test run set_canned_message() 1001 characters long"""
#    iface = MagicMock(autospec=SerialInterface)
#    with pytest.raises(SystemExit) as pytest_wrapped_e:
#        with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#            anode = Node(mo, 'bar')
#            message_1001_chars_long = 'a' * 1001
#            anode.set_canned_message(message_1001_chars_long)
#    assert pytest_wrapped_e.type == SystemExit
#    assert pytest_wrapped_e.value.code == 1
#    out, err = capsys.readouterr()
#    assert re.search(r'Warning: The canned message', out, re.MULTILINE)
#    assert err == ''


# TODO
# @pytest.mark.unit
# def test_setOwnerShort(caplog):
#    """Test setOwner"""
#    anode = Node('foo', 'bar', noProto=True)
#    with caplog.at_level(logging.DEBUG):
#        anode.setOwner(long_name=None, short_name='123')
#    assert re.search(r'p.set_owner.short_name:123:', caplog.text, re.MULTILINE)


# TODO
# @pytest.mark.unit
# def test_setOwner_no_short_name(caplog):
#    """Test setOwner"""
#    anode = Node('foo', 'bar', noProto=True)
#    with caplog.at_level(logging.DEBUG):
#        anode.setOwner(long_name ='Test123')
#    assert re.search(r'p.set_owner.long_name:Test123:', caplog.text, re.MULTILINE)
#    assert re.search(r'p.set_owner.short_name:Tst:', caplog.text, re.MULTILINE)
#    assert re.search(r'p.set_owner.is_licensed:False', caplog.text, re.MULTILINE)


# TODO
# @pytest.mark.unit
# def test_setOwner_no_short_name_and_long_name_is_short(caplog):
#    """Test setOwner"""
#    anode = Node('foo', 'bar', noProto=True)
#    with caplog.at_level(logging.DEBUG):
#        anode.setOwner(long_name ='Tnt')
#    assert re.search(r'p.set_owner.long_name:Tnt:', caplog.text, re.MULTILINE)
#    assert re.search(r'p.set_owner.short_name:Tnt:', caplog.text, re.MULTILINE)
#    assert re.search(r'p.set_owner.is_licensed:False', caplog.text, re.MULTILINE)


# TODO
# @pytest.mark.unit
# def test_setOwner_no_short_name_and_long_name_has_words(caplog):
#    """Test setOwner"""
#    anode = Node('foo', 'bar', noProto=True)
#    with caplog.at_level(logging.DEBUG):
#        anode.setOwner(long_name ='A B C', is_licensed=True)
#    assert re.search(r'p.set_owner.long_name:A B C:', caplog.text, re.MULTILINE)
#    assert re.search(r'p.set_owner.short_name:ABC:', caplog.text, re.MULTILINE)
#    assert re.search(r'p.set_owner.is_licensed:True', caplog.text, re.MULTILINE)


# TODO
# @pytest.mark.unit
# def test_setOwner_long_name_no_short(caplog):
#    """Test setOwner"""
#    anode = Node('foo', 'bar', noProto=True)
#    with caplog.at_level(logging.DEBUG):
#        anode.setOwner(long_name ='Aabo', is_licensed=True)
#    assert re.search(r'p.set_owner.long_name:Aabo:', caplog.text, re.MULTILINE)
#    assert re.search(r'p.set_owner.short_name:Aab:', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_exitSimulator(caplog):
    """Test exitSimulator"""
    anode = Node("foo", "bar", noProto=True)
    with caplog.at_level(logging.DEBUG):
        anode.exitSimulator()
    assert re.search(r"in exitSimulator", caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_reboot(caplog):
    """Test reboot"""
    anode = Node(MeshInterface(), 1234567890, noProto=True)
    with caplog.at_level(logging.DEBUG):
        anode.reboot()
    assert re.search(r"Telling node to reboot", caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_shutdown(caplog):
    """Test shutdown"""
    anode = Node(MeshInterface(), 1234567890, noProto=True)
    with caplog.at_level(logging.DEBUG):
        anode.shutdown()
    assert re.search(r"Telling node to shutdown", caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_setURL_empty_url(capsys):
    """Test reboot"""
    anode = Node("foo", "bar", noProto=True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        anode.setURL("")
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.search(r"Warning: There were no settings.", out, re.MULTILINE)
    assert err == ""


# TODO
# @pytest.mark.unit
# def test_setURL_valid_URL(caplog):
#    """Test setURL"""
#    iface = MagicMock(autospec=SerialInterface)
#    url = "https://www.meshtastic.org/d/#CgUYAyIBAQ"
#    with caplog.at_level(logging.DEBUG):
#        anode = Node(iface, 'bar', noProto=True)
#        anode.radioConfig = 'baz'
#        channels = ['zoo']
#        anode.channels = channels
#        anode.setURL(url)
#    assert re.search(r'Channel i:0', caplog.text, re.MULTILINE)
#    assert re.search(r'modem_config: MidSlow', caplog.text, re.MULTILINE)
#    assert re.search(r'psk: "\\001"', caplog.text, re.MULTILINE)
#    assert re.search(r'role: PRIMARY', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_setURL_valid_URL_but_no_settings(capsys):
    """Test setURL"""
    iface = MagicMock(autospec=SerialInterface)
    url = "https://www.meshtastic.org/d/#"
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        anode = Node(iface, "bar", noProto=True)
        anode.radioConfig = "baz"
        anode.setURL(url)
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.search(r"Warning: There were no settings", out, re.MULTILINE)
    assert err == ""


# TODO
# @pytest.mark.unit
# def test_showChannels(capsys):
#    """Test showChannels"""
#    anode = Node('foo', 'bar')
#
#    # primary channel
#    # role: 0=Disabled, 1=Primary, 2=Secondary
#    # modem_config: 0-5
#    # role: 0=Disabled, 1=Primary, 2=Secondary
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    channel2 = Channel(index=2, role=2)
#    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
#    channel2.settings.name = 'testing'
#
#    channel3 = Channel(index=3, role=0)
#    channel4 = Channel(index=4, role=0)
#    channel5 = Channel(index=5, role=0)
#    channel6 = Channel(index=6, role=0)
#    channel7 = Channel(index=7, role=0)
#    channel8 = Channel(index=8, role=0)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#    anode.channels = channels
#    anode.showChannels()
#    out, err = capsys.readouterr()
#    assert re.search(r'Channels:', out, re.MULTILINE)
#    # primary channel
#    assert re.search(r'Primary channel URL', out, re.MULTILINE)
#    assert re.search(r'PRIMARY psk=default ', out, re.MULTILINE)
#    assert re.search(r'"modemConfig": "MidSlow"', out, re.MULTILINE)
#    assert re.search(r'"psk": "AQ=="', out, re.MULTILINE)
#    # secondary channel
#    assert re.search(r'SECONDARY psk=secret ', out, re.MULTILINE)
#    assert re.search(r'"psk": "ipR5DsbJHjWREkCmMKi0M4cA8ksO539Bes31sJAwqDQ="', out, re.MULTILINE)
#    assert err == ''


@pytest.mark.unit
def test_getChannelByChannelIndex():
    """Test getChannelByChannelIndex()"""
    anode = Node("foo", "bar")

    channel1 = Channel(index=1, role=1)  # primary channel
    channel2 = Channel(index=2, role=2)  # secondary channel
    channel3 = Channel(index=3, role=0)
    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [
        channel1,
        channel2,
        channel3,
        channel4,
        channel5,
        channel6,
        channel7,
        channel8,
    ]

    anode.channels = channels

    # test primary
    assert anode.getChannelByChannelIndex(0) is not None
    # test secondary
    assert anode.getChannelByChannelIndex(1) is not None
    # test disabled
    assert anode.getChannelByChannelIndex(2) is not None
    # test invalid values
    assert anode.getChannelByChannelIndex(-1) is None
    assert anode.getChannelByChannelIndex(9) is None


# TODO
# @pytest.mark.unit
# def test_deleteChannel_try_to_delete_primary_channel(capsys):
#    """Try to delete primary channel."""
#    anode = Node('foo', 'bar')
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    # no secondary channels
#    channel2 = Channel(index=2, role=0)
#    channel3 = Channel(index=3, role=0)
#    channel4 = Channel(index=4, role=0)
#    channel5 = Channel(index=5, role=0)
#    channel6 = Channel(index=6, role=0)
#    channel7 = Channel(index=7, role=0)
#    channel8 = Channel(index=8, role=0)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#    anode.channels = channels
#    with pytest.raises(SystemExit) as pytest_wrapped_e:
#        anode.deleteChannel(0)
#    assert pytest_wrapped_e.type == SystemExit
#    assert pytest_wrapped_e.value.code == 1
#    out, err = capsys.readouterr()
#    assert re.search(r'Warning: Only SECONDARY channels can be deleted', out, re.MULTILINE)
#    assert err == ''


# TODO
# @pytest.mark.unit
# def test_deleteChannel_secondary():
#    """Try to delete a secondary channel."""
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    channel2 = Channel(index=2, role=2)
#    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
#    channel2.settings.name = 'testing'
#
#    channel3 = Channel(index=3, role=0)
#    channel4 = Channel(index=4, role=0)
#    channel5 = Channel(index=5, role=0)
#    channel6 = Channel(index=6, role=0)
#    channel7 = Channel(index=7, role=0)
#    channel8 = Channel(index=8, role=0)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        mo.localNode.getChannelByName.return_value = None
#        mo.myInfo.max_channels = 8
#        anode = Node(mo, 'bar', noProto=True)
#
#        anode.channels = channels
#        assert len(anode.channels) == 8
#        assert channels[0].settings.modem_config == 3
#        assert channels[1].settings.name == 'testing'
#        assert channels[2].settings.name == ''
#        assert channels[3].settings.name == ''
#        assert channels[4].settings.name == ''
#        assert channels[5].settings.name == ''
#        assert channels[6].settings.name == ''
#        assert channels[7].settings.name == ''
#
#        anode.deleteChannel(1)
#
#        assert len(anode.channels) == 8
#        assert channels[0].settings.modem_config == 3
#        assert channels[1].settings.name == ''
#        assert channels[2].settings.name == ''
#        assert channels[3].settings.name == ''
#        assert channels[4].settings.name == ''
#        assert channels[5].settings.name == ''
#        assert channels[6].settings.name == ''
#        assert channels[7].settings.name == ''


# TODO
# @pytest.mark.unit
# def test_deleteChannel_secondary_with_admin_channel_after_testing():
#    """Try to delete a secondary channel where there is an admin channel."""
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    channel2 = Channel(index=2, role=2)
#    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
#    channel2.settings.name = 'testing'
#
#    channel3 = Channel(index=3, role=2)
#    channel3.settings.name = 'admin'
#
#    channel4 = Channel(index=4, role=0)
#    channel5 = Channel(index=5, role=0)
#    channel6 = Channel(index=6, role=0)
#    channel7 = Channel(index=7, role=0)
#    channel8 = Channel(index=8, role=0)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        mo.localNode.getChannelByName.return_value = None
#        mo.myInfo.max_channels = 8
#        anode = Node(mo, 'bar', noProto=True)
#
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        assert mo.localNode == anode
#
#        anode.channels = channels
#        assert len(anode.channels) == 8
#        assert channels[0].settings.modem_config == 3
#        assert channels[1].settings.name == 'testing'
#        assert channels[2].settings.name == 'admin'
#        assert channels[3].settings.name == ''
#        assert channels[4].settings.name == ''
#        assert channels[5].settings.name == ''
#        assert channels[6].settings.name == ''
#        assert channels[7].settings.name == ''
#
#        anode.deleteChannel(1)
#
#        assert len(anode.channels) == 8
#        assert channels[0].settings.modem_config == 3
#        assert channels[1].settings.name == 'admin'
#        assert channels[2].settings.name == ''
#        assert channels[3].settings.name == ''
#        assert channels[4].settings.name == ''
#        assert channels[5].settings.name == ''
#        assert channels[6].settings.name == ''
#        assert channels[7].settings.name == ''


# TODO
# @pytest.mark.unit
# def test_deleteChannel_secondary_with_admin_channel_before_testing():
#    """Try to delete a secondary channel where there is an admin channel."""
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    channel2 = Channel(index=2, role=2)
#    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
#    channel2.settings.name = 'admin'
#
#    channel3 = Channel(index=3, role=2)
#    channel3.settings.name = 'testing'
#
#    channel4 = Channel(index=4, role=0)
#    channel5 = Channel(index=5, role=0)
#    channel6 = Channel(index=6, role=0)
#    channel7 = Channel(index=7, role=0)
#    channel8 = Channel(index=8, role=0)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        mo.localNode.getChannelByName.return_value = None
#        mo.myInfo.max_channels = 8
#        anode = Node(mo, 'bar', noProto=True)
#
#        anode.channels = channels
#        assert len(anode.channels) == 8
#        assert channels[0].settings.modem_config == 3
#        assert channels[1].settings.name == 'admin'
#        assert channels[2].settings.name == 'testing'
#        assert channels[3].settings.name == ''
#        assert channels[4].settings.name == ''
#        assert channels[5].settings.name == ''
#        assert channels[6].settings.name == ''
#        assert channels[7].settings.name == ''
#
#        anode.deleteChannel(2)
#
#        assert len(anode.channels) == 8
#        assert channels[0].settings.modem_config == 3
#        assert channels[1].settings.name == 'admin'
#        assert channels[2].settings.name == ''
#        assert channels[3].settings.name == ''
#        assert channels[4].settings.name == ''
#        assert channels[5].settings.name == ''
#        assert channels[6].settings.name == ''
#        assert channels[7].settings.name == ''
#
#
# @pytest.mark.unit
# def test_getChannelByName():
#    """Get a channel by the name."""
#    anode = Node('foo', 'bar')
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    channel2 = Channel(index=2, role=2)
#    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
#    channel2.settings.name = 'admin'
#
#    channel3 = Channel(index=3, role=0)
#    channel4 = Channel(index=4, role=0)
#    channel5 = Channel(index=5, role=0)
#    channel6 = Channel(index=6, role=0)
#    channel7 = Channel(index=7, role=0)
#    channel8 = Channel(index=8, role=0)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#    anode.channels = channels
#    ch = anode.getChannelByName('admin')
#    assert ch.index == 2


# TODO
# @pytest.mark.unit
# def test_getChannelByName_invalid_name():
#    """Get a channel by the name but one that is not present."""
#    anode = Node('foo', 'bar')
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    channel2 = Channel(index=2, role=2)
#    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
#    channel2.settings.name = 'admin'
#
#    channel3 = Channel(index=3, role=0)
#    channel4 = Channel(index=4, role=0)
#    channel5 = Channel(index=5, role=0)
#    channel6 = Channel(index=6, role=0)
#    channel7 = Channel(index=7, role=0)
#    channel8 = Channel(index=8, role=0)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#    anode.channels = channels
#    ch = anode.getChannelByName('testing')
#    assert ch is None
#
#
# @pytest.mark.unit
# def test_getDisabledChannel():
#    """Get the first disabled channel."""
#    anode = Node('foo', 'bar')
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    channel2 = Channel(index=2, role=2)
#    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
#    channel2.settings.name = 'testingA'
#
#    channel3 = Channel(index=3, role=2)
#    channel3.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
#    channel3.settings.name = 'testingB'
#
#    channel4 = Channel(index=4, role=0)
#    channel5 = Channel(index=5, role=0)
#    channel6 = Channel(index=6, role=0)
#    channel7 = Channel(index=7, role=0)
#    channel8 = Channel(index=8, role=0)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#    anode.channels = channels
#    ch = anode.getDisabledChannel()
#    assert ch.index == 4


# TODO
# @pytest.mark.unit
# def test_getDisabledChannel_where_all_channels_are_used():
#    """Get the first disabled channel."""
#    anode = Node('foo', 'bar')
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    channel2 = Channel(index=2, role=2)
#    channel3 = Channel(index=3, role=2)
#    channel4 = Channel(index=4, role=2)
#    channel5 = Channel(index=5, role=2)
#    channel6 = Channel(index=6, role=2)
#    channel7 = Channel(index=7, role=2)
#    channel8 = Channel(index=8, role=2)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#    anode.channels = channels
#    ch = anode.getDisabledChannel()
#    assert ch is None


# TODO
# @pytest.mark.unit
# def test_getAdminChannelIndex():
#    """Get the 'admin' channel index."""
#    anode = Node('foo', 'bar')
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    channel2 = Channel(index=2, role=2)
#    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
#    channel2.settings.name = 'admin'
#
#    channel3 = Channel(index=3, role=0)
#    channel4 = Channel(index=4, role=0)
#    channel5 = Channel(index=5, role=0)
#    channel6 = Channel(index=6, role=0)
#    channel7 = Channel(index=7, role=0)
#    channel8 = Channel(index=8, role=0)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#    anode.channels = channels
#    i = anode._getAdminChannelIndex()
#    assert i == 2


# TODO
# @pytest.mark.unit
# def test_getAdminChannelIndex_when_no_admin_named_channel():
#    """Get the 'admin' channel when there is not one."""
#    anode = Node('foo', 'bar')
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    channel2 = Channel(index=2, role=0)
#    channel3 = Channel(index=3, role=0)
#    channel4 = Channel(index=4, role=0)
#    channel5 = Channel(index=5, role=0)
#    channel6 = Channel(index=6, role=0)
#    channel7 = Channel(index=7, role=0)
#    channel8 = Channel(index=8, role=0)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#    anode.channels = channels
#    i = anode._getAdminChannelIndex()
#    assert i == 0


# TODO
# TODO: should we check if we need to turn it off?
# @pytest.mark.unit
# def test_turnOffEncryptionOnPrimaryChannel(capsys):
#    """Turn off encryption when there is a psk."""
#    anode = Node('foo', 'bar', noProto=True)
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    # value from using "--ch-set psk 0x1a1a1a1a2b2b2b2b1a1a1a1a2b2b2b2b1a1a1a1a2b2b2b2b1a1a1a1a2b2b2b2b "
#    channel1.settings.psk = b'\x1a\x1a\x1a\x1a++++\x1a\x1a\x1a\x1a++++\x1a\x1a\x1a\x1a++++\x1a\x1a\x1a\x1a++++'
#
#    channel2 = Channel(index=2, role=0)
#    channel3 = Channel(index=3, role=0)
#    channel4 = Channel(index=4, role=0)
#    channel5 = Channel(index=5, role=0)
#    channel6 = Channel(index=6, role=0)
#    channel7 = Channel(index=7, role=0)
#    channel8 = Channel(index=8, role=0)
#
#    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]
#
#    anode.channels = channels
#    anode.turnOffEncryptionOnPrimaryChannel()
#    out, err = capsys.readouterr()
#    assert re.search(r'Writing modified channels to device', out)
#    assert err == ''


@pytest.mark.unit
def test_writeConfig_with_no_radioConfig(capsys):
    """Test writeConfig with no radioConfig."""
    anode = Node("foo", "bar", noProto=True)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        anode.writeConfig('foo')
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    print(out)
    assert re.search(r"Error: No valid config with name foo", out)
    assert err == ""


# TODO
# @pytest.mark.unit
# def test_writeConfig(caplog):
#    """Test writeConfig"""
#    anode = Node('foo', 'bar', noProto=True)
#    radioConfig = RadioConfig()
#    anode.radioConfig = radioConfig
#
#    with caplog.at_level(logging.DEBUG):
#        anode.writeConfig()
#    assert re.search(r'Wrote config', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_requestChannel_not_localNode(caplog, capsys):
    """Test _requestChannel()"""
    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        mo.localNode.getChannelByName.return_value = None
        mo.myInfo.max_channels = 8
        anode = Node(mo, "bar", noProto=True)
        with caplog.at_level(logging.DEBUG):
            anode._requestChannel(0)
            assert re.search(
                r"Requesting channel 0 info from remote node", caplog.text, re.MULTILINE
            )
        out, err = capsys.readouterr()
        assert re.search(r"Requesting channel 0 info", out, re.MULTILINE)
        assert err == ""


@pytest.mark.unit
def test_requestChannel_localNode(caplog):
    """Test _requestChannel()"""
    iface = MagicMock(autospec=SerialInterface)
    with patch("meshtastic.serial_interface.SerialInterface", return_value=iface) as mo:
        mo.localNode.getChannelByName.return_value = None
        mo.myInfo.max_channels = 8
        anode = Node(mo, "bar", noProto=True)

        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
        mo.localNode = anode

        with caplog.at_level(logging.DEBUG):
            anode._requestChannel(0)
            assert re.search(r"Requesting channel 0", caplog.text, re.MULTILINE)
            assert not re.search(r"from remote node", caplog.text, re.MULTILINE)


# @pytest.mark.unit
# def test_onResponseRequestCannedMessagePluginMesagePart1(caplog):
#    """Test onResponseRequestCannedMessagePluginMessagePart1()"""
#
#    part1 = CannedMessagePluginMessagePart1()
#    part1.text = 'foo1'
#
#    msg1 = MagicMock(autospec=AdminMessage)
#    msg1.get_canned_message_plugin_part1_response = part1
#
#    packet = {
#            'from': 682968612,
#            'to': 682968612,
#            'decoded': {
#                'portnum': 'ADMIN_APP',
#                'payload': 'faked',
#                'requestId': 927039000,
#                'admin': {
#                    'getCannedMessagePluginPart1Response': {'text': 'foo1'},
#                    'raw': msg1
#                    }
#                },
#            'id': 589440320,
#            'rxTime': 1642710843,
#            'hopLimit': 3,
#            'priority': 'RELIABLE',
#            'raw': 'faked',
#            'fromId': '!28b54624',
#            'toId': '!28b54624'
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        anode = Node(mo, 'bar', noProto=True)
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.onResponseRequestCannedMessagePluginMessagePart1(packet)
#            assert re.search(r'onResponseRequestCannedMessagePluginMessagePart1', caplog.text, re.MULTILINE)
#            assert anode.cannedPluginMessagePart1 == 'foo1'


# @pytest.mark.unit
# def test_onResponseRequestCannedMessagePluginMesagePart2(caplog):
#    """Test onResponseRequestCannedMessagePluginMessagePart2()"""
#
#    part2 = CannedMessagePluginMessagePart2()
#    part2.text = 'foo2'
#
#    msg2 = MagicMock(autospec=AdminMessage)
#    msg2.get_canned_message_plugin_part2_response = part2
#
#    packet = {
#            'from': 682968612,
#            'to': 682968612,
#            'decoded': {
#                'portnum': 'ADMIN_APP',
#                'payload': 'faked',
#                'requestId': 927039000,
#                'admin': {
#                    'getCannedMessagePluginPart2Response': {'text': 'foo2'},
#                    'raw': msg2
#                    }
#                },
#            'id': 589440320,
#            'rxTime': 1642710843,
#            'hopLimit': 3,
#            'priority': 'RELIABLE',
#            'raw': 'faked',
#            'fromId': '!28b54624',
#            'toId': '!28b54624'
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        anode = Node(mo, 'bar', noProto=True)
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.onResponseRequestCannedMessagePluginMessagePart2(packet)
#            assert re.search(r'onResponseRequestCannedMessagePluginMessagePart2', caplog.text, re.MULTILINE)
#            assert anode.cannedPluginMessagePart2 == 'foo2'


# @pytest.mark.unit
# def test_onResponseRequestCannedMessagePluginMesagePart3(caplog):
#    """Test onResponseRequestCannedMessagePluginMessagePart3()"""
#
#    part3 = CannedMessagePluginMessagePart3()
#    part3.text = 'foo3'
#
#    msg3 = MagicMock(autospec=AdminMessage)
#    msg3.get_canned_message_plugin_part3_response = part3
#
#    packet = {
#            'from': 682968612,
#            'to': 682968612,
#            'decoded': {
#                'portnum': 'ADMIN_APP',
#                'payload': 'faked',
#                'requestId': 927039000,
#                'admin': {
#                    'getCannedMessagePluginPart3Response': {'text': 'foo3'},
#                    'raw': msg3
#                    }
#                },
#            'id': 589440320,
#            'rxTime': 1642710843,
#            'hopLimit': 3,
#            'priority': 'RELIABLE',
#            'raw': 'faked',
#            'fromId': '!28b54624',
#            'toId': '!28b54624'
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        anode = Node(mo, 'bar', noProto=True)
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.onResponseRequestCannedMessagePluginMessagePart3(packet)
#            assert re.search(r'onResponseRequestCannedMessagePluginMessagePart3', caplog.text, re.MULTILINE)
#            assert anode.cannedPluginMessagePart3 == 'foo3'


# @pytest.mark.unit
# def test_onResponseRequestCannedMessagePluginMesagePart4(caplog):
#    """Test onResponseRequestCannedMessagePluginMessagePart4()"""
#
#    part4 = CannedMessagePluginMessagePart4()
#    part4.text = 'foo4'
#
#    msg4 = MagicMock(autospec=AdminMessage)
#    msg4.get_canned_message_plugin_part4_response = part4
#
#    packet = {
#            'from': 682968612,
#            'to': 682968612,
#            'decoded': {
#                'portnum': 'ADMIN_APP',
#                'payload': 'faked',
#                'requestId': 927039000,
#                'admin': {
#                    'getCannedMessagePluginPart4Response': {'text': 'foo4'},
#                    'raw': msg4
#                    }
#                },
#            'id': 589440320,
#            'rxTime': 1642710843,
#            'hopLimit': 3,
#            'priority': 'RELIABLE',
#            'raw': 'faked',
#            'fromId': '!28b54624',
#            'toId': '!28b54624'
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        anode = Node(mo, 'bar', noProto=True)
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.onResponseRequestCannedMessagePluginMessagePart4(packet)
#            assert re.search(r'onResponseRequestCannedMessagePluginMessagePart4', caplog.text, re.MULTILINE)
#            assert anode.cannedPluginMessagePart4 == 'foo4'


# @pytest.mark.unit
# def test_onResponseRequestCannedMessagePluginMesagePart5(caplog):
#    """Test onResponseRequestCannedMessagePluginMessagePart5()"""
#
#    part5 = CannedMessagePluginMessagePart5()
#    part5.text = 'foo5'
#
#    msg5 = MagicMock(autospec=AdminMessage)
#    msg5.get_canned_message_plugin_part5_response = part5
#
#
#    packet = {
#            'from': 682968612,
#            'to': 682968612,
#            'decoded': {
#                'portnum': 'ADMIN_APP',
#                'payload': 'faked',
#                'requestId': 927039000,
#                'admin': {
#                    'getCannedMessagePluginPart5Response': {'text': 'foo5'},
#                    'raw': msg5
#                    }
#                },
#            'id': 589440320,
#            'rxTime': 1642710843,
#            'hopLimit': 3,
#            'priority': 'RELIABLE',
#            'raw': 'faked',
#            'fromId': '!28b54624',
#            'toId': '!28b54624'
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        anode = Node(mo, 'bar', noProto=True)
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.onResponseRequestCannedMessagePluginMessagePart5(packet)
#            assert re.search(r'onResponseRequestCannedMessagePluginMessagePart5', caplog.text, re.MULTILINE)
#            assert anode.cannedPluginMessagePart5 == 'foo5'


# @pytest.mark.unit
# def test_onResponseRequestCannedMessagePluginMesagePart1_error(caplog, capsys):
#    """Test onResponseRequestCannedMessagePluginMessagePart1() with error"""
#
#    packet = {
#            'decoded': {
#                'routing': {
#                    'errorReason': 'some made up error',
#                    },
#                },
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        anode = Node(mo, 'bar', noProto=True)
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.onResponseRequestCannedMessagePluginMessagePart1(packet)
#            assert re.search(r'onResponseRequestCannedMessagePluginMessagePart1', caplog.text, re.MULTILINE)
#        out, err = capsys.readouterr()
#        assert re.search(r'Error on response', out)
#        assert err == ''


# @pytest.mark.unit
# def test_onResponseRequestCannedMessagePluginMesagePart2_error(caplog, capsys):
#    """Test onResponseRequestCannedMessagePluginMessagePart2() with error"""
#
#    packet = {
#            'decoded': {
#                'routing': {
#                    'errorReason': 'some made up error',
#                    },
#                },
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        anode = Node(mo, 'bar', noProto=True)
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.onResponseRequestCannedMessagePluginMessagePart2(packet)
#            assert re.search(r'onResponseRequestCannedMessagePluginMessagePart2', caplog.text, re.MULTILINE)
#        out, err = capsys.readouterr()
#        assert re.search(r'Error on response', out)
#        assert err == ''


# @pytest.mark.unit
# def test_onResponseRequestCannedMessagePluginMesagePart3_error(caplog, capsys):
#    """Test onResponseRequestCannedMessagePluginMessagePart3() with error"""
#
#    packet = {
#            'decoded': {
#                'routing': {
#                    'errorReason': 'some made up error',
#                    },
#                },
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        anode = Node(mo, 'bar', noProto=True)
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.onResponseRequestCannedMessagePluginMessagePart3(packet)
#            assert re.search(r'onResponseRequestCannedMessagePluginMessagePart3', caplog.text, re.MULTILINE)
#        out, err = capsys.readouterr()
#        assert re.search(r'Error on response', out)
#        assert err == ''
#
#
# @pytest.mark.unit
# def test_onResponseRequestCannedMessagePluginMesagePart4_error(caplog, capsys):
#    """Test onResponseRequestCannedMessagePluginMessagePart4() with error"""
#
#    packet = {
#            'decoded': {
#                'routing': {
#                    'errorReason': 'some made up error',
#                    },
#                },
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        anode = Node(mo, 'bar', noProto=True)
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.onResponseRequestCannedMessagePluginMessagePart4(packet)
#            assert re.search(r'onResponseRequestCannedMessagePluginMessagePart4', caplog.text, re.MULTILINE)
#        out, err = capsys.readouterr()
#        assert re.search(r'Error on response', out)
#        assert err == ''
#
#
# @pytest.mark.unit
# def test_onResponseRequestCannedMessagePluginMesagePart5_error(caplog, capsys):
#    """Test onResponseRequestCannedMessagePluginMessagePart5() with error"""
#
#    packet = {
#            'decoded': {
#                'routing': {
#                    'errorReason': 'some made up error',
#                    },
#                },
#            }
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        anode = Node(mo, 'bar', noProto=True)
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.onResponseRequestCannedMessagePluginMessagePart5(packet)
#            assert re.search(r'onResponseRequestCannedMessagePluginMessagePart5', caplog.text, re.MULTILINE)
#        out, err = capsys.readouterr()
#        assert re.search(r'Error on response', out)
#        assert err == ''


# TODO
# @pytest.mark.unit
# def test_onResponseRequestChannel(caplog):
#    """Test onResponseRequestChannel()"""
#
#    channel1 = Channel(index=1, role=1)
#    channel1.settings.modem_config = 3
#    channel1.settings.psk = b'\x01'
#
#    msg1 = MagicMock(autospec=AdminMessage)
#    msg1.get_channel_response = channel1
#
#    msg2 = MagicMock(autospec=AdminMessage)
#    channel2 = Channel(index=2, role=0) # disabled
#    msg2.get_channel_response = channel2
#
#    # default primary channel
#    packet1 = {
#        'from': 2475227164,
#        'to': 2475227164,
#        'decoded': {
#            'portnum': 'ADMIN_APP',
#            'payload': b':\t\x12\x05\x18\x03"\x01\x01\x18\x01',
#            'requestId': 2615094405,
#            'admin': {
#                'getChannelResponse': {
#                    'settings': {
#                        'modemConfig': 'Bw125Cr48Sf4096',
#                        'psk': 'AQ=='
#                    },
#                    'role': 'PRIMARY'
#                },
#                'raw': msg1,
#            }
#        },
#        'id': 1692918436,
#        'hopLimit': 3,
#        'priority':
#        'RELIABLE',
#        'raw': 'fake',
#        'fromId': '!9388f81c',
#        'toId': '!9388f81c'
#        }
#
#    # no other channels
#    packet2 = {
#        'from': 2475227164,
#        'to': 2475227164,
#        'decoded': {
#            'portnum': 'ADMIN_APP',
#            'payload': b':\x04\x08\x02\x12\x00',
#            'requestId': 743049663,
#            'admin': {
#                'getChannelResponse': {
#                    'index': 2,
#                    'settings': {}
#                },
#                'raw': msg2,
#            }
#        },
#        'id': 1692918456,
#        'rxTime': 1640202239,
#        'hopLimit': 3,
#        'priority': 'RELIABLE',
#        'raw': 'faked',
#        'fromId': '!9388f81c',
#        'toId': '!9388f81c'
#    }
#
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        mo.localNode.getChannelByName.return_value = None
#        mo.myInfo.max_channels = 8
#        anode = Node(mo, 'bar', noProto=True)
#
#        radioConfig = RadioConfig()
#        anode.radioConfig = radioConfig
#
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.requestConfig()
#            anode.onResponseRequestChannel(packet1)
#            assert re.search(r'Received channel', caplog.text, re.MULTILINE)
#            anode.onResponseRequestChannel(packet2)
#            assert re.search(r'Received channel', caplog.text, re.MULTILINE)
#            assert re.search(r'Finished downloading channels', caplog.text, re.MULTILINE)
#            assert len(anode.channels) == 8
#            assert anode.channels[0].settings.modem_config == 3
#            assert anode.channels[1].settings.name == ''
#            assert anode.channels[2].settings.name == ''
#            assert anode.channels[3].settings.name == ''
#            assert anode.channels[4].settings.name == ''
#            assert anode.channels[5].settings.name == ''
#            assert anode.channels[6].settings.name == ''
#            assert anode.channels[7].settings.name == ''


# TODO
# @pytest.mark.unit
# def test_onResponseRequestSetting(caplog):
#    """Test onResponseRequestSetting()"""
#    # Note: Split out the get_radio_response to a MagicMock
#    # so it could be "returned" (not really sure how to do that
#    # in a python dict.
#    amsg = MagicMock(autospec=AdminMessage)
#    amsg.get_radio_response = """{
#  preferences {
#    phone_timeout_secs: 900
#    ls_secs: 300
#    position_broadcast_smart: true
#    position_flags: 35
#  }
# }"""
#    packet = {
#        'from': 2475227164,
#        'to': 2475227164,
#        'decoded': {
#            'portnum': 'ADMIN_APP',
#            'payload': b'*\x0e\n\x0c0\x84\x07P\xac\x02\x88\x01\x01\xb0\t#',
#            'requestId': 3145147848,
#            'admin': {
#                'getRadioResponse': {
#                    'preferences': {
#                        'phoneTimeoutSecs': 900,
#                        'lsSecs': 300,
#                        'positionBroadcastSmart': True,
#                        'positionFlags': 35
#                     }
#                },
#                'raw': amsg
#            },
#            'id': 365963704,
#            'rxTime': 1640195197,
#            'hopLimit': 3,
#            'priority': 'RELIABLE',
#            'raw': 'faked',
#            'fromId': '!9388f81c',
#            'toId': '!9388f81c'
#        }
#    }
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        mo.localNode.getChannelByName.return_value = None
#        mo.myInfo.max_channels = 8
#        anode = Node(mo, 'bar', noProto=True)
#
#        radioConfig = RadioConfig()
#        anode.radioConfig = radioConfig
#
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        with caplog.at_level(logging.DEBUG):
#            anode.onResponseRequestSettings(packet)
#            assert re.search(r'Received radio config, now fetching channels..', caplog.text, re.MULTILINE)


# TODO
# @pytest.mark.unit
# def test_onResponseRequestSetting_with_error(capsys):
#    """Test onResponseRequestSetting() with an error"""
#    packet = {
#        'from': 2475227164,
#        'to': 2475227164,
#        'decoded': {
#            'portnum': 'ADMIN_APP',
#            'payload': b'*\x0e\n\x0c0\x84\x07P\xac\x02\x88\x01\x01\xb0\t#',
#            'requestId': 3145147848,
#            'routing': {
#                'errorReason': 'some made up error',
#            },
#            'admin': {
#                'getRadioResponse': {
#                    'preferences': {
#                        'phoneTimeoutSecs': 900,
#                        'lsSecs': 300,
#                        'positionBroadcastSmart': True,
#                        'positionFlags': 35
#                     }
#                },
#            },
#            'id': 365963704,
#            'rxTime': 1640195197,
#            'hopLimit': 3,
#            'priority': 'RELIABLE',
#            'fromId': '!9388f81c',
#            'toId': '!9388f81c'
#        }
#    }
#    iface = MagicMock(autospec=SerialInterface)
#    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
#        mo.localNode.getChannelByName.return_value = None
#        mo.myInfo.max_channels = 8
#        anode = Node(mo, 'bar', noProto=True)
#
#        radioConfig = RadioConfig()
#        anode.radioConfig = radioConfig
#
#        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
#        mo.localNode = anode
#
#        anode.onResponseRequestSettings(packet)
#        out, err = capsys.readouterr()
#        assert re.search(r'Error on response', out)
#        assert err == ''


# TODO
# @pytest.mark.unitslow
# def test_waitForConfig():
#    """Test waitForConfig()"""
#    anode = Node('foo', 'bar')
#    radioConfig = RadioConfig()
#    anode.radioConfig = radioConfig
#    anode._timeout = Timeout(0.01)
#    result = anode.waitForConfig()
#    assert not result
