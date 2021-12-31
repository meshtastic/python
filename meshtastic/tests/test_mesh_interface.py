"""Meshtastic unit tests for mesh_interface.py"""

import re
import logging

from unittest.mock import patch, MagicMock
import pytest

from ..mesh_interface import MeshInterface
from ..node import Node
from .. import mesh_pb2
from ..__init__ import LOCAL_ADDR, BROADCAST_ADDR


@pytest.mark.unit
def test_MeshInterface(capsys, reset_globals):
    """Test that we can instantiate a MeshInterface"""
    iface = MeshInterface(noProto=True)
    anode = Node('foo', 'bar')

    nodes = {
        '!9388f81c': {
            'num': 2475227164,
            'user': {
                'id': '!9388f81c',
                'longName': 'Unknown f81c',
                'shortName': '?1C',
                'macaddr': 'RBeTiPgc',
                'hwModel': 'TBEAM'
            },
            'position': {},
            'lastHeard': 1640204888
        }
    }

    iface.nodesByNum = {1: anode }
    iface.nodes = nodes

    myInfo = MagicMock()
    iface.myInfo = myInfo

    iface.showInfo()
    iface.localNode.showInfo()
    iface.showNodes()
    iface.sendText('hello')
    iface.close()
    out, err = capsys.readouterr()
    assert re.search(r'Owner: None \(None\)', out, re.MULTILINE)
    assert re.search(r'Nodes', out, re.MULTILINE)
    assert re.search(r'Preferences', out, re.MULTILINE)
    assert re.search(r'Channels', out, re.MULTILINE)
    assert re.search(r'Primary channel URL', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
def test_getMyUser(reset_globals, iface_with_nodes):
    """Test getMyUser()"""
    iface = iface_with_nodes

    iface.myInfo.my_node_num = 2475227164
    myuser = iface.getMyUser()
    assert myuser is not None
    assert myuser["id"] == '!9388f81c'


@pytest.mark.unit
def test_getLongName(reset_globals, iface_with_nodes):
    """Test getLongName()"""
    iface = iface_with_nodes
    iface.myInfo.my_node_num = 2475227164
    mylongname = iface.getLongName()
    assert mylongname == 'Unknown f81c'


@pytest.mark.unit
def test_getShortName(reset_globals, iface_with_nodes):
    """Test getShortName()."""
    iface = iface_with_nodes
    iface.myInfo.my_node_num = 2475227164
    myshortname = iface.getShortName()
    assert myshortname == '?1C'


@pytest.mark.unit
def test_handlePacketFromRadio_no_from(capsys, reset_globals):
    """Test _handlePacketFromRadio with no 'from' in the mesh packet."""
    iface = MeshInterface(noProto=True)
    meshPacket = mesh_pb2.MeshPacket()
    iface._handlePacketFromRadio(meshPacket)
    out, err = capsys.readouterr()
    assert re.search(r'Device returned a packet we sent, ignoring', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
def test_handlePacketFromRadio_with_a_portnum(caplog, reset_globals):
    """Test _handlePacketFromRadio with a portnum
       Since we have an attribute called 'from', we cannot simply 'set' it.
       Had to implement a hack just to be able to test some code.
    """
    iface = MeshInterface(noProto=True)
    meshPacket = mesh_pb2.MeshPacket()
    meshPacket.decoded.payload = b''
    meshPacket.decoded.portnum = 1
    with caplog.at_level(logging.WARNING):
        iface._handlePacketFromRadio(meshPacket, hack=True)
    assert re.search(r'Not populating fromId', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_handlePacketFromRadio_no_portnum(caplog, reset_globals):
    """Test _handlePacketFromRadio without a portnum"""
    iface = MeshInterface(noProto=True)
    meshPacket = mesh_pb2.MeshPacket()
    meshPacket.decoded.payload = b''
    with caplog.at_level(logging.WARNING):
        iface._handlePacketFromRadio(meshPacket, hack=True)
    assert re.search(r'Not populating fromId', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_getNode_with_local(reset_globals):
    """Test getNode"""
    iface = MeshInterface(noProto=True)
    anode = iface.getNode(LOCAL_ADDR)
    assert anode == iface.localNode


@pytest.mark.unit
def test_getNode_not_local(reset_globals, caplog):
    """Test getNode not local"""
    iface = MeshInterface(noProto=True)
    anode = MagicMock(autospec=Node)
    with caplog.at_level(logging.DEBUG):
        with patch('meshtastic.node.Node', return_value=anode):
            another_node = iface.getNode('bar2')
            assert another_node != iface.localNode
    assert re.search(r'About to requestConfig', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_getNode_not_local_timeout(reset_globals, capsys):
    """Test getNode not local, simulate timeout"""
    iface = MeshInterface(noProto=True)
    anode = MagicMock(autospec=Node)
    anode.waitForConfig.return_value = False
    with patch('meshtastic.node.Node', return_value=anode):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            iface.getNode('bar2')
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1
        out, err = capsys.readouterr()
        assert re.match(r'Error: Timed out waiting for node config', out)
        assert err == ''


@pytest.mark.unit
def test_sendPosition(reset_globals, caplog):
    """Test sendPosition"""
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface.sendPosition()
    iface.close()
    assert re.search(r'p.time:', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_handleFromRadio_empty_payload(reset_globals, caplog):
    """Test _handleFromRadio"""
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface._handleFromRadio(b'')
    iface.close()
    assert re.search(r'Unexpected FromRadio payload', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_handleFromRadio_with_my_info(reset_globals, caplog):
    """Test _handleFromRadio with my_info"""
    # Note: I captured the '--debug --info' for the bytes below.
    # It "translates" to this:
    # my_info {
    #  my_node_num: 682584012
    #  num_bands: 13
    #  firmware_version: "1.2.49.5354c49"
    #  reboot_count: 13
    #  bitrate: 17.088470458984375
    #  message_timeout_msec: 300000
    #  min_app_version: 20200
    #  max_channels: 8
    # }
    from_radio_bytes = b'\x1a,\x08\xcc\xcf\xbd\xc5\x02\x18\r2\x0e1.2.49.5354c49P\r]0\xb5\x88Ah\xe0\xa7\x12p\xe8\x9d\x01x\x08\x90\x01\x01'
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface._handleFromRadio(from_radio_bytes)
    iface.close()
    assert re.search(r'Received myinfo', caplog.text, re.MULTILINE)
    assert re.search(r'num_bands: 13', caplog.text, re.MULTILINE)
    assert re.search(r'max_channels: 8', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_handleFromRadio_with_node_info(reset_globals, caplog, capsys):
    """Test _handleFromRadio with node_info"""
    # Note: I captured the '--debug --info' for the bytes below.
    # It "translates" to this:
    # node_info {
    #  num: 682584012
    #  user {
    #    id: "!28af67cc"
    #    long_name: "Unknown 67cc"
    #    short_name: "?CC"
    #    macaddr: "$o(\257g\314"
    #    hw_model: HELTEC_V2_1
    #  }
    #  position {
    #    }
    #  }

    from_radio_bytes = b'"2\x08\xcc\xcf\xbd\xc5\x02\x12(\n\t!28af67cc\x12\x0cUnknown 67cc\x1a\x03?CC"\x06$o(\xafg\xcc0\n\x1a\x00'
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface._startConfig()
        iface._handleFromRadio(from_radio_bytes)
        assert re.search(r'Received nodeinfo', caplog.text, re.MULTILINE)
        assert re.search(r'682584012', caplog.text, re.MULTILINE)
        assert re.search(r'HELTEC_V2_1', caplog.text, re.MULTILINE)
        # validate some of showNodes() output
        iface.showNodes()
        out, err = capsys.readouterr()
        assert re.search(r' 1 ', out, re.MULTILINE)
        assert re.search(r'│ Unknown 67cc │ ', out, re.MULTILINE)
        assert re.search(r'│ !28af67cc │ N/A   │ N/A         │ N/A', out, re.MULTILINE)
        assert err == ''
        iface.close()


@pytest.mark.unit
def test_handleFromRadio_with_node_info_tbeam1(reset_globals, caplog, capsys):
    """Test _handleFromRadio with node_info"""
    # Note: Captured the '--debug --info' for the bytes below.
    # pylint: disable=C0301
    from_radio_bytes = b'"=\x08\x80\xf8\xc8\xf6\x07\x12"\n\t!7ed23c00\x12\x07TBeam 1\x1a\x02T1"\x06\x94\xb9~\xd2<\x000\x04\x1a\x07 ]MN\x01\xbea%\xad\x01\xbea=\x00\x00,A'
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface._startConfig()
        iface._handleFromRadio(from_radio_bytes)
        assert re.search(r'Received nodeinfo', caplog.text, re.MULTILINE)
        assert re.search(r'TBeam 1', caplog.text, re.MULTILINE)
        assert re.search(r'2127707136', caplog.text, re.MULTILINE)
        # validate some of showNodes() output
        iface.showNodes()
        out, err = capsys.readouterr()
        assert re.search(r' 1 ', out, re.MULTILINE)
        assert re.search(r'│ TBeam 1 │ ', out, re.MULTILINE)
        assert re.search(r'│ !7ed23c00 │', out, re.MULTILINE)
        assert err == ''
        iface.close()


@pytest.mark.unit
def test_handleFromRadio_with_node_info_tbeam_with_bad_data(reset_globals, caplog, capsys):
    """Test _handleFromRadio with node_info with some bad data (issue#172) - ensure we do not throw exception"""
    # Note: Captured the '--debug --info' for the bytes below.
    from_radio_bytes = b'"\x17\x08\xdc\x8a\x8a\xae\x02\x12\x08"\x06\x00\x00\x00\x00\x00\x00\x1a\x00=\x00\x00\xb8@'
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface._startConfig()
        iface._handleFromRadio(from_radio_bytes)


@pytest.mark.unit
def test_MeshInterface_sendToRadioImpl(caplog, reset_globals):
    """Test _sendToRadioImp()"""
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface._sendToRadioImpl('foo')
    assert re.search(r'Subclass must provide toradio', caplog.text, re.MULTILINE)
    iface.close()


@pytest.mark.unit
def test_MeshInterface_sendToRadio_no_proto(caplog, reset_globals):
    """Test sendToRadio()"""
    iface = MeshInterface()
    with caplog.at_level(logging.DEBUG):
        iface._sendToRadioImpl('foo')
    assert re.search(r'Subclass must provide toradio', caplog.text, re.MULTILINE)
    iface.close()


@pytest.mark.unit
def test_sendData_too_long(caplog, reset_globals):
    """Test when data payload is too big"""
    iface = MeshInterface(noProto=True)
    some_large_text = b'This is a long text that will be too long for send text.'
    some_large_text += b'This is a long text that will be too long for send text.'
    some_large_text += b'This is a long text that will be too long for send text.'
    some_large_text += b'This is a long text that will be too long for send text.'
    some_large_text += b'This is a long text that will be too long for send text.'
    some_large_text += b'This is a long text that will be too long for send text.'
    some_large_text += b'This is a long text that will be too long for send text.'
    some_large_text += b'This is a long text that will be too long for send text.'
    some_large_text += b'This is a long text that will be too long for send text.'
    some_large_text += b'This is a long text that will be too long for send text.'
    some_large_text += b'This is a long text that will be too long for send text.'
    some_large_text += b'This is a long text that will be too long for send text.'
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(Exception) as pytest_wrapped_e:
            iface.sendData(some_large_text)
            assert re.search('Data payload too big', caplog.text, re.MULTILINE)
        assert pytest_wrapped_e.type == Exception
    iface.close()


@pytest.mark.unit
def test_sendData_unknown_app(capsys, reset_globals):
    """Test sendData when unknown app"""
    iface = MeshInterface(noProto=True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        iface.sendData(b'hello', portNum=0)
    out, err = capsys.readouterr()
    assert re.search(r'Warning: A non-zero port number', out, re.MULTILINE)
    assert err == ''
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


@pytest.mark.unit
def test_sendPosition_with_a_position(caplog, reset_globals):
    """Test sendPosition when lat/long/alt"""
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        iface.sendPosition(latitude=40.8, longitude=-111.86, altitude=201)
        assert re.search(r'p.latitude_i:408', caplog.text, re.MULTILINE)
        assert re.search(r'p.longitude_i:-11186', caplog.text, re.MULTILINE)
        assert re.search(r'p.altitude:201', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_sendPacket_with_no_destination(capsys, reset_globals):
    """Test _sendPacket()"""
    iface = MeshInterface(noProto=True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        iface._sendPacket(b'', destinationId=None)
    out, err = capsys.readouterr()
    assert re.search(r'Warning: destinationId must not be None', out, re.MULTILINE)
    assert err == ''
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


@pytest.mark.unit
def test_sendPacket_with_destination_as_int(caplog, reset_globals):
    """Test _sendPacket() with int as a destination"""
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        meshPacket = mesh_pb2.MeshPacket()
        iface._sendPacket(meshPacket, destinationId=123)
        assert re.search(r'Not sending packet', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_sendPacket_with_destination_starting_with_a_bang(caplog, reset_globals):
    """Test _sendPacket() with int as a destination"""
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        meshPacket = mesh_pb2.MeshPacket()
        iface._sendPacket(meshPacket, destinationId='!1234')
        assert re.search(r'Not sending packet', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_sendPacket_with_destination_as_BROADCAST_ADDR(caplog, reset_globals):
    """Test _sendPacket() with BROADCAST_ADDR as a destination"""
    iface = MeshInterface(noProto=True)
    with caplog.at_level(logging.DEBUG):
        meshPacket = mesh_pb2.MeshPacket()
        iface._sendPacket(meshPacket, destinationId=BROADCAST_ADDR)
        assert re.search(r'Not sending packet', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_sendPacket_with_destination_as_LOCAL_ADDR_no_myInfo(capsys, reset_globals):
    """Test _sendPacket() with LOCAL_ADDR as a destination with no myInfo"""
    iface = MeshInterface(noProto=True)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        meshPacket = mesh_pb2.MeshPacket()
        iface._sendPacket(meshPacket, destinationId=LOCAL_ADDR)
    out, err = capsys.readouterr()
    assert re.search(r'Warning: No myInfo', out, re.MULTILINE)
    assert err == ''
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


@pytest.mark.unit
def test_sendPacket_with_destination_as_LOCAL_ADDR_with_myInfo(caplog, reset_globals):
    """Test _sendPacket() with LOCAL_ADDR as a destination with myInfo"""
    iface = MeshInterface(noProto=True)
    myInfo = MagicMock()
    iface.myInfo = myInfo
    with caplog.at_level(logging.DEBUG):
        meshPacket = mesh_pb2.MeshPacket()
        iface._sendPacket(meshPacket, destinationId=LOCAL_ADDR)
        assert re.search(r'Not sending packet', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_sendPacket_with_destination_is_blank_with_nodes(capsys, reset_globals, iface_with_nodes):
    """Test _sendPacket() with '' as a destination with myInfo"""
    iface = iface_with_nodes
    meshPacket = mesh_pb2.MeshPacket()
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        iface._sendPacket(meshPacket, destinationId='')
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    out, err = capsys.readouterr()
    assert re.match(r'Warning: NodeId  not found in DB', out, re.MULTILINE)
    assert err == ''


@pytest.mark.unit
def test_sendPacket_with_destination_is_blank_without_nodes(caplog, reset_globals, iface_with_nodes):
    """Test _sendPacket() with '' as a destination with myInfo"""
    iface = iface_with_nodes
    iface.nodes = None
    meshPacket = mesh_pb2.MeshPacket()
    with caplog.at_level(logging.WARNING):
        iface._sendPacket(meshPacket, destinationId='')
    assert re.search(r'Warning: There were no self.nodes.', caplog.text, re.MULTILINE)


@pytest.mark.unit
def test_getMyNodeInfo(reset_globals):
    """Test getMyNodeInfo()"""
    iface = MeshInterface(noProto=True)
    anode = iface.getNode(LOCAL_ADDR)
    iface.nodesByNum = {1: anode }
    assert iface.nodesByNum.get(1) == anode
    myInfo = MagicMock()
    iface.myInfo = myInfo
    iface.myInfo.my_node_num = 1
    myinfo = iface.getMyNodeInfo()
    assert myinfo == anode


@pytest.mark.unit
def test_generatePacketId(capsys, reset_globals):
    """Test _generatePacketId() when no currentPacketId (not connected)"""
    iface = MeshInterface(noProto=True)
    # not sure when this condition would ever happen... but we can simulate it
    iface.currentPacketId = None
    assert iface.currentPacketId is None
    with pytest.raises(Exception) as pytest_wrapped_e:
        iface._generatePacketId()
        out, err = capsys.readouterr()
        assert re.search(r'Not connected yet, can not generate packet', out, re.MULTILINE)
        assert err == ''
    assert pytest_wrapped_e.type == Exception
