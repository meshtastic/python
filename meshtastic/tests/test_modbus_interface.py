"""Meshtastic unit tests for modbus_interface.py"""

import re
import sys
from unittest.mock import MagicMock, patch

import pytest

from .. import mt_config
from ..__main__ import main
from ..mesh_interface import MeshInterface
from ..modbus_interface import (
    FC_READ,
    FC_WRITE,
    MAX_DATA,
    RETRIES,
    ModbusInterface,
    crc16,
    parseModbusSpec,
    withCrc,
)


class FakeNode:
    """Stands in for the RS485 adapter and answers tunnel requests like the firmware does"""

    def __init__(self, output: bytes = b"", silent: int = 0, answer=None):
        self.output = output  # API bytes the node has queued for the host
        self.received = b""  # API bytes the node accepted
        self.silent = silent  # requests to ignore, as after a collision on the bus
        self.answer = answer  # fixed answer bytes, overriding the node logic
        self.requests: list = []
        self._reply = b""

    def reset_input_buffer(self):
        """Drop anything not yet read"""
        self._reply = b""

    def flush(self):
        """Nothing buffered"""

    def close(self):
        """Nothing to release"""

    def write(self, req):
        """Take one request and prepare the node's answer"""
        req = bytes(req)
        self.requests.append(req)
        assert crc16(req[:-2]) == req[-2] | req[-1] << 8
        if self.silent:
            self.silent -= 1
            return len(req)
        if self.answer is not None:
            self._reply = self.answer
            return len(req)
        fc, seq = req[1], req[2]
        if fc == FC_WRITE:
            self.received += req[4:-2]
            self._reply = withCrc(bytes((req[0], fc, seq, req[3])))
        else:
            chunk, self.output = self.output[:MAX_DATA], self.output[MAX_DATA:]
            self._reply = withCrc(bytes((req[0], fc, seq, len(chunk))) + chunk)
        return len(req)

    def read(self, n):
        """Return up to n bytes of the prepared answer"""
        out, self._reply = self._reply[:n], self._reply[n:]
        return out


def makeInterface(node: FakeNode) -> ModbusInterface:
    """A ModbusInterface wired to a fake node instead of a serial port"""
    iface = ModbusInterface("COM5", noProto=True, connectNow=False)
    iface.stream = node  # type: ignore[assignment]
    return iface


@pytest.mark.unit
@pytest.mark.parametrize(
    "frame",
    [
        "01 04 00 00 00 02 71 CB",
        "01 84 04 42 C3",
        "F0 42 00 41 53",
        "F0 42 00 00 93 30",
        "F0 42 01 80 93",
        "F0 41 05 06 94 C3 00 02 18 01 DD 6D",
        "F0 41 05 06 E0 62",
        "F0 C1 01 E1 A3",
    ],
)
def test_crc16_matches_firmware_vectors(frame):
    """The CRCs agree with the frames the firmware's tests pin"""
    f = bytes.fromhex(frame)
    assert withCrc(f[:-2]) == f


@pytest.mark.unit
def test_parseModbusSpec():
    """DEVICE[:ADDR[:BAUD]] with the tunnel defaults filled in"""
    assert parseModbusSpec("COM5") == ("COM5", 240, 9600)
    assert parseModbusSpec("/dev/ttyUSB0:10") == ("/dev/ttyUSB0", 10, 9600)
    assert parseModbusSpec("COM5::19200") == ("COM5", 240, 19200)
    assert parseModbusSpec("COM5:241:19200") == ("COM5", 241, 19200)
    for bad in ["", ":240", "COM5:0", "COM5:248", "COM5:1:2:3", "COM5:x"]:
        with pytest.raises(ValueError):
            parseModbusSpec(bad)


@pytest.mark.unit
def test_ModbusInterface_without_connecting():
    """Constructing with connectNow=False opens nothing"""
    iface = ModbusInterface("COM5", address=10, noProto=True, connectNow=False)
    assert iface.stream is None
    assert repr(iface) == "ModbusInterface(devPath='COM5', address=10, noProto=True)"


@pytest.mark.unit
def test_write_frame_matches_firmware_vector():
    """A framed ToRadio{want_config_id: 1} goes out exactly as the firmware's test expects it"""
    node = FakeNode()
    iface = makeInterface(node)
    iface._seq = 4
    iface._writeBytes(bytes.fromhex("94 C3 00 02 18 01"))
    assert node.requests == [bytes.fromhex("F0 41 05 06 94 C3 00 02 18 01 DD 6D")]
    assert node.received == bytes.fromhex("94 C3 00 02 18 01")


