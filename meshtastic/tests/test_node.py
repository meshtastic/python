"""Meshtastic unit tests for node.py"""

import re
import logging

from unittest.mock import patch, MagicMock
import pytest

from ..node import Node
from ..serial_interface import SerialInterface
from ..admin_pb2 import AdminMessage
from ..channel_pb2 import Channel
from ..radioconfig_pb2 import RadioConfig


@pytest.mark.unit
def test_node(capsys):
    """Test that we can instantiate a Node"""
    anode = Node('foo', 'bar')
    radioConfig = RadioConfig()
    anode.radioConfig = radioConfig
    anode.showChannels()
    anode.showInfo()
    out, err = capsys.readouterr()
    assert re.search(r'Preferences', out)
    assert re.search(r'Channels', out)
    assert re.search(r'Primary channel URL', out)
    assert err == ''


@pytest.mark.unit
def test_node_reqquestConfig():
    """Test run requestConfig"""
    iface = MagicMock(autospec=SerialInterface)
    amesg = MagicMock(autospec=AdminMessage)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        with patch('meshtastic.admin_pb2.AdminMessage', return_value=amesg):
            anode = Node(mo, 'bar')
            anode.requestConfig()


@pytest.mark.unit
def test_setOwner_and_team(caplog):
    """Test setOwner"""
    anode = Node('foo', 'bar', noProto=True)
    with caplog.at_level(logging.DEBUG):
        anode.setOwner(long_name ='Test123', short_name='123', team=1)
    assert re.search(r'p.set_owner.long_name:Test123:', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.short_name:123:', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.is_licensed:False', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.team:1', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_setOwner_no_short_name(caplog):
    """Test setOwner"""
    anode = Node('foo', 'bar', noProto=True)
    with caplog.at_level(logging.DEBUG):
        anode.setOwner(long_name ='Test123')
    assert re.search(r'p.set_owner.long_name:Test123:', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.short_name:Tst:', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.is_licensed:False', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.team:0', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_setOwner_no_short_name_and_long_name_is_short(caplog):
    """Test setOwner"""
    anode = Node('foo', 'bar', noProto=True)
    with caplog.at_level(logging.DEBUG):
        anode.setOwner(long_name ='Tnt')
    assert re.search(r'p.set_owner.long_name:Tnt:', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.short_name:Tnt:', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.is_licensed:False', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.team:0', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_setOwner_no_short_name_and_long_name_has_words(caplog):
    """Test setOwner"""
    anode = Node('foo', 'bar', noProto=True)
    with caplog.at_level(logging.DEBUG):
        anode.setOwner(long_name ='A B C', is_licensed=True)
    assert re.search(r'p.set_owner.long_name:A B C:', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.short_name:ABC:', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.is_licensed:True', caplog.text, re.MULTILINE)
    assert re.search(r'p.set_owner.team:0', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_exitSimulator(caplog):
    """Test exitSimulator"""
    anode = Node('foo', 'bar', noProto=True)
    with caplog.at_level(logging.DEBUG):
        anode.exitSimulator()
    assert re.search(r'in exitSimulator', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_reboot(caplog):
    """Test reboot"""
    anode = Node('foo', 'bar', noProto=True)
    with caplog.at_level(logging.DEBUG):
        anode.reboot()
    assert re.search(r'Telling node to reboot', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_setURL_empty_url():
    """Test reboot"""
    anode = Node('foo', 'bar', noProto=True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        anode.setURL('')
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


@pytest.mark.unit
def test_setURL_valid_URL(caplog):
    """Test setURL"""
    iface = MagicMock(autospec=SerialInterface)
    url = "https://www.meshtastic.org/d/#CgUYAyIBAQ"
    with caplog.at_level(logging.DEBUG):
        anode = Node(iface, 'bar', noProto=True)
        anode.radioConfig = 'baz'
        channels = ['zoo']
        anode.channels = channels
        anode.setURL(url)
    assert re.search(r'Channel i:0', caplog.text, re.MULTILINE)
    assert re.search(r'modem_config: Bw125Cr48Sf4096', caplog.text, re.MULTILINE)
    assert re.search(r'psk: "\\001"', caplog.text, re.MULTILINE)
    assert re.search(r'role: PRIMARY', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_setURL_valid_URL_but_no_settings(caplog):
    """Test setURL"""
    iface = MagicMock(autospec=SerialInterface)
    url = "https://www.meshtastic.org/d/#"
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        anode = Node(iface, 'bar', noProto=True)
        anode.radioConfig = 'baz'
        anode.setURL(url)
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


@pytest.mark.unit
def test_showChannels(capsys):
    """Test showChannels"""
    anode = Node('foo', 'bar')

    # primary channel
    # role: 0=Disabled, 1=Primary, 2=Secondary
    # modem_config: 0-5
    # role: 0=Disabled, 1=Primary, 2=Secondary
    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    channel1.settings.psk = b'\x01'

    channel2 = Channel(index=2, role=2)
    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
    channel2.settings.name = 'testing'

    channel3 = Channel(index=3, role=0)
    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]

    anode.channels = channels
    anode.showChannels()
    out, err = capsys.readouterr()
    assert re.search(r'Channels:', out, re.MULTILINE)
    # primary channel
    assert re.search(r'Primary channel URL', out, re.MULTILINE)
    assert re.search(r'PRIMARY psk=default ', out, re.MULTILINE)
    assert re.search(r'"modemConfig": "Bw125Cr48Sf4096"', out, re.MULTILINE)
    assert re.search(r'"psk": "AQ=="', out, re.MULTILINE)
    # secondary channel
    assert re.search(r'SECONDARY psk=secret ', out, re.MULTILINE)
    assert re.search(r'"psk": "ipR5DsbJHjWREkCmMKi0M4cA8ksO539Bes31sJAwqDQ="', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
def test_deleteChannel_try_to_delete_primary_channel(capsys):
    """Try to delete primary channel."""
    anode = Node('foo', 'bar')

    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    channel1.settings.psk = b'\x01'

    # no secondary channels
    channel2 = Channel(index=2, role=0)
    channel3 = Channel(index=3, role=0)
    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]

    anode.channels = channels
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        anode.deleteChannel(0)
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.search(r'Warning: Only SECONDARY channels can be deleted', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
def test_deleteChannel_secondary():
    """Try to delete a secondary channel."""

    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    channel1.settings.psk = b'\x01'

    channel2 = Channel(index=2, role=2)
    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
    channel2.settings.name = 'testing'

    channel3 = Channel(index=3, role=0)
    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]


    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        mo.localNode.getChannelByName.return_value = None
        mo.myInfo.max_channels = 8
        anode = Node(mo, 'bar', noProto=True)

        anode.channels = channels
        assert len(anode.channels) == 8
        assert channels[0].settings.modem_config == 3
        assert channels[1].settings.name == 'testing'
        assert channels[2].settings.name == ''
        assert channels[3].settings.name == ''
        assert channels[4].settings.name == ''
        assert channels[5].settings.name == ''
        assert channels[6].settings.name == ''
        assert channels[7].settings.name == ''

        anode.deleteChannel(1)

        assert len(anode.channels) == 8
        assert channels[0].settings.modem_config == 3
        assert channels[1].settings.name == ''
        assert channels[2].settings.name == ''
        assert channels[3].settings.name == ''
        assert channels[4].settings.name == ''
        assert channels[5].settings.name == ''
        assert channels[6].settings.name == ''
        assert channels[7].settings.name == ''


@pytest.mark.unit
def test_deleteChannel_secondary_with_admin_channel_after_testing():
    """Try to delete a secondary channel where there is an admin channel."""

    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    channel1.settings.psk = b'\x01'

    channel2 = Channel(index=2, role=2)
    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
    channel2.settings.name = 'testing'

    channel3 = Channel(index=3, role=2)
    channel3.settings.name = 'admin'

    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]


    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        mo.localNode.getChannelByName.return_value = None
        mo.myInfo.max_channels = 8
        anode = Node(mo, 'bar', noProto=True)

        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
        mo.localNode = anode

        assert mo.localNode == anode

        anode.channels = channels
        assert len(anode.channels) == 8
        assert channels[0].settings.modem_config == 3
        assert channels[1].settings.name == 'testing'
        assert channels[2].settings.name == 'admin'
        assert channels[3].settings.name == ''
        assert channels[4].settings.name == ''
        assert channels[5].settings.name == ''
        assert channels[6].settings.name == ''
        assert channels[7].settings.name == ''

        anode.deleteChannel(1)

        assert len(anode.channels) == 8
        assert channels[0].settings.modem_config == 3
        assert channels[1].settings.name == 'admin'
        assert channels[2].settings.name == ''
        assert channels[3].settings.name == ''
        assert channels[4].settings.name == ''
        assert channels[5].settings.name == ''
        assert channels[6].settings.name == ''
        assert channels[7].settings.name == ''


@pytest.mark.unit
def test_deleteChannel_secondary_with_admin_channel_before_testing():
    """Try to delete a secondary channel where there is an admin channel."""

    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    channel1.settings.psk = b'\x01'

    channel2 = Channel(index=2, role=2)
    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
    channel2.settings.name = 'admin'

    channel3 = Channel(index=3, role=2)
    channel3.settings.name = 'testing'

    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]


    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        mo.localNode.getChannelByName.return_value = None
        mo.myInfo.max_channels = 8
        anode = Node(mo, 'bar', noProto=True)

        anode.channels = channels
        assert len(anode.channels) == 8
        assert channels[0].settings.modem_config == 3
        assert channels[1].settings.name == 'admin'
        assert channels[2].settings.name == 'testing'
        assert channels[3].settings.name == ''
        assert channels[4].settings.name == ''
        assert channels[5].settings.name == ''
        assert channels[6].settings.name == ''
        assert channels[7].settings.name == ''

        anode.deleteChannel(2)

        assert len(anode.channels) == 8
        assert channels[0].settings.modem_config == 3
        assert channels[1].settings.name == 'admin'
        assert channels[2].settings.name == ''
        assert channels[3].settings.name == ''
        assert channels[4].settings.name == ''
        assert channels[5].settings.name == ''
        assert channels[6].settings.name == ''
        assert channels[7].settings.name == ''


@pytest.mark.unit
def test_getChannelByName(capsys):
    """Get a channel by the name."""
    anode = Node('foo', 'bar')

    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    channel1.settings.psk = b'\x01'

    channel2 = Channel(index=2, role=2)
    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
    channel2.settings.name = 'admin'

    channel3 = Channel(index=3, role=0)
    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]

    anode.channels = channels
    ch = anode.getChannelByName('admin')
    assert ch.index == 2


@pytest.mark.unit
def test_getChannelByName_invalid_name(capsys):
    """Get a channel by the name but one that is not present."""
    anode = Node('foo', 'bar')

    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    channel1.settings.psk = b'\x01'

    channel2 = Channel(index=2, role=2)
    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
    channel2.settings.name = 'admin'

    channel3 = Channel(index=3, role=0)
    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]

    anode.channels = channels
    ch = anode.getChannelByName('testing')
    assert ch is None


@pytest.mark.unit
def test_getDisabledChannel(capsys):
    """Get the first disabled channel."""
    anode = Node('foo', 'bar')

    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    channel1.settings.psk = b'\x01'

    channel2 = Channel(index=2, role=2)
    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
    channel2.settings.name = 'testingA'

    channel3 = Channel(index=3, role=2)
    channel3.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
    channel3.settings.name = 'testingB'

    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]

    anode.channels = channels
    ch = anode.getDisabledChannel()
    assert ch.index == 4


@pytest.mark.unit
def test_getDisabledChannel_where_all_channels_are_used(capsys):
    """Get the first disabled channel."""
    anode = Node('foo', 'bar')

    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    channel1.settings.psk = b'\x01'

    channel2 = Channel(index=2, role=2)
    channel3 = Channel(index=3, role=2)
    channel4 = Channel(index=4, role=2)
    channel5 = Channel(index=5, role=2)
    channel6 = Channel(index=6, role=2)
    channel7 = Channel(index=7, role=2)
    channel8 = Channel(index=8, role=2)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]

    anode.channels = channels
    ch = anode.getDisabledChannel()
    assert ch is None


@pytest.mark.unit
def test_getAdminChannelIndex(capsys):
    """Get the 'admin' channel index."""
    anode = Node('foo', 'bar')

    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    channel1.settings.psk = b'\x01'

    channel2 = Channel(index=2, role=2)
    channel2.settings.psk = b'\x8a\x94y\x0e\xc6\xc9\x1e5\x91\x12@\xa60\xa8\xb43\x87\x00\xf2K\x0e\xe7\x7fAz\xcd\xf5\xb0\x900\xa84'
    channel2.settings.name = 'admin'

    channel3 = Channel(index=3, role=0)
    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]

    anode.channels = channels
    i = anode._getAdminChannelIndex()
    assert i == 2


