"""Per-portnum fragmentation: the field codec, splitting a client-owned port, joining what arrives."""

from unittest.mock import MagicMock

import pytest

from meshtastic import fragment
from meshtastic.mesh_interface import MeshInterface
from meshtastic.protobuf import packet_pb2, portnums_pb2, wire_pb2

ATAK = portnums_pb2.PortNum.ATAK_FORWARDER


@pytest.mark.unit
def test_field_packs_msg_id_index_total():
    """msg_id << 6 | index << 3 | total, the order SCHEMA.md and firmware use."""
    assert fragment.pack(0xAB, 2, 3) == (0xAB << 6) | (2 << 3) | 3
    assert fragment.unpack(fragment.pack(0xAB, 2, 3)) == (0xAB, 2, 3)


@pytest.mark.unit
def test_field_rejects_what_no_sender_produces():
    assert fragment.unpack(fragment.pack(1, 0, 0)) is None  # one fragment is no fragmented message
    assert fragment.unpack(fragment.pack(1, 3, 2)) is None  # index above total
    assert fragment.unpack(1 << 14) is None  # wider than the 14-bit field


def _fragment(sender, msg_id, index, total, payload, port=ATAK):
    p = packet_pb2.MeshPacket()
    setattr(p, "from", sender)
    p.decoded.portnum = port
    p.decoded.payload = payload
    p.header_options = wire_pb2.HeaderOptions(fragment=fragment.pack(msg_id, index, total)).SerializeToString()
    return p


@pytest.mark.unit
def test_reassembler_joins_out_of_order_and_keeps_fragment_0_fields():
    r = fragment.Reassembler()
    first = _fragment(7, 5, 0, 2, b"aa")
    first.decoded.reply_id = 99
    assert r.add(_fragment(7, 5, 2, 2, b"cc")) is None
    assert r.add(first) is None
    whole = r.add(_fragment(7, 5, 1, 2, b"bb"))
    assert whole.decoded.payload == b"aabbcc"
    assert whole.decoded.reply_id == 99
    assert not whole.header_options


@pytest.mark.unit
def test_reassembler_keys_on_sender_port_and_msg_id_and_times_out():
    r = fragment.Reassembler(timeout_s=10)
    assert r.add(_fragment(7, 5, 0, 1, b"a"), now=0) is None
    assert r.add(_fragment(8, 5, 1, 1, b"b"), now=1) is None  # another sender's message
    assert r.add(_fragment(7, 5, 1, 1, b"b", port=portnums_pb2.PortNum.LORAWAN_BRIDGE), now=1) is None
    assert r.add(_fragment(7, 5, 1, 1, b"b"), now=20) is None  # the first half timed out
    assert r.add(_fragment(7, 5, 0, 1, b"a"), now=21).decoded.payload == b"ab"


@pytest.mark.unit
def test_reassembler_drops_a_message_whose_total_changes():
    r = fragment.Reassembler()
    assert r.add(_fragment(7, 5, 0, 1, b"a")) is None
    assert r.add(_fragment(7, 5, 1, 2, b"b")) is None
    assert r.add(_fragment(7, 5, 2, 2, b"c")) is None


def _capture(iface):
    sent = []

    def fakeSend(meshPacket, destinationId, **kwargs):
        sent.append(meshPacket)
        return meshPacket

    iface._sendPacket = MagicMock(side_effect=fakeSend)
    return sent


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_send_splits_a_client_owned_port_and_answers_once():
    iface = MeshInterface(noProto=True)
    sent = _capture(iface)
    responses = []
    data = bytes(range(256)) * 2  # 512 bytes: four broadcast fragments
    iface.sendData(data, portNum=ATAK, wantAck=True, onResponse=responses.append)
    assert len(sent) == 4
    fields = [fragment.field_of(p) for p in sent]
    assert [f[1] for f in fields] == [0, 1, 2, 3] and {f[2] for f in fields} == {3} and len({f[0] for f in fields}) == 1
    assert b"".join(p.decoded.payload for p in sent) == data

    for p in sent[:3]:
        iface.responseHandlers.pop(p.id).callback({"decoded": {"requestId": p.id, "routing": {"errorReason": "NONE"}}})
    assert responses == []
    iface.responseHandlers.pop(sent[3].id).callback({"decoded": {"requestId": sent[3].id, "routing": {"errorReason": "NONE"}}})
    assert len(responses) == 1
    iface.close()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_send_refuses_more_fragments_than_the_port_allows_and_leaves_other_ports_alone():
    iface = MeshInterface(noProto=True)
    sent = _capture(iface)
    with pytest.raises(MeshInterface.MeshInterfaceError):
        iface.sendData(bytes(900), portNum=ATAK)
    assert sent == []
    iface.sendData(bytes(200), portNum=portnums_pb2.PortNum.PRIVATE_APP)
    assert len(sent) == 1 and not sent[0].header_options
    iface.close()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_received_fragments_publish_one_whole_packet(monkeypatch):
    iface = MeshInterface(noProto=True)
    published = []
    monkeypatch.setattr("meshtastic.mesh_interface.publishingThread.queueWork", published.append)
    iface._handlePacketFromRadio(_fragment(7, 9, 1, 1, b"world"), hack=True)
    assert published == []
    iface._handlePacketFromRadio(_fragment(7, 9, 0, 1, b"hello "), hack=True)
    assert len(published) == 1
    iface.close()
