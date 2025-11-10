"""Meshtastic smoke tests with a single device via USB"""
import io
import re
import subprocess
import sys
import time
from pathlib import Path
import tempfile

# Do not like using hard coded sleeps, but it probably makes
# sense to pause for the radio at appropriate times
import pytest

from ..util import findPorts

# seconds to pause after running a meshtastic command
PAUSE_AFTER_COMMAND = 2
PAUSE_AFTER_REBOOT = 10


@pytest.mark.smoke1
def test_smoke1_reboot():
    """Test reboot"""
    return_value, _ = subprocess.getstatusoutput("meshtastic --reboot")
    assert return_value == 0
    # pause for the radio to reset (10 seconds for the pause, and a few more seconds to be back up)
    time.sleep(2*PAUSE_AFTER_REBOOT)


@pytest.mark.smoke1
def test_smoke1_info():
    """Test --info"""
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Owner", out, re.MULTILINE)
    assert re.search(r"^My info", out, re.MULTILINE)
    assert re.search(r"^Nodes in mesh", out, re.MULTILINE)
    assert re.search(r"^Preferences", out, re.MULTILINE)
    assert re.search(r"^Channels", out, re.MULTILINE)
    assert re.search(r"^\s*Index 0: PRIMARY", out, re.MULTILINE)
    assert re.search(r"^Primary channel URL", out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_nodes():
    """Test --nodes"""
    return_value, out = subprocess.getstatusoutput('meshtastic --nodes --fmt json')
    assert re.match(r"Connected to radio", out)
    assert re.search(r"N.+User", out, re.MULTILINE)
    assert re.search(r'"N": 1, "User":', out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_get_with_invalid_setting():
    """Test '--get a_bad_setting'."""
    return_value, out = subprocess.getstatusoutput("meshtastic --get a_bad_setting")
    assert re.search(r"Choices are...", out)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_set_with_invalid_setting():
    """Test '--set a_bad_setting'."""
    return_value, out = subprocess.getstatusoutput("meshtastic --set a_bad_setting foo")
    assert re.search(r"Choices are...", out)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_ch_set_with_invalid_setting():
    """Test '--ch-set with a_bad_setting'."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --ch-set invalid_setting foo --ch-index 0"
    )
    assert re.search(r"Choices are...", out)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_pos_fields():
    """Test --pos-fields (with some values POS_ALTITUDE POS_ALT_MSL POS_BATTERY)"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --pos-fields ALTITUDE ALTITUDE_MSL HEADING"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Setting position fields to 259", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(2*PAUSE_AFTER_REBOOT)
    return_value, out = subprocess.getstatusoutput("meshtastic --pos-fields")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"ALTITUDE", out, re.MULTILINE)
    assert re.search(r"ALTITUDE_MSL", out, re.MULTILINE)
    assert re.search(r"HEADING", out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_test_with_arg_but_no_hardware():
    """Test --test
    Note: Since only one device is connected, it will not do much.
    """
    return_value, out = subprocess.getstatusoutput("meshtastic --test")
    assert re.search(r"^Warning: Must have at least two devices", out, re.MULTILINE)
    assert return_value == 1
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_debug():
    """Test --debug"""
    return_value, out = subprocess.getstatusoutput("meshtastic --info --debug")
    assert re.search(r"^Owner", out, re.MULTILINE)
    assert re.search(r"^DEBUG file", out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_seriallog_to_file():
    """Test --seriallog to a file creates a file"""
    with tempfile.NamedTemporaryFile('w+t', encoding='utf-8', delete=True, delete_on_close=False) as f:
        return_value, _ = subprocess.getstatusoutput(f"meshtastic --info --seriallog {f.name}")
        f.seek(0)
        data = f.read()
        assert len(data) > 2000
        assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_port():
    """Test --port"""
    # first, get the ports
    ports = findPorts(True)
    # hopefully there is just one
    assert len(ports) == 1
    port = ports[0]
    return_value, out = subprocess.getstatusoutput(f"meshtastic --port {port} --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Owner", out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_set_location_info():
    """Test --setlat, --setlon and --setalt"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --setlat 32.7767 --setlon -96.7970 --setalt 1337"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Fixing altitude", out, re.MULTILINE)
    assert re.search(r"^Fixing latitude", out, re.MULTILINE)
    assert re.search(r"^Fixing longitude", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out2 = subprocess.getstatusoutput("meshtastic --info")
    assert re.search(r"1337", out2, re.MULTILINE)
    assert re.search(r"32.7767", out2, re.MULTILINE)
    assert re.search(r"-96.797", out2, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_set_owner():
    """Test --set-owner name"""
    # make sure the owner is not Joe
    return_value, out = subprocess.getstatusoutput("meshtastic --set-owner Bob")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Setting device owner to Bob", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert not re.search(r"Owner: Joe", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --set-owner Joe")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Setting device owner to Joe", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.search(r"Owner: Joe", out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)

@pytest.mark.smoke1
def test_smoke1_ch_modem_presets():
    """Test --ch-vlongslow --ch-longslow, --ch-longfast, --ch-mediumslow, --ch-mediumsfast,
    --ch-shortslow, and --ch-shortfast arguments
    """
    exp = {
        "--ch-vlongslow": 'VERY_LONG_SLOW',
        "--ch-longslow": "LONG_SLOW",
        "--ch-longfast": "LONG_FAST",
        "--ch-medslow": "MEDIUM_SLOW",
        "--ch-medfast": "MEDIUM_FAST",
        "--ch-shortslow": "SHORT_SLOW",
        "--ch-shortfast": "SHORT_FAST",
    }

    for key, val in exp.items():
        print(key, val)
        return_value, out = subprocess.getstatusoutput(f"meshtastic {key}")
        assert re.match(r"Connected to radio", out)
        assert return_value == 0
        # pause for the radio (might reboot)
        time.sleep(2*PAUSE_AFTER_REBOOT)        # Radio tends to stall with many LoRa changes
        return_value, out = subprocess.getstatusoutput("meshtastic --info")
        assert re.search(f'"modemPreset":\\s*"{val}"', out, re.MULTILINE)
        assert return_value == 0
        # pause for the radio
        time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ch_set_name():
    """Test --ch-set name"""
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert not re.search(r"MyChannel", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-set name MyChannel")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"Warning: Need to specify", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --ch-set name MyChannel --ch-index 0"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Set name to MyChannel", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.search(r"MyChannel", out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ch_set_downlink_and_uplink():
    """Test -ch-set downlink_enabled X and --ch-set uplink_enabled X"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --ch-set downlink_enabled false --ch-set uplink_enabled false"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"Warning: Need to specify", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --ch-set downlink_enabled false --ch-set uplink_enabled false --ch-index 0"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.search(r'("uplinkEnabled")\s*:\s*(false)', out, re.MULTILINE)
    assert re.search(r'("downlinkEnabled")\s*:\s*(false)', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --ch-set downlink_enabled true --ch-set uplink_enabled true --ch-index 0"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Set downlink_enabled to true", out, re.MULTILINE)
    assert re.search(r"^Set uplink_enabled to true", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.search(r'("uplinkEnabled")\s*:\s*(true)', out, re.MULTILINE)
    assert re.search(r'("downlinkEnabled")\s*:\s*(true)', out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ch_add_and_ch_del():
    """Test --ch-add"""
    setAndTestUrl("CgI6ABIPCAE4A0ADSAFQG2gBwAYB")       # ensure we have only primary channel configured.
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-add testing")
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-index 1 --ch-del")
    assert re.search(r"Deleting channel 1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    # make sure the secondary channel is not there
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert not re.search(r"SECONDARY", out, re.MULTILINE)
    assert not re.search(r"testing", out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ch_enable_and_disable():
    """Test --ch-enable and --ch-disable"""
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-add testing")
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r'(Index\s*1:\s* SECONDARY).*("name"\s*:\s*"testing")', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    # ensure they need to specify a --ch-index
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-disable")
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --ch-disable --ch-index 1"
    )
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert not re.search(r'SECONDARY', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --ch-enable --ch-index 1"
    )
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r'(Index\s*1:\s* SECONDARY).*("name"\s*:\s*"testing")', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-del --ch-index 1")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"Deleting\schannel\s1", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ch_del_a_disabled_non_primary_channel():
    """Test --ch-del will work on a disabled non-primary channel."""
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-add testing")
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r'(Index\s*1:\s* SECONDARY).*("name"\s*:\s*"testing")', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    # ensure they need to specify a --ch-index
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-disable")
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --ch-disable --ch-index 1"
    )
    assert return_value == 0
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert not re.search(r"SECONDARY", out, re.MULTILINE)
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-del --ch-index 1")
    assert re.search(r"Deleting\schannel\s1", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert not re.search(r"DISABLED", out, re.MULTILINE)
    assert not re.search(r"SECONDARY", out, re.MULTILINE)
    assert not re.search(r"testing", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_attempt_to_delete_primary_channel():
    """Test that we cannot delete the PRIMARY channel."""
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-del --ch-index 0")
    assert re.search(r"Warning: Cannot delete primary channel", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_attempt_to_disable_primary_channel():
    """Test that we cannot disable the PRIMARY channel."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --ch-disable --ch-index 0"
    )
    assert re.search(r"Warning: Cannot enable", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_attempt_to_enable_primary_channel():
    """Test that we cannot enable the PRIMARY channel."""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --ch-enable --ch-index 0"
    )
    assert re.search(r"Warning: Cannot enable", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ensure_ch_del_second_of_three_channels():
    """Test that when we delete the 2nd of 3 channels, that it deletes the correct channel."""
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-add testing1")
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-add testing2")
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"testing2", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-del --ch-index 1")
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"testing2", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-del --ch-index 1")
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ensure_ch_del_third_of_three_channels():
    """Test that when we delete the 3rd of 3 channels, that it deletes the correct channel."""
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-add testing1")
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-add testing2")
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"testing2", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-del --ch-index 2")
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"testing1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --ch-del --ch-index 1")
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


def checkQr(f, qrCompare: str) -> None:
    """checks binary file containing url"""
    f.seek(0)
    qrData = f.read()
    assert len(qrData) > 20000  # file containing qr does not contain enough data
    qrSplit = qrData.split(b'\r\n', 3)
    assert len(qrSplit) == 4
    assert re.search(qrCompare, qrSplit[1].decode('utf-8'), re.MULTILINE)


def setAndTestUrl(pat: str) -> None:
    """transmits set-url command with pattern "pat" and then checks if has been set correctly"""
    url = f"https://meshtastic.org/e/#{pat}"
    return_value, out = subprocess.getstatusoutput(f"meshtastic --seturl {url}")
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.search(pat, out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_seturl_default():
    """Test --seturl with default value"""
    # set some channel value so we no longer have a default channel
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --ch-set name foo --ch-index 0"
    )
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    # ensure we no longer have a default primary channel
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert not re.search("CgI6ABIPCAE4A0ADSAFQG2gBwAYB", out, re.MULTILINE)
    assert return_value == 0
    setAndTestUrl("CgI6ABIPCAE4A0ADSAFQG2gBwAYB")


@pytest.mark.smoke1
def test_smoke1_seturl_invalid_url():
    """Test --seturl with invalid url"""
    # Note: This url is no longer a valid url.
    url = "https://www.meshtastic.org/c/#GAMiENTxuzogKQdZ8Lz_q89Oab8qB0RlZmF1bHQ="
    return_value, out = subprocess.getstatusoutput(f"meshtastic --seturl {url}")
    assert re.match(r"Connected to radio", out)
    assert re.search("Warning: There were no settings", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_seturl_2chan():
    """Test --seturl with 2 channels"""
    pat = "CgcSAQE6AggNCjASIOKjX3f5UXnz8zkcXi6MxfIsnNof5sUAW4FQQi_IXsLdGgRUZXN0KAEwAToCCBESDwgBOANAA0gBUBtoAcAGAQ"
    setAndTestUrl(pat)
    # check qr output
    with tempfile.NamedTemporaryFile('w+b', delete=True, delete_on_close=False) as f:
        return_value, _ = subprocess.getstatusoutput(f"meshtastic --qr-all >{f.name}")
        assert return_value == 0
        checkQr(f, pat)
    # reset to standard url
    setAndTestUrl("CgI6ABIPCAE4A0ADSAFQG2gBwAYB")


@pytest.mark.smoke1
def test_smoke1_send_hello():
    """Test --sendtext hello, use channel 1 to not bother other participants with testing messages"""
    return_value, out = subprocess.getstatusoutput('meshtastic --sendtext "hello from smoke test" --ch-index 1')
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Sending text message hello from smoke test to \^all on channelIndex:1", out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_seturl_3_to_2_chan():
    """Test --seturl with 3 channels, then reconfigure back to 1 channel"""
    pat = "CgcSAQE6AggNCjASIOKjX3f5UXnz8zkcXi6MxfIsnNof5sUAW4FQQi_IXsLdGgRUZXN0KAEwAToCCBESDwgBOANAA0gBUBtoAcAGAQ"
    setAndTestUrl(pat)
    # check qr output
    with tempfile.NamedTemporaryFile('w+b', delete=True, delete_on_close=False) as f:
        return_value, _ = subprocess.getstatusoutput(f"meshtastic --qr-all >{f.name}")
        assert return_value == 0
        checkQr(f, pat)
    # now configure 2 channels only
    pat = "CgcSAQE6AggNCjASIOKjX3f5UXnz8zkcXi6MxfIsnNof5sUAW4FQQi_IXsLdGgRUZXN0KAEwAToCCBESDwgBOANAA0gBUBtoAcAGAQ"
    setAndTestUrl(pat)
    # check qr output
    with tempfile.NamedTemporaryFile('w+b', delete=True, delete_on_close=False) as f:
        return_value, _ = subprocess.getstatusoutput(f"meshtastic --qr-all >{f.name}")
        assert return_value == 0
        checkQr(f, pat)
    # reset to standard url
    setAndTestUrl("CgI6ABIPCAE4A0ADSAFQG2gBwAYB")

@pytest.mark.smoke1
def test_smoke1_qr():
    """Test --qr"""
    # reset to standard url
    pat = "CgI6ABIPCAE4A0ADSAFQG2gBwAYB"
    setAndTestUrl(pat)
    with tempfile.NamedTemporaryFile('w+b', delete=True, delete_on_close=False) as f:
        return_value, _ = subprocess.getstatusoutput(f"meshtastic --qr >{f.name}")
        assert return_value == 0
        checkQr(f, pat)
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_configure():
    """Test --configure"""
    if not Path('example_config.yaml').exists():
        pytest.fail(f"Cannot access config: actual path: {Path.cwd()}. Execute tests from base folder.")

    _, out = subprocess.getstatusoutput(f"meshtastic --configure example_config.yaml")
    assert re.search("Connected to radio", out)
    assert re.search("^Setting owner properties: Bob TBeam - BOB - True", out, re.MULTILINE)
    assert re.search("^Setting channel url to https://www.meshtastic.org/e/#CgI6ABIPCAE4AUADSAFQHmgBwAYB", out, re.MULTILINE)
    assert re.search("^Setting fixed device position to lat 35.88888 lon -93.88888 alt 304", out, re.MULTILINE)
    assert re.search("^Set lora.region to US", out, re.MULTILINE)
    assert re.search("^Set display.screen_on_secs to 781", out, re.MULTILINE)
    assert re.search("^Set power.wait_bluetooth_secs to 344", out, re.MULTILINE)
    assert re.search("^Committing modified configuration to device", out, re.MULTILINE)
    # pause for the radio
    time.sleep(2*PAUSE_AFTER_REBOOT)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.search('Bob TBeam', out, re.MULTILINE)
    assert re.search('"latitude": 35.8', out, re.MULTILINE)
    assert re.search('"longitude": -93.8', out, re.MULTILINE)
    assert re.search('"fixedPosition": true', out, re.MULTILINE)
    assert re.search('"region": "US"', out, re.MULTILINE)
    assert re.search('"screenOnSecs": 781', out, re.MULTILINE)
    assert re.search('"waitBluetoothSecs": 344', out, re.MULTILINE)
    assert re.search("CgI6ABIPCAE4AUADSAFQHmgBwAYB", out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_set_ham():
    """Test --set-ham
    Note: Do a factory reset after this setting so it is very short-lived.
    """
    return_value, out = subprocess.getstatusoutput("meshtastic --set-ham KI1234")
    assert re.search(r"Setting Ham ID", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    return_value, out = subprocess.getstatusoutput("meshtastic --info")
    assert re.search(r"Owner: KI1234", out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_set_wifi_settings():
    """Test --set wifi_ssid and --set wifi_password"""
    return_value, out = subprocess.getstatusoutput(
        'meshtastic --set network.wifi_ssid "some_ssid" --set network.wifi_psk "temp1234"'
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Set network.wifi_ssid to some_ssid", out, re.MULTILINE)
    assert re.search(r"^Set network.wifi_psk to temp1234", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --get network.wifi_ssid --get network.wifi_psk"
    )
    assert re.search(r"^network.wifi_ssid:\s*some_ssid", out, re.MULTILINE)
    assert re.search(r"^network.wifi_psk:\s*temp1234", out, re.MULTILINE)
    assert return_value == 0
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_factory_reset():
    """Test factory reset"""
    return_value, out = subprocess.getstatusoutput(
        "meshtastic --factory-reset"
    )
    assert re.search("Connected to radio", out)
    assert re.search(r"(factory reset).+config\sreset", out, re.MULTILINE)
    assert return_value == 0
    # NOTE: The radio may not be responsive after this, may need to do a manual reboot
    # by pressing the button
    time.sleep(PAUSE_AFTER_REBOOT)