@pytest.mark.unit
def test_getAdminChannelIndex_when_no_admin_named_channel(capsys):
    """Get the 'admin' channel when there is not one."""
    anode = Node('foo', 'bar')

    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    channel1.settings.psk = b'\x01'

    channel2 = Channel(index=2, role=0)
    channel3 = Channel(index=3, role=0)
    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]

    anode.channels = channels
    i = anode._getAdminChannelIndex()
    assert i == 0


# TODO: should we check if we need to turn it off?
@pytest.mark.unit
def test_turnOffEncryptionOnPrimaryChannel(capsys):
    """Turn off encryption when there is a psk."""
    anode = Node('foo', 'bar', noProto=True)

    channel1 = Channel(index=1, role=1)
    channel1.settings.modem_config = 3
    # value from using "--ch-set psk 0x1a1a1a1a2b2b2b2b1a1a1a1a2b2b2b2b1a1a1a1a2b2b2b2b1a1a1a1a2b2b2b2b "
    channel1.settings.psk = b'\x1a\x1a\x1a\x1a++++\x1a\x1a\x1a\x1a++++\x1a\x1a\x1a\x1a++++\x1a\x1a\x1a\x1a++++'

    channel2 = Channel(index=2, role=0)
    channel3 = Channel(index=3, role=0)
    channel4 = Channel(index=4, role=0)
    channel5 = Channel(index=5, role=0)
    channel6 = Channel(index=6, role=0)
    channel7 = Channel(index=7, role=0)
    channel8 = Channel(index=8, role=0)

    channels = [ channel1, channel2, channel3, channel4, channel5, channel6, channel7, channel8 ]

    anode.channels = channels
    anode.turnOffEncryptionOnPrimaryChannel()
    out, err = capsys.readouterr()
    assert re.search(r'Writing modified channels to device', out)
    assert err == ''


