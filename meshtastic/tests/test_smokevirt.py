"""Meshtastic smoke tests with a single virtual device via localhost.

   During the CI build of the Meshtastic-device, a build.zip file is created.
   Inside that build.zip is a standalone executable meshtasticd_linux_amd64.
   That linux executable will simulate a Meshtastic device listening on localhost.

   This smoke test runs against that localhost.

"""
import os
import platform
import re
import subprocess
import time

# Do not like using hard coded sleeps, but it probably makes
# sense to pause for the radio at apprpriate times
import pytest

from ..util import findPorts

# seconds to pause after running a meshtastic command
PAUSE_AFTER_COMMAND = 0.1
PAUSE_AFTER_REBOOT = 0.2


# TODO: need to fix the virtual device to have a reboot. When you issue the command
#      below, you get "FIXME implement reboot for this platform"
# @pytest.mark.smokevirt
# def test_smokevirt_reboot():
#    """Test reboot"""
#    return_value, _ = subprocess.getstatusoutput('meshtastic --host localhost --reboot')
#    assert return_value == 0
#    # pause for the radio to reset
#    time.sleep(8)


@pytest.mark.smokevirt
def test_smokevirt_info():
    """Test --info"""
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Owner", out, re.MULTILINE)
    assert re.search(r"^My info", out, re.MULTILINE)
    assert re.search(r"^Nodes in mesh", out, re.MULTILINE)
    assert re.search(r"^Preferences", out, re.MULTILINE)
    assert re.search(r"^Channels", out, re.MULTILINE)
    assert re.search(r"^  PRIMARY", out, re.MULTILINE)
    assert re.search(r"^Primary channel URL", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_sendping():
    """Test --sendping"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --sendping"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Sending ping message", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_get_with_invalid_setting():
    """Test '--get a_bad_setting'."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --get a_bad_setting"
    )
    assert re.search(r"Choices in sorted order", out)
    assert return_value == 0


