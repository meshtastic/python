"""Meshtastic unit tests for util.py"""

import json
import logging
import re
from unittest.mock import patch

import pytest
from hypothesis import given, strategies as st

from meshtastic.supported_device import SupportedDevice
from meshtastic.protobuf import mesh_pb2
from meshtastic.util import (
    Timeout,
    active_ports_on_supported_devices,
    camel_to_snake,
    catchAndIgnore,
    convert_mac_addr,
    eliminate_duplicate_port,
    findPorts,
    fixme,
    fromPSK,
    fromStr,
    genPSK256,
    hexstr,
    ipstr,
    is_windows11,
    our_exit,
    pskToString,
    quoteBooleans,
    readnet_u16,
    remove_keys_from_dict,
    snake_to_camel,
    stripnl,
    support_info,
    message_to_json,
    Acknowledgment
)


@pytest.mark.unit
def test_genPSK256():
    """Test genPSK256"""
    assert genPSK256() != ""


@pytest.mark.unit
def test_fromStr():
    """Test fromStr"""
    assert fromStr("") == b""
    assert fromStr("0x12") == b"\x12"
    assert fromStr("t")
    assert fromStr("T")
    assert fromStr("true")
    assert fromStr("True")
    assert fromStr("yes")
    assert fromStr("Yes")
    assert fromStr("f") is False
    assert fromStr("F") is False
    assert fromStr("false") is False
    assert fromStr("False") is False
    assert fromStr("no") is False
    assert fromStr("No") is False
    assert fromStr("100.01") == 100.01
    assert fromStr("123") == 123
    assert fromStr("abc") == "abc"
    assert fromStr("123456789") == 123456789
    assert fromStr("base64:Zm9vIGJhciBiYXo=") == b"foo bar baz"


@pytest.mark.unitslow
def test_quoteBooleans():
    """Test quoteBooleans"""
    assert quoteBooleans("") == ""
    assert quoteBooleans("foo") == "foo"
    assert quoteBooleans("true") == "true"
    assert quoteBooleans("false") == "false"
    assert quoteBooleans(": true") == ": 'true'"
    assert quoteBooleans(": false") == ": 'false'"


@pytest.mark.unit
def test_fromPSK():
    """Test fromPSK"""
    assert fromPSK("random") != ""
    assert fromPSK("none") == b"\x00"
    assert fromPSK("default") == b"\x01"
    assert fromPSK("simple22") == b"\x17"
    assert fromPSK("trash") == "trash"


@pytest.mark.unit
def test_stripnl():
    """Test stripnl"""
    assert stripnl("") == ""
    assert stripnl("a\n") == "a"
    assert stripnl(" a \n ") == "a"
    assert stripnl("a\nb") == "a b"


@pytest.mark.unit
def test_pskToString_empty_string():
    """Test pskToString empty string"""
    assert pskToString("") == "unencrypted"


@pytest.mark.unit
def test_pskToString_string():
    """Test pskToString string"""
    assert pskToString("hunter123") == "secret"


@pytest.mark.unit
def test_pskToString_one_byte_zero_value():
    """Test pskToString one byte that is value of 0"""
    assert pskToString(bytes([0x00])) == "unencrypted"


@pytest.mark.unitslow
def test_pskToString_one_byte_non_zero_value():
    """Test pskToString one byte that is non-zero"""
    assert pskToString(bytes([0x01])) == "default"


@pytest.mark.unitslow
def test_pskToString_many_bytes():
    """Test pskToString many bytes"""
    assert pskToString(bytes([0x02, 0x01])) == "secret"


@pytest.mark.unit
def test_pskToString_simple():
    """Test pskToString simple"""
    assert pskToString(bytes([0x03])) == "simple2"


