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