@pytest.mark.smokevirt
def test_set_with_invalid_setting():
    """Test '--set a_bad_setting'."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --set a_bad_setting foo"
    )
    assert re.search(r"Choices in sorted order", out)
    assert return_value == 0


@pytest.mark.smokevirt
def test_ch_set_with_invalid_settingpatch_find_ports():
    """Test '--ch-set with a_bad_setting'."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-set invalid_setting foo --ch-index 0"
    )
    assert re.search(r"Choices in sorted order", out)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_pos_fields():
    """Test --pos-fields (with some values POS_ALTITUDE POS_ALT_MSL POS_BATTERY)"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --pos-fields POS_ALTITUDE POS_ALT_MSL POS_BATTERY"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Setting position fields to 35", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --pos-fields"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"POS_ALTITUDE", out, re.MULTILINE)
    assert re.search(r"POS_ALT_MSL", out, re.MULTILINE)
    assert re.search(r"POS_BATTERY", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_test_with_arg_but_no_hardware():
    """Test --test
    Note: Since only one device is connected, it will not do much.
    """
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --test")
    assert re.search(r"^Warning: Must have at least two devices", out, re.MULTILINE)
    assert return_value == 1


@pytest.mark.smokevirt
def test_smokevirt_debug():
    """Test --debug"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --info --debug"
    )
    assert re.search(r"^Owner", out, re.MULTILINE)
    assert re.search(r"^DEBUG file", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_seriallog_to_file():
    """Test --seriallog to a file creates a file"""
    filename = "tmpoutput.txt"
    if os.path.exists(f"{filename}"):
        os.remove(f"{filename}")
    return_value, _ = subprocess.getstatusoutput(
        f"meshtastic --host localhost --info --seriallog {filename}"
    )
    assert os.path.exists(f"{filename}")
    assert return_value == 0
    os.remove(f"{filename}")


@pytest.mark.smokevirt
def test_smokevirt_qr():
    """Test --qr"""
    filename = "tmpqr"
    if os.path.exists(f"{filename}"):
        os.remove(f"{filename}")
    return_value, _ = subprocess.getstatusoutput(
        f"meshtastic --host localhost --qr > {filename}"
    )
    assert os.path.exists(f"{filename}")
    # not really testing that a valid qr code is created, just that the file size
    # is reasonably big enough for a qr code
    assert os.stat(f"{filename}").st_size > 20000
    assert return_value == 0
    os.remove(f"{filename}")


@pytest.mark.smokevirt
def test_smokevirt_nodes():
    """Test --nodes"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --nodes"
    )
    assert re.match(r"Connected to radio", out)
    if platform.system() != "Windows":
        assert re.search(r" User ", out, re.MULTILINE)
        assert re.search(r"  1 ", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_send_hello():
    """Test --sendtext hello"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --sendtext hello"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Sending text message hello to \^all", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_port():
    """Test --port"""
    # first, get the ports
    ports = findPorts()
    # hopefully there is none
    assert len(ports) == 0


@pytest.mark.smokevirt
def test_smokevirt_set_location_info():
    """Test --setlat, --setlon and --setalt"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --setlat 32.7767 --setlon -96.7970 --setalt 1337"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Fixing altitude", out, re.MULTILINE)
    assert re.search(r"^Fixing latitude", out, re.MULTILINE)
    assert re.search(r"^Fixing longitude", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out2 = subprocess.getstatusoutput(
        "meshtastic --host localhost --info"
    )
    assert re.search(r"1337", out2, re.MULTILINE)
    assert re.search(r"32.7767", out2, re.MULTILINE)
    assert re.search(r"-96.797", out2, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_set_owner():
    """Test --set-owner name"""
    # make sure the owner is not Joe
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --set-owner Bob"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Setting device owner to Bob", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert not re.search(r"Owner: Joe", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --set-owner Joe"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Setting device owner to Joe", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.search(r"Owner: Joe", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_ch_values():
    """Test --ch-longslow, --ch-longfast, --ch-mediumslow, --ch-mediumsfast,
    --ch-shortslow, and --ch-shortfast arguments
    """
    exp = {
        "--ch-longslow": "LongSlow",
        "--ch-longfast": "LongFast",
        "--ch-medslow": "MedSlow",
        "--ch-medfast": "MedFast",
        "--ch-shortslow": "ShortSlow",
        "--ch-shortfast": "ShortFast",
    }

    for key, val in exp.items():
        return_value, out = subprocess.getstatusoutput(
            f"meshtastic --host localhost {key}"
        )
        assert re.match(r"Connected to radio", out)
        assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
        assert return_value == 0
        # pause for the radio (might reboot)
        time.sleep(PAUSE_AFTER_REBOOT)
        return_value, out = subprocess.getstatusoutput(
            "meshtastic --host localhost --info"
        )
        assert re.search(val, out, re.MULTILINE)
        assert return_value == 0
        # pause for the radio
        time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smokevirt
def test_smokevirt_ch_set_name():
    """Test --ch-set name"""
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert not re.search(r"MyChannel", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-set name MyChannel"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"Warning: Need to specify", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-set name MyChannel --ch-index 0"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Set name to MyChannel", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.search(r"MyChannel", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_ch_set_downlink_and_uplink():
    """Test -ch-set downlink_enabled X and --ch-set uplink_enabled X"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-set downlink_enabled false --ch-set uplink_enabled false"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"Warning: Need to specify", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    # pylint: disable=C0301
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-set downlink_enabled false --ch-set uplink_enabled false --ch-index 0"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert not re.search(r"uplinkEnabled", out, re.MULTILINE)
    assert not re.search(r"downlinkEnabled", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    # pylint: disable=C0301
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-set downlink_enabled true --ch-set uplink_enabled true --ch-index 0"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Set downlink_enabled to true", out, re.MULTILINE)
    assert re.search(r"^Set uplink_enabled to true", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.search(r"uplinkEnabled", out, re.MULTILINE)
    assert re.search(r"downlinkEnabled", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_ch_add_and_ch_del():
    """Test --ch-add"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-index 1 --ch-del"
    )
    assert re.search(r"Deleting channel 1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-add testing"
    )
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-index 1 --ch-del"
    )
    assert re.search(r"Deleting channel 1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    # make sure the secondary channel is not there
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert not re.search(r"SECONDARY", out, re.MULTILINE)
    assert not re.search(r"testing", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_ch_enable_and_disable():
    """Test --ch-enable and --ch-disable"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-index 1 --ch-del"
    )
    assert re.search(r"Deleting channel 1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-add testing"
    )
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    # ensure they need to specify a --ch-index
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-disable"
    )
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-disable --ch-index 1"
    )
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"DISABLED", out, re.MULTILINE)
    assert re.search(r"testing", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-enable --ch-index 1"
    )
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-del --ch-index 1"
    )
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smokevirt
def test_smokevirt_ch_del_a_disabled_non_primary_channel():
    """Test --ch-del will work on a disabled non-primary channel."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-index 1 --ch-del"
    )
    assert re.search(r"Deleting channel 1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-add testing"
    )
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    # ensure they need to specify a --ch-index
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-disable"
    )
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-del --ch-index 1"
    )
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert not re.search(r"DISABLED", out, re.MULTILINE)
    assert not re.search(r"SECONDARY", out, re.MULTILINE)
    assert not re.search(r"testing", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smokevirt
def test_smokevirt_attempt_to_delete_primary_channel():
    """Test that we cannot delete the PRIMARY channel."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-del --ch-index 0"
    )
    assert re.search(r"Warning: Cannot delete primary channel", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smokevirt
def test_smokevirt_attempt_to_disable_primary_channel():
    """Test that we cannot disable the PRIMARY channel."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-disable --ch-index 0"
    )
    assert re.search(r"Warning: Cannot enable", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smokevirt
def test_smokevirt_attempt_to_enable_primary_channel():
    """Test that we cannot enable the PRIMARY channel."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-enable --ch-index 0"
    )
    assert re.search(r"Warning: Cannot enable", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smokevirt
def test_smokevirt_ensure_ch_del_second_of_three_channels():
    """Test that when we delete the 2nd of 3 channels, that it deletes the correct channel."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-add testing1"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-add testing2"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"testing2", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-del --ch-index 1"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"testing2", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-del --ch-index 1"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smokevirt
def test_smokevirt_ensure_ch_del_third_of_three_channels():
    """Test that when we delete the 3rd of 3 channels, that it deletes the correct channel."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-add testing1"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-add testing2"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"testing2", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-del --ch-index 2"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"testing1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-del --ch-index 1"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smokevirt
def test_smokevirt_ch_set_modem_config():
    """Test --ch-set modem_config"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-set modem_config Bw31_25Cr48Sf512"
    )
    assert re.search(r"Warning: Need to specify", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert not re.search(r"Bw31_25Cr48Sf512", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-set modem_config MidSlow --ch-index 0"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Set modem_config to MidSlow", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.search(r"MidSlow", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_seturl_default():
    """Test --seturl with default value"""
    # set some channel value so we no longer have a default channel
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --ch-set name foo --ch-index 0"
    )
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    # ensure we no longer have a default primary channel
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert not re.search("CgUYAyIBAQ", out, re.MULTILINE)
    assert return_value == 0
    url = "https://www.meshtastic.org/d/#CgUYAyIBAQ"
    return_value, out = subprocess.getstatusoutput(
        f"meshtastic --host localhost --seturl {url}"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.search("CgUYAyIBAQ", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_seturl_invalid_url():
    """Test --seturl with invalid url"""
    # Note: This url is no longer a valid url.
    url = "https://www.meshtastic.org/c/#GAMiENTxuzogKQdZ8Lz_q89Oab8qB0RlZmF1bHQ="
    return_value, out = subprocess.getstatusoutput(
        f"meshtastic --host localhost --seturl {url}"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search("Warning: There were no settings", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smokevirt
def test_smokevirt_configure():
    """Test --configure"""
    _, out = subprocess.getstatusoutput(
        f"meshtastic --host localhost --configure example_config.yaml"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search("^Setting device owner to Bob TBeam", out, re.MULTILINE)
    assert re.search("^Fixing altitude at 304 meters", out, re.MULTILINE)
    assert re.search("^Fixing latitude at 35.8", out, re.MULTILINE)
    assert re.search("^Fixing longitude at -93.8", out, re.MULTILINE)
    assert re.search("^Setting device position", out, re.MULTILINE)
    assert re.search("^Set region to 1", out, re.MULTILINE)
    assert re.search("^Set is_always_powered to true", out, re.MULTILINE)
    assert re.search("^Set send_owner_interval to 2", out, re.MULTILINE)
    assert re.search("^Set screen_on_secs to 31536000", out, re.MULTILINE)
    assert re.search("^Set wait_bluetooth_secs to 31536000", out, re.MULTILINE)
    assert re.search("^Writing modified preferences to device", out, re.MULTILINE)
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)


@pytest.mark.smokevirt
def test_smokevirt_set_ham():
    """Test --set-ham
    Note: Do a factory reset after this setting so it is very short-lived.
    """
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --set-ham KI1234"
    )
    assert re.search(r"Setting Ham ID", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    return_value, out = subprocess.getstatusoutput("meshtastic --host localhost --info")
    assert re.search(r"Owner: KI1234", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_set_wifi_settings():
    """Test --set wifi_ssid and --set wifi_password"""
    return_value, out = subprocess.getstatusoutput(
        'meshtastic --host localhost --set wifi_ssid "some_ssid" --set wifi_password "temp1234"'
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Set wifi_ssid to some_ssid", out, re.MULTILINE)
    assert re.search(r"^Set wifi_password to temp1234", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --get wifi_ssid --get wifi_password"
    )
    assert re.search(r"^wifi_ssid: some_ssid", out, re.MULTILINE)
    assert re.search(r"^wifi_password: sekrit", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smokevirt
def test_smokevirt_factory_reset():
    """Test factory reset"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --host localhost --set factory_reset true"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Set factory_reset to true", out, re.MULTILINE)
    assert re.search(r"^Writing modified preferences to device", out, re.MULTILINE)
    assert return_value == 0
    # NOTE: The virtual radio will not respond well after this command. Need to re-start the virtual program at this point.
    # TODO: fix?