@pytest.mark.unitslow
def test_our_exit_zero_return_value(capsys):
    """Test our_exit with a zero return value"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        our_exit("Warning: Some message", 0)
    out, err = capsys.readouterr()
    assert re.search(r"Warning: Some message", out, re.MULTILINE)
    assert err == ""
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 0


@pytest.mark.unitslow
def test_our_exit_non_zero_return_value(capsys):
    """Test our_exit with a non-zero return value"""
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        our_exit("Error: Some message", 1)
    out, err = capsys.readouterr()
    assert re.search(r"Error: Some message", out, re.MULTILINE)
    assert err == ""
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


@pytest.mark.unitslow
def test_fixme():
    """Test fixme()"""
    with pytest.raises(Exception) as pytest_wrapped_e:
        fixme("some exception")
    assert pytest_wrapped_e.type == Exception


@pytest.mark.unit
def test_support_info(capsys):
    """Test support_info"""
    support_info()
    out, err = capsys.readouterr()
    assert re.search(r"System", out, re.MULTILINE)
    assert re.search(r"Platform", out, re.MULTILINE)
    assert re.search(r"Machine", out, re.MULTILINE)
    assert re.search(r"Executable", out, re.MULTILINE)
    assert err == ""


@pytest.mark.unit
def test_catchAndIgnore(caplog):
    """Test catchAndIgnore() does not actually throw an exception, but just logs"""

    def some_closure():
        raise Exception("foo") # pylint: disable=W0719

    with caplog.at_level(logging.DEBUG):
        catchAndIgnore("something", some_closure)
    assert re.search(r"Exception thrown in something", caplog.text, re.MULTILINE)


@pytest.mark.unitslow
def test_remove_keys_from_dict_empty_keys_empty_dict():
    """Test when keys and dict both are empty"""
    assert not remove_keys_from_dict((), {})


@pytest.mark.unitslow
def test_remove_keys_from_dict_empty_dict():
    """Test when dict is empty"""
    assert not remove_keys_from_dict(("a"), {})


@pytest.mark.unit
def test_remove_keys_from_dict_empty_keys():
    """Test when keys is empty"""
    assert remove_keys_from_dict((), {"a": 1}) == {"a": 1}


@pytest.mark.unitslow
def test_remove_keys_from_dict():
    """Test remove_keys_from_dict()"""
    assert remove_keys_from_dict(("b"), {"a": 1, "b": 2}) == {"a": 1}


@pytest.mark.unitslow
def test_remove_keys_from_dict_multiple_keys():
    """Test remove_keys_from_dict()"""
    keys = ("a", "b")
    adict = {"a": 1, "b": 2, "c": 3}
    assert remove_keys_from_dict(keys, adict) == {"c": 3}


@pytest.mark.unit
def test_remove_keys_from_dict_nested():
    """Test remove_keys_from_dict()"""
    keys = "b"
    adict = {"a": {"b": 1}, "b": 2, "c": 3}
    exp = {"a": {}, "c": 3}
    assert remove_keys_from_dict(keys, adict) == exp


@pytest.mark.unitslow
def test_Timeout_not_found():
    """Test Timeout()"""
    to = Timeout(0.2)
    attrs = "foo"
    to.waitForSet("bar", attrs)


@pytest.mark.unitslow
def test_Timeout_found():
    """Test Timeout()"""
    to = Timeout(0.2)
    attrs = ()
    to.waitForSet("bar", attrs)


@pytest.mark.unitslow
def test_hexstr():
    """Test hexstr()"""
    assert hexstr(b"123") == "31:32:33"
    assert hexstr(b"") == ""


@pytest.mark.unitslow
def test_ipstr():
    """Test ipstr()"""
    assert ipstr(b"1234") == "49.50.51.52"
    assert ipstr(b"") == ""


@pytest.mark.unitslow
def test_readnet_u16():
    """Test readnet_u16()"""
    assert readnet_u16(b"123456", 2) == 13108


@pytest.mark.unitslow
@patch("serial.tools.list_ports.comports", return_value=[])
def test_findPorts_when_none_found(patch_comports):
    """Test findPorts()"""
    assert not findPorts()
    patch_comports.assert_called()


@pytest.mark.unitslow
@patch("serial.tools.list_ports.comports")
def test_findPorts_when_duplicate_found_and_duplicate_option_used(patch_comports):
    """Test findPorts()"""

    class TempPort:
        """temp class for port"""

        def __init__(self, device=None, vid=None):
            self.device = device
            self.vid = vid

    fake1 = TempPort("/dev/cu.usbserial-1430", vid="fake1")
    fake2 = TempPort("/dev/cu.wchusbserial1430", vid="fake2")
    patch_comports.return_value = [fake1, fake2]
    assert findPorts(eliminate_duplicates=True) == ["/dev/cu.wchusbserial1430"]
    patch_comports.assert_called()


@pytest.mark.unitslow
@patch("serial.tools.list_ports.comports")
def test_findPorts_when_duplicate_found_and_duplicate_option_used_ports_reversed(
    patch_comports,
):
    """Test findPorts()"""

    class TempPort:
        """temp class for port"""

        def __init__(self, device=None, vid=None):
            self.device = device
            self.vid = vid

    fake1 = TempPort("/dev/cu.usbserial-1430", vid="fake1")
    fake2 = TempPort("/dev/cu.wchusbserial1430", vid="fake2")
    patch_comports.return_value = [fake2, fake1]
    assert findPorts(eliminate_duplicates=True) == ["/dev/cu.wchusbserial1430"]
    patch_comports.assert_called()


@pytest.mark.unitslow
@patch("serial.tools.list_ports.comports")
def test_findPorts_when_duplicate_found_and_duplicate_option_not_used(patch_comports):
    """Test findPorts()"""

    class TempPort:
        """temp class for port"""

        def __init__(self, device=None, vid=None):
            self.device = device
            self.vid = vid

    fake1 = TempPort("/dev/cu.usbserial-1430", vid="fake1")
    fake2 = TempPort("/dev/cu.wchusbserial1430", vid="fake2")
    patch_comports.return_value = [fake1, fake2]
    assert findPorts() == ["/dev/cu.usbserial-1430", "/dev/cu.wchusbserial1430"]
    patch_comports.assert_called()


@pytest.mark.unitslow
def test_convert_mac_addr():
    """Test convert_mac_addr()"""
    assert convert_mac_addr("/c0gFyhb") == "fd:cd:20:17:28:5b"
    assert convert_mac_addr("fd:cd:20:17:28:5b") == "fd:cd:20:17:28:5b"
    assert convert_mac_addr("") == ""


@pytest.mark.unit
def test_snake_to_camel():
    """Test snake_to_camel"""
    assert snake_to_camel("") == ""
    assert snake_to_camel("foo") == "foo"
    assert snake_to_camel("foo_bar") == "fooBar"
    assert snake_to_camel("fooBar") == "fooBar"


@pytest.mark.unit
def test_camel_to_snake():
    """Test camel_to_snake"""
    assert camel_to_snake("") == ""
    assert camel_to_snake("foo") == "foo"
    assert camel_to_snake("Foo") == "foo"
    assert camel_to_snake("fooBar") == "foo_bar"
    assert camel_to_snake("fooBarBaz") == "foo_bar_baz"


@pytest.mark.unit
def test_eliminate_duplicate_port():
    """Test eliminate_duplicate_port()"""
    assert not eliminate_duplicate_port([])
    assert eliminate_duplicate_port(["/dev/fake"]) == ["/dev/fake"]
    assert eliminate_duplicate_port(["/dev/fake", "/dev/fake1"]) == [
        "/dev/fake",
        "/dev/fake1",
    ]
    assert eliminate_duplicate_port(["/dev/fake", "/dev/fake1", "/dev/fake2"]) == [
        "/dev/fake",
        "/dev/fake1",
        "/dev/fake2",
    ]
    assert eliminate_duplicate_port(
        ["/dev/cu.usbserial-1430", "/dev/cu.wchusbserial1430"]
    ) == ["/dev/cu.wchusbserial1430"]
    assert eliminate_duplicate_port(
        ["/dev/cu.wchusbserial1430", "/dev/cu.usbserial-1430"]
    ) == ["/dev/cu.wchusbserial1430"]
    assert eliminate_duplicate_port(
        ["/dev/cu.SLAB_USBtoUART", "/dev/cu.usbserial-0001"]
    ) == ["/dev/cu.usbserial-0001"]
    assert eliminate_duplicate_port(
        ["/dev/cu.usbserial-0001", "/dev/cu.SLAB_USBtoUART"]
    ) == ["/dev/cu.usbserial-0001"]
    assert eliminate_duplicate_port(
        ["/dev/cu.usbmodem11301", "/dev/cu.wchusbserial11301"]
    ) == ["/dev/cu.wchusbserial11301"]
    assert eliminate_duplicate_port(
        ["/dev/cu.wchusbserial11301", "/dev/cu.usbmodem11301"]
    ) == ["/dev/cu.wchusbserial11301"]
    assert eliminate_duplicate_port(
        ["/dev/cu.usbmodem53230051441", "/dev/cu.wchusbserial53230051441"]
    ) == ["/dev/cu.wchusbserial53230051441"]
    assert eliminate_duplicate_port(
        ["/dev/cu.wchusbserial53230051441", "/dev/cu.usbmodem53230051441"]
    ) == ["/dev/cu.wchusbserial53230051441"]


@patch("platform.version", return_value="10.0.22000.194")
@patch("platform.release", return_value="10")
@patch("platform.system", return_value="Windows")
def test_is_windows11_true(patched_platform, patched_release, patched_version):
    """Test is_windows11()"""
    assert is_windows11() is True
    patched_platform.assert_called()
    patched_release.assert_called()
    patched_version.assert_called()


@patch("platform.version", return_value="10.0.a2200.foo")  # made up
@patch("platform.release", return_value="10")
@patch("platform.system", return_value="Windows")
def test_is_windows11_true2(patched_platform, patched_release, patched_version):
    """Test is_windows11()"""
    assert is_windows11() is False
    patched_platform.assert_called()
    patched_release.assert_called()
    patched_version.assert_called()


@patch("platform.version", return_value="10.0.17763")  # windows 10 home
@patch("platform.release", return_value="10")
@patch("platform.system", return_value="Windows")
def test_is_windows11_false(patched_platform, patched_release, patched_version):
    """Test is_windows11()"""
    assert is_windows11() is False
    patched_platform.assert_called()
    patched_release.assert_called()
    patched_version.assert_called()


@patch("platform.release", return_value="8.1")
@patch("platform.system", return_value="Windows")
def test_is_windows11_false_win8_1(patched_platform, patched_release):
    """Test is_windows11()"""
    assert is_windows11() is False
    patched_platform.assert_called()
    patched_release.assert_called()


@pytest.mark.unit
@patch("platform.system", return_value="Linux")
def test_active_ports_on_supported_devices_empty(mock_platform):
    """Test active_ports_on_supported_devices()"""
    sds = set()
    assert active_ports_on_supported_devices(sds) == set()
    mock_platform.assert_called()


@pytest.mark.unit
@patch("subprocess.getstatusoutput")
@patch("platform.system", return_value="Linux")
def test_active_ports_on_supported_devices_linux(mock_platform, mock_sp):
    """Test active_ports_on_supported_devices()"""
    mock_sp.return_value = (
        None,
        "crw-rw-rw-  1 root        wheel   0x9000000 Feb  8 22:22 /dev/ttyUSBfake",
    )
    fake_device = SupportedDevice(
        name="a", for_firmware="heltec-v2.1", baseport_on_linux="ttyUSB"
    )
    fake_supported_devices = [fake_device]
    assert active_ports_on_supported_devices(fake_supported_devices) == {
        "/dev/ttyUSBfake"
    }
    mock_platform.assert_called()
    mock_sp.assert_called()


@pytest.mark.unit
@patch("subprocess.getstatusoutput")
@patch("platform.system", return_value="Darwin")
def test_active_ports_on_supported_devices_mac(mock_platform, mock_sp):
    """Test active_ports_on_supported_devices()"""
    mock_sp.return_value = (
        None,
        "crw-rw-rw-  1 root        wheel   0x9000000 Feb  8 22:22 /dev/cu.usbserial-foo",
    )
    fake_device = SupportedDevice(
        name="a", for_firmware="heltec-v2.1", baseport_on_linux="cu.usbserial-"
    )
    fake_supported_devices = [fake_device]
    assert active_ports_on_supported_devices(fake_supported_devices) == {
        "/dev/cu.usbserial-foo"
    }
    mock_platform.assert_called()
    mock_sp.assert_called()


@pytest.mark.unit
@patch("meshtastic.util.detect_windows_port", return_value={"COM2"})
@patch("platform.system", return_value="Windows")
def test_active_ports_on_supported_devices_win(mock_platform, mock_dwp):
    """Test active_ports_on_supported_devices()"""
    fake_device = SupportedDevice(name="a", for_firmware="heltec-v2.1")
    fake_supported_devices = [fake_device]
    assert active_ports_on_supported_devices(fake_supported_devices) == {"COM2"}
    mock_platform.assert_called()
    mock_dwp.assert_called()


@pytest.mark.unit
@patch("subprocess.getstatusoutput")
@patch("platform.system", return_value="Darwin")
def test_active_ports_on_supported_devices_mac_no_duplicates_check(
    mock_platform, mock_sp
):
    """Test active_ports_on_supported_devices()"""
    mock_sp.return_value = (
        None,
        (
            "crw-rw-rw-  1 root  wheel  0x9000005 Mar  8 10:05 /dev/cu.usbmodem53230051441\n"
            "crw-rw-rw-  1 root  wheel  0x9000003 Mar  8 10:06 /dev/cu.wchusbserial53230051441"
        ),
    )
    fake_device = SupportedDevice(
        name="a", for_firmware="tbeam", baseport_on_mac="cu.usbmodem"
    )
    fake_supported_devices = [fake_device]
    assert active_ports_on_supported_devices(fake_supported_devices, False) == {
        "/dev/cu.usbmodem53230051441",
        "/dev/cu.wchusbserial53230051441",
    }
    mock_platform.assert_called()
    mock_sp.assert_called()


@pytest.mark.unit
@patch("subprocess.getstatusoutput")
@patch("platform.system", return_value="Darwin")
def test_active_ports_on_supported_devices_mac_duplicates_check(mock_platform, mock_sp):
    """Test active_ports_on_supported_devices()"""
    mock_sp.return_value = (
        None,
        (
            "crw-rw-rw-  1 root  wheel  0x9000005 Mar  8 10:05 /dev/cu.usbmodem53230051441\n"
            "crw-rw-rw-  1 root  wheel  0x9000003 Mar  8 10:06 /dev/cu.wchusbserial53230051441"
        ),
    )
    fake_device = SupportedDevice(
        name="a", for_firmware="tbeam", baseport_on_mac="cu.usbmodem"
    )
    fake_supported_devices = [fake_device]
    assert active_ports_on_supported_devices(fake_supported_devices, True) == {
        "/dev/cu.wchusbserial53230051441"
    }
    mock_platform.assert_called()
    mock_sp.assert_called()

@pytest.mark.unit
def test_message_to_json_shows_all():
    """Test that message_to_json prints fields that aren't included in data passed in"""
    actual = json.loads(message_to_json(mesh_pb2.MyNodeInfo()))
    expected = { "myNodeNum": 0, "rebootCount": 0, "minAppVersion": 0 }
    assert actual == expected