@pytest.mark.unit
def test_writeConfig_with_no_radioConfig(capsys):
    """Test writeConfig with no radioConfig."""
    anode = Node('foo', 'bar', noProto=True)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        anode.writeConfig()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.search(r'Error: No RadioConfig has been read', out)
    assert err == ''


@pytest.mark.unit
def test_writeConfig(caplog):
    """Test writeConfig"""
    anode = Node('foo', 'bar', noProto=True)
    radioConfig = RadioConfig()
    anode.radioConfig = radioConfig

    with caplog.at_level(logging.DEBUG):
        anode.writeConfig()
    assert re.search(r'Wrote config', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_requestChannel_not_localNode(caplog):
    """Test _requestChannel()"""
    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        mo.localNode.getChannelByName.return_value = None
        mo.myInfo.max_channels = 8
        anode = Node(mo, 'bar', noProto=True)
        with caplog.at_level(logging.DEBUG):
            anode._requestChannel(0)
            assert re.search(r'Requesting channel 0 info from remote node', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_requestChannel_localNode(caplog):
    """Test _requestChannel()"""
    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        mo.localNode.getChannelByName.return_value = None
        mo.myInfo.max_channels = 8
        anode = Node(mo, 'bar', noProto=True)

        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
        mo.localNode = anode

        with caplog.at_level(logging.DEBUG):
            anode._requestChannel(0)
            assert re.search(r'Requesting channel 0', caplog.text, re.MULTILINE)
            assert not re.search(r'from remote node', caplog.text, re.MULTILINE)


# TODO:
#@pytest.mark.unit
#def test_onResponseRequestChannel(caplog):
#    """Test onResponseRequestChannel()"""
#    anode = Node('foo', 'bar')
#    radioConfig = RadioConfig()
#    anode.radioConfig = radioConfig


@pytest.mark.unit
def test_onResponseRequestSetting(caplog):
    """Test onResponseRequestSetting()"""
    # Note: Split out the get_radio_response to a MagicMock
    # so it could be "returned" (not really sure how to do that
    # in a python dict.
    amsg = MagicMock(autospec=AdminMessage)
    amsg.get_radio_response = """{
  preferences {
    phone_timeout_secs: 900
    ls_secs: 300
    position_broadcast_smart: true
    position_flags: 35
  }
}"""
    # TODO: not sure if this tmpraw is formatted correctly
    tmpraw = """from: 2475227164
to: 2475227164
decoded {
  portnum: ADMIN_APP
  payload: "*\016\n\0140\204\007P\254\002\210\001\001\260\t#"
  request_id: 3145147848
}
id: 365963704
rx_time: 1640195197
hop_limit: 3
priority: RELIABLE"""

    packet = {
        'from': 2475227164,
        'to': 2475227164,
        'decoded': {
            'portnum': 'ADMIN_APP',
            'payload': b'*\x0e\n\x0c0\x84\x07P\xac\x02\x88\x01\x01\xb0\t#',
            'requestId': 3145147848,
            'admin': {
                'getRadioResponse': {
                    'preferences': {
                        'phoneTimeoutSecs': 900,
                        'lsSecs': 300,
                        'positionBroadcastSmart': True,
                        'positionFlags': 35
                     }
                },
                'raw': amsg
            },
            'id': 365963704,
            'rxTime': 1640195197,
            'hopLimit': 3,
            'priority': 'RELIABLE',
            'raw': tmpraw,
            'fromId': '!9388f81c',
            'toId': '!9388f81c'
        }
    }
    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        mo.localNode.getChannelByName.return_value = None
        mo.myInfo.max_channels = 8
        anode = Node(mo, 'bar', noProto=True)

        radioConfig = RadioConfig()
        anode.radioConfig = radioConfig

        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
        mo.localNode = anode

        with caplog.at_level(logging.DEBUG):
            anode.onResponseRequestSettings(packet)
            assert re.search(r'Received radio config, now fetching channels..', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_onResponseRequestSetting_with_error(capsys):
    """Test onResponseRequestSetting() with an error"""
    packet = {
        'from': 2475227164,
        'to': 2475227164,
        'decoded': {
            'portnum': 'ADMIN_APP',
            'payload': b'*\x0e\n\x0c0\x84\x07P\xac\x02\x88\x01\x01\xb0\t#',
            'requestId': 3145147848,
            'routing': {
                'errorReason': 'some made up error',
            },
            'admin': {
                'getRadioResponse': {
                    'preferences': {
                        'phoneTimeoutSecs': 900,
                        'lsSecs': 300,
                        'positionBroadcastSmart': True,
                        'positionFlags': 35
                     }
                },
            },
            'id': 365963704,
            'rxTime': 1640195197,
            'hopLimit': 3,
            'priority': 'RELIABLE',
            'fromId': '!9388f81c',
            'toId': '!9388f81c'
        }
    }
    iface = MagicMock(autospec=SerialInterface)
    with patch('meshtastic.serial_interface.SerialInterface', return_value=iface) as mo:
        mo.localNode.getChannelByName.return_value = None
        mo.myInfo.max_channels = 8
        anode = Node(mo, 'bar', noProto=True)

        radioConfig = RadioConfig()
        anode.radioConfig = radioConfig

        # Note: Have to do this next line because every call to MagicMock object/method returns a new magic mock
        mo.localNode = anode

        anode.onResponseRequestSettings(packet)
        out, err = capsys.readouterr()
        assert re.search(r'Error on response', out)
        assert err == ''