@pytest.mark.unit
def test_writeBytes_splits_into_tunnel_frames():
    """Data longer than one frame is sent in 240-byte slices, each acknowledged"""
    node = FakeNode()
    iface = makeInterface(node)
    data = bytes(range(256)) * 2
    iface._writeBytes(data)
    assert [r[3] for r in node.requests] == [240, 240, 32]
    assert node.received == data


@pytest.mark.unit
def test_readBytes_delivers_output_and_polls_again_after_full_read():
    """A full read is followed by another one straight away; an empty one waits for the poll interval"""
    output = bytes(range(250)) * 2
    node = FakeNode(output=output)
    iface = makeInterface(node)
    got = b""
    with patch("meshtastic.modbus_interface.time.monotonic", return_value=1000.0), patch("time.sleep") as mock_sleep:
        while len(got) < len(output):
            got += iface._readBytes(1)
        mock_sleep.assert_not_called()
        assert got == output
        assert len(node.requests) == 3  # 240 + 240 + 20
        assert iface._readBytes(1) == b""
        mock_sleep.assert_called_once()
        assert len(node.requests) == 3


@pytest.mark.unit
def test_retry_repeats_the_same_request():
    """An unanswered request is resent unchanged, so the node can recognise the retry"""
    node = FakeNode(output=b"abc", silent=1)
    iface = makeInterface(node)
    with patch("time.sleep"):
        assert iface._transact(FC_READ) == b"abc"
    assert len(node.requests) == 2
    assert node.requests[0] == node.requests[1]


@pytest.mark.unit
def test_unreachable_after_retries():
    """Silence on every attempt raises once the retries are used up"""
    node = FakeNode(silent=100)
    iface = makeInterface(node)
    with patch("time.sleep"), pytest.raises(MeshInterface.MeshInterfaceError, match="No answer"):
        iface._writeBytes(b"x")
    assert len(node.requests) == 1 + RETRIES


@pytest.mark.unit
def test_answer_to_another_request_is_ignored():
    """An answer with a stale sequence number or a bad CRC counts as no answer"""
    stale = withCrc(bytes((240, FC_READ, 0x77, 0)))
    node = FakeNode(answer=stale)
    iface = makeInterface(node)
    iface._seq = 0x10
    with patch("time.sleep"), pytest.raises(MeshInterface.MeshInterfaceError, match="No answer"):
        iface._transact(FC_READ)

    damaged = bytearray(withCrc(bytes((240, FC_READ, 0x11, 1, 0x55))))
    damaged[4] ^= 0xFF
    node = FakeNode(answer=bytes(damaged))
    iface = makeInterface(node)
    iface._seq = 0x10
    with patch("time.sleep"), pytest.raises(MeshInterface.MeshInterfaceError, match="No answer"):
        iface._transact(FC_READ)


@pytest.mark.unit
def test_exception_answer_raises_without_retry():
    """A node that rejects the function code says so; retrying would not help"""
    node = FakeNode(answer=bytes.fromhex("F0 C1 01 E1 A3"))
    iface = makeInterface(node)
    with pytest.raises(MeshInterface.MeshInterfaceError, match="rejected"):
        iface._writeBytes(b"x")
    assert len(node.requests) == 1


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_main_info_with_modbus_interface(capsys):
    """--modbus DEVICE:ADDR:BAUD connects through ModbusInterface"""
    sys.argv = ["", "--info", "--modbus", "COM5:241:19200"]
    mt_config.args = sys.argv

    iface = MagicMock(autospec=ModbusInterface)

    def mock_showInfo():
        print("inside mocked showInfo")

    iface.showInfo.side_effect = mock_showInfo
    with patch("meshtastic.modbus_interface.ModbusInterface", return_value=iface) as mo:
        main()
        out, err = capsys.readouterr()
        assert re.search(r"Connected to radio", out, re.MULTILINE)
        assert re.search(r"inside mocked showInfo", out, re.MULTILINE)
        assert err == ""
        assert mo.call_args.args == ("COM5",)
        assert mo.call_args.kwargs["address"] == 241
        assert mo.call_args.kwargs["baudrate"] == 19200