@pytest.mark.unit
def test_acknowledgement_reset():
    """
    Test that the reset method can set all fields back to False
    """
    test_ack_obj = Acknowledgment()
    # everything's set to False; let's set it to True to get a good test
    test_ack_obj.receivedAck = True
    test_ack_obj.receivedNak = True
    test_ack_obj.receivedImplAck = True
    test_ack_obj.receivedTraceRoute = True
    test_ack_obj.receivedTelemetry = True
    test_ack_obj.receivedPosition = True
    test_ack_obj.reset()
    assert test_ack_obj.receivedAck is False
    assert test_ack_obj.receivedNak is False
    assert test_ack_obj.receivedImplAck is False
    assert test_ack_obj.receivedTraceRoute is False
    assert test_ack_obj.receivedTelemetry is False
    assert test_ack_obj.receivedPosition is False

@given(a_string=st.text(
    alphabet=st.characters(
        codec='ascii',
        min_codepoint=0x5F,
        max_codepoint=0x7A,
        exclude_characters=r'`',
    )).filter(
        lambda x: x not in [''] and x[0] not in "_" and x[-1] not in '_' and not re.search(r'__', x)
    ))
def test_roundtrip_snake_to_camel_camel_to_snake(a_string):
    """Test that snake_to_camel and camel_to_snake roundtrip each other"""
    value0 = snake_to_camel(a_string=a_string)
    value1 = camel_to_snake(a_string=value0)
    assert a_string == value1, (a_string, value1)
