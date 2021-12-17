"""Meshtastic unit tests for node.py"""

import re
import logging

from unittest.mock import patch, MagicMock
import pytest

from ..node import Node
from ..serial_interface import SerialInterface
from ..admin_pb2 import AdminMessage


@pytest.mark.unit
def test_node(capsys):
    """Test that we can instantiate a Node"""
    anode = Node('foo', 'bar')
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
