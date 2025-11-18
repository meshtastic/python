"""Meshtastic smoke tests with a single device via USB"""
import re
import subprocess
import time
from pathlib import Path
import tempfile

import pytest

from ..util import findPorts

# Do not like using hard coded sleeps, but it makes
# sense to pause for the radio at appropriate times to
# avoid overload of the radio.
# seconds to pause after running a meshtastic command
PAUSE_AFTER_COMMAND = 2
PAUSE_AFTER_REBOOT = 10
WAIT_FOR_REBOOT = -1

""" Following 2 switches allow control creation of additional or debug messages during testing
    DEBUG contains a string passed to the meshtastic call to log internal behavior
    VERBOSE toggles additional print output during the command execution of smoketest functions
    TEMPFILE contains the extracted settings of the radio till the tests have finished, so the 
    radio will not stay with wrong region settings for a longer time 
"""
DEBUG: str = ''
VERBOSE: bool = False
# DEBUG: str = '--debug --logTo smoke1.log'
# VERBOSE: bool = True
TEMPFILE = None


def noPrint(*args):
    """Dummy print function"""
    pass


vprint = print if VERBOSE else noPrint


# Helper functions used in executing tests
def communicate(cmd: str, repeatTimes: int = 2) -> tuple[int, str]:
    """Communicate to the radio. Repeat request in case serial line is not operational"""
    k = 0
    vprint(f'---COM: "{cmd}", r: {repeatTimes}')
    while k < repeatTimes:
        return_value, out = subprocess.getstatusoutput(f"{cmd} {DEBUG}")
        k += 1

        if return_value == 0 \
            and not re.search("Input/output error", out, re.MULTILINE) \
            and not re.search("MeshInterfaceError: Timed out", out, re.MULTILINE):
            break
        vprint(f"k: {k} ret: {return_value} out: {out}")
    return return_value, out

def waitFor(eventOrTime: int, repeatTimes: int = 5) -> None:
    """Wait for a dedicated time (positive integer input) or for a reboot. The latter will ensure that the
    serial line is back operational so we can safely send the next command."""
    vprint(f"---WAI {eventOrTime}")
    if eventOrTime > 0:
        time.sleep(eventOrTime)
    elif eventOrTime == WAIT_FOR_REBOOT:
        k = 0
        while True:
            time.sleep(2*PAUSE_AFTER_REBOOT)
            return_value, out = communicate("meshtastic --device-metadata")
            vprint(f"ret: {return_value} out: {out}")
            k += 1
            if return_value == 0 and re.search("firmware_version", out, re.MULTILINE) is not None:
                break
            if k > repeatTimes:
                vprint("Reboot failed")
                break

def checkQr(f, qrCompare: str) -> None:
    """checks binary file containing url"""
    f.seek(0)
    qrData = f.read()
    assert len(qrData) > 20000  # file containing qr does not contain enough data
    qrSplit = qrData.splitlines(keepends=True)
    vprint(f"checkQr: found lines: {len(qrSplit)}")
    assert len(qrSplit) >= 4
    assert re.search(qrCompare, qrSplit[1].decode('utf-8'), re.MULTILINE)

def setAndTestUrl(pat: str, skipTest: bool = False) -> None:
    """transmits set-url command with pattern "pat" and then checks if has been set correctly"""
    url = f"https://meshtastic.org/e/#{pat}"
    return_value, out = communicate(f"meshtastic --seturl {url}")
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    if not skipTest:
        return_value, out = communicate("meshtastic --info")
        assert re.search(pat, out, re.MULTILINE)
        assert return_value == 0
        waitFor(PAUSE_AFTER_COMMAND)


# Fixtures
@pytest.fixture
def temporaryCfgFile(scope="module"):
    """Return a temp file valid throughout the whole test.
    Purpose: store the exported data for later reconfigure"""
    global TEMPFILE
    if TEMPFILE is None:
        TEMPFILE = tempfile.NamedTemporaryFile(mode='w+t', encoding='utf-8', delete=False)
        print(f"created file {TEMPFILE.name}")
    else:
        open(TEMPFILE.name, 'r+t', encoding='utf-8')
    yield TEMPFILE
    TEMPFILE.close()

@pytest.mark.smoke1
def test_smoke1_reboot():
    """Test reboot"""
    return_value, _ = communicate("meshtastic --reboot")
    assert return_value == 0
    # pause for the radio to reset (10 seconds for the pause, and a few more seconds to be back up)
    waitFor(WAIT_FOR_REBOOT)


@pytest.mark.smoke1
def test_smoke1_info():
    """Test --info"""
    return_value, out = communicate("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Owner", out, re.MULTILINE)
    assert re.search(r"^My info", out, re.MULTILINE)
    assert re.search(r"^Nodes in mesh", out, re.MULTILINE)
    assert re.search(r"^Preferences", out, re.MULTILINE)
    assert re.search(r"^Channels", out, re.MULTILINE)
    assert re.search(r"^\s*Index 0: PRIMARY", out, re.MULTILINE)
    assert re.search(r"^Primary channel URL", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_export_config(temporaryCfgFile):
    """Test exporting current config, then later reimport and check if things are back as before
    Store this config in a temporary file to be used later"""
    vprint(f"\nGot temp file: {temporaryCfgFile.name}")
    return_value, out = communicate(f'meshtastic --export-config {temporaryCfgFile.name}')
    temporaryCfgFile.seek(0)
    vprint(f"ret: {return_value} out: {out}")
    pat = f"Exported configuration to {temporaryCfgFile.name}".replace('\\', '\\\\')
    assert re.match(pat, out)


@pytest.mark.smoke1
def test_smoke1_nodes():
    """Test --nodes"""
    return_value, out = communicate('meshtastic --nodes --fmt json')
    assert re.match(r"Connected to radio", out)
    assert re.search(r"N.+User", out, re.MULTILINE)
    assert re.search(r'"N": 1, "User":', out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_get_with_invalid_setting():
    """Test '--get a_bad_setting'."""
    return_value, out = communicate("meshtastic --get a_bad_setting")
    assert re.search(r"Choices are...", out)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_set_with_invalid_setting():
    """Test '--set a_bad_setting'."""
    return_value, out = communicate("meshtastic --set a_bad_setting foo")
    assert re.search(r"Choices are...", out)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_ch_set_with_invalid_setting():
    """Test '--ch-set with a_bad_setting'."""
    return_value, out = communicate(
        "meshtastic --ch-set invalid_setting foo --ch-index 0"
    )
    assert re.search(r"Choices are...", out)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_pos_fields():
    """Test --pos-fields (with some values POS_ALTITUDE POS_ALT_MSL POS_BATTERY)"""
    return_value, out = communicate(
        "meshtastic --pos-fields ALTITUDE ALTITUDE_MSL HEADING"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Setting position fields to 259", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(WAIT_FOR_REBOOT)
    return_value, out = communicate("meshtastic --pos-fields")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"ALTITUDE", out, re.MULTILINE)
    assert re.search(r"ALTITUDE_MSL", out, re.MULTILINE)
    assert re.search(r"HEADING", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_test_with_arg_but_no_hardware():
    """Test --test
    Note: Since only one device is connected, it will not do much.
    """
    return_value, out = communicate("meshtastic --test", repeatTimes=1)
    assert re.search(r"^Warning: Must have at least two devices", out, re.MULTILINE)
    assert return_value == 1
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_debug():
    """Test --debug"""
    return_value, out = communicate("meshtastic --info --debug")
    assert re.search(r"^Owner", out, re.MULTILINE)
    assert re.search(r"^DEBUG file", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_seriallog_to_file():
    """Test --seriallog to a file creates a file"""
    with tempfile.NamedTemporaryFile('w+t', encoding='utf-8', delete=True, delete_on_close=False) as f:
        return_value, _ = communicate(f"meshtastic --info --seriallog {f.name}")
        f.seek(0)
        data = f.read()
        assert len(data) > 2000
        assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_port():
    """Test --port"""
    # first, get the ports
    ports = findPorts(True)
    # hopefully there is just one
    assert len(ports) == 1
    port = ports[0]
    return_value, out = communicate(f"meshtastic --port {port} --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Owner", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_set_location_info():
    """Test --setlat, --setlon and --setalt"""
    return_value, out = communicate(
        "meshtastic --setlat 32.7767 --setlon -96.7970 --setalt 1337"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Fixing altitude", out, re.MULTILINE)
    assert re.search(r"^Fixing latitude", out, re.MULTILINE)
    assert re.search(r"^Fixing longitude", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out2 = communicate("meshtastic --info")
    assert re.search(r"1337", out2, re.MULTILINE)
    assert re.search(r"32.7767", out2, re.MULTILINE)
    assert re.search(r"-96.797", out2, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_set_owner():
    """Test --set-owner name"""
    # make sure the owner is not Joe
    return_value, out = communicate("meshtastic --set-owner Bob")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Setting device owner to Bob", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --info")
    assert not re.search(r"Owner: Joe", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --set-owner Joe")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Setting device owner to Joe", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --info")
    assert re.search(r"Owner: Joe", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)

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
    print("\n")
    for key, val in exp.items():
        print(key, val)
        return_value, out = communicate(f"meshtastic {key}")
        assert re.match(r"Connected to radio", out)
        assert return_value == 0
        # pause for the radio (might reboot)
        waitFor(WAIT_FOR_REBOOT)        # Radio tends to stall with many LoRa changes
        return_value, out = communicate("meshtastic --info")
        assert re.search(f'"modemPreset":\\s*"{val}"', out, re.MULTILINE)
        assert return_value == 0
        # pause for the radio
        waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ch_set_name():
    """Test --ch-set name"""
    return_value, out = communicate("meshtastic --info")
    assert not re.search(r"MyChannel", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --ch-set name MyChannel", repeatTimes=1)
    assert return_value == 1
    assert re.match(r"Connected to radio", out)
    assert re.search(r"Warning: Need to specify", out, re.MULTILINE)
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate(
        "meshtastic --ch-set name MyChannel --ch-index 0"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Set name to MyChannel", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --info")
    assert re.search(r"MyChannel", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ch_set_downlink_and_uplink():
    """Test -ch-set downlink_enabled X and --ch-set uplink_enabled X"""
    return_value, out = communicate(
        "meshtastic --ch-set downlink_enabled false --ch-set uplink_enabled false",
        repeatTimes=1
    )
    assert return_value == 1
    assert re.match(r"Connected to radio", out)
    assert re.search(r"Warning: Need to specify", out, re.MULTILINE)
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate(
        "meshtastic --ch-set downlink_enabled false --ch-set uplink_enabled false --ch-index 0"
    )
    assert re.match(r"Connected to radio", out)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --info")
    assert re.search(r'("uplinkEnabled")\s*:\s*(false)', out, re.MULTILINE)
    assert re.search(r'("downlinkEnabled")\s*:\s*(false)', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate(
        "meshtastic --ch-set downlink_enabled true --ch-set uplink_enabled true --ch-index 0"
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Set downlink_enabled to true", out, re.MULTILINE)
    assert re.search(r"^Set uplink_enabled to true", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --info")
    assert re.search(r'("uplinkEnabled")\s*:\s*(true)', out, re.MULTILINE)
    assert re.search(r'("downlinkEnabled")\s*:\s*(true)', out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ch_add_and_ch_del():
    """Test --ch-add"""
    setAndTestUrl("CgI6ABIPCAE4A0ADSAFQG2gBwAYB")       # ensure we have only primary channel configured.
    return_value, out = communicate("meshtastic --ch-add testing1")
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --ch-index 1 --ch-del")
    assert re.search(r"Deleting channel 1", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(WAIT_FOR_REBOOT)
    # make sure the secondary channel is not there
    return_value, out = communicate("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert not re.search(r"SECONDARY", out, re.MULTILINE)
    assert not re.search(r"testing1", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ch_enable_and_disable():
    """Test --ch-enable and --ch-disable"""
    setAndTestUrl("CgI6ABIPCAE4A0ADSAFQG2gBwAYB")       # ensure we have only primary channel configured.
    return_value, out = communicate("meshtastic --ch-add testing1")
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r'(Index\s*1:\s* SECONDARY).*("name"\s*:\s*"testing1")', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    # ensure they need to specify a --ch-index
    return_value, out = communicate("meshtastic --ch-disable", repeatTimes=1)
    assert return_value == 1
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --ch-disable --ch-index 1")
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert not re.search(r'SECONDARY', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --ch-enable --ch-index 1")
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r'(Index\s*1:\s* SECONDARY).*("name"\s*:\s*"testing1")', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    return_value, out = communicate("meshtastic --ch-del --ch-index 1")
    assert re.match(r"Connected to radio", out)
    assert re.search(r"Deleting\schannel\s1", out)
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ch_del_a_disabled_non_primary_channel():
    """Test --ch-del will work on a disabled non-primary channel."""
    setAndTestUrl("CgI6ABIPCAE4A0ADSAFQG2gBwAYB")       # ensure we have only primary channel configured.
    return_value, out = communicate("meshtastic --ch-add testing1")
    assert re.search(r"Writing modified channels to device", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)

    return_value, out = communicate("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert re.search(r'(Index\s*1:\s* SECONDARY).*("name"\s*:\s*"testing1")', out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)

    # ensure they need to specify a --ch-index
    return_value, out = communicate("meshtastic --ch-disable", repeatTimes=1)
    assert return_value == 1
    waitFor(PAUSE_AFTER_COMMAND)

    return_value, out = communicate("meshtastic --ch-disable --ch-index 1")
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)

    return_value, out = communicate("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert not re.search(r"SECONDARY", out, re.MULTILINE)
    waitFor(PAUSE_AFTER_COMMAND)

    return_value, out = communicate("meshtastic --ch-del --ch-index 1")
    assert re.search(r"Deleting\schannel\s1", out)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)

    return_value, out = communicate("meshtastic --info")
    assert re.match(r"Connected to radio", out)
    assert not re.search(r"DISABLED", out, re.MULTILINE)
    assert not re.search(r"SECONDARY", out, re.MULTILINE)
    assert not re.search(r"testing1", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_attempt_to_delete_primary_channel():
    """Test that we cannot delete the PRIMARY channel."""
    return_value, out = communicate("meshtastic --ch-del --ch-index 0", repeatTimes=1)
    assert re.search(r"Warning: Cannot delete primary channel", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_attempt_to_disable_primary_channel():
    """Test that we cannot disable the PRIMARY channel."""
    return_value, out = communicate(
        "meshtastic --ch-disable --ch-index 0",
        repeatTimes=1
    )
    assert re.search(r"Warning: Cannot enable", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_attempt_to_enable_primary_channel():
    """Test that we cannot enable the PRIMARY channel."""
    return_value, out = communicate(
        "meshtastic --ch-enable --ch-index 0",
        repeatTimes=1
    )
    assert re.search(r"Warning: Cannot enable", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ensure_ch_del_second_of_three_channels():
    """Test that when we delete the 2nd of 3 channels, that it deletes the correct channel."""

    # prepare test setting: setup 2 channels and validate they are created
    return_value, out = communicate("meshtastic --configure tests/ch_reset_config.yaml")
    assert return_value == 0
    waitFor(WAIT_FOR_REBOOT)

    return_value, out = communicate("meshtastic --ch-info")
    vprint(f"ret: {return_value} out: {out}")

    return_value, out = communicate("meshtastic --ch-add testing1")
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    waitFor(PAUSE_AFTER_COMMAND)

    return_value, out = communicate("meshtastic --ch-add testing2")
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    waitFor(PAUSE_AFTER_COMMAND)

    waitFor(WAIT_FOR_REBOOT)
    return_value, out = communicate("meshtastic --info")
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing1", out, re.MULTILINE)
    assert re.search(r"testing2", out, re.MULTILINE)
    waitFor(PAUSE_AFTER_COMMAND)

    # validate the first channel is deleted correctly.
    # Second channel must move up to index 1 and index 2 must become disabled
    return_value, out = communicate("meshtastic --ch-del --ch-index 1")
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    vprint(f"ret: {return_value} out: {out}")
    waitFor(PAUSE_AFTER_COMMAND)

    return_value, out = communicate("meshtastic --info")
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    assert re.search(r"testing2", out, re.MULTILINE)
    assert re.search(r"Index 1: SECONDARY", out, re.MULTILINE)
    assert not re.search(r"Index 2", out, re.MULTILINE)
    assert not re.search(r"Index 3", out, re.MULTILINE)
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ensure_ch_del_third_of_three_channels():
    """Test that when we delete the 3rd of 3 channels, that it deletes the correct channel."""

    # prepare test setting: setup 2 channels and validate they are created
    return_value, out = communicate("meshtastic --configure tests/ch_reset_config.yaml")
    assert return_value == 0
    waitFor(WAIT_FOR_REBOOT)

    return_value, out = communicate("meshtastic --ch-info")
    vprint(f"ret: {return_value} out: {out}")

    return_value, out = communicate("meshtastic --ch-add testing1")
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    waitFor(PAUSE_AFTER_COMMAND)

    return_value, out = communicate("meshtastic --ch-add testing2")
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    waitFor(PAUSE_AFTER_COMMAND)

    waitFor(WAIT_FOR_REBOOT)
    return_value, out = communicate("meshtastic --info", repeatTimes=2)
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"testing1", out, re.MULTILINE)
    assert re.search(r"testing2", out, re.MULTILINE)
    waitFor(PAUSE_AFTER_COMMAND)

    # validate the second channel is deleted correctly
    return_value, out = communicate("meshtastic --ch-del --ch-index 2")
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    waitFor(PAUSE_AFTER_COMMAND)

    return_value, out = communicate("meshtastic --info", repeatTimes=2)
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    assert re.search(r"testing1", out, re.MULTILINE)
    assert re.search(r"Index 1: SECONDARY", out, re.MULTILINE)
    assert not re.search(r"Index 2", out, re.MULTILINE)
    assert not re.search(r"Index 3", out, re.MULTILINE)
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_set_primary_channel():
    """Test --seturl with primary channel"""
    # prepare test setting: setup 2 channels and validate they are created
    return_value, _ = communicate("meshtastic --configure tests/ch_reset_config.yaml")
    assert return_value == 0
    waitFor(WAIT_FOR_REBOOT)

    # set to different url
    pat = "CgcSAQE6AggNEg8IATgDQANIAVAbaAHABgE"
    setAndTestUrl(pat)


@pytest.mark.smoke1
def test_smoke1_qr():
    """Test --qr, based on setting via URL"""
    # prepare test setting: setup 2 channels and validate they are created
    return_value, _ = communicate("meshtastic --configure tests/ch_reset_config.yaml")
    assert return_value == 0
    waitFor(WAIT_FOR_REBOOT)

    # set to different url
    pat = "CgcSAQE6AggNEg8IATgDQANIAVAbaAHABgE"
    setAndTestUrl(pat)
    with tempfile.NamedTemporaryFile('w+b', delete=True, delete_on_close=False) as f:
        return_value, _ = communicate(f"meshtastic --qr >{f.name}")
        assert return_value == 0
        checkQr(f, pat)
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_seturl_default():
    """Test --seturl with default value"""
    # prepare test setting: setup std channel
    return_value, out = communicate("meshtastic --configure tests/ch_reset_config.yaml")
    assert return_value == 0
    waitFor(WAIT_FOR_REBOOT)

    # set some channel value so we no longer have a default channel
    return_value, out = communicate(
        "meshtastic --ch-set name foo --ch-index 0"
    )
    assert return_value == 0
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)
    # ensure we no longer have a default primary channel
    return_value, out = communicate("meshtastic --info")
    assert not re.search("CgI6ABIPCAE4A0ADSAFQG2gBwAYB", out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_seturl_invalid_url():
    """Test --seturl with invalid url"""
    # Note: This url is no longer a valid url.
    url = "https://www.meshtastic.org/c/#GAMiENTxuzogKQdZ8Lz_q89Oab8qB0RlZmF1bHQ="
    return_value, out = communicate(f"meshtastic --seturl {url}", repeatTimes=1)
    assert re.match(r"Connected to radio", out)
    assert re.search("Warning: There were no settings", out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_seturl_2chan():
    """Test --seturl with 2 channels"""
    # prepare test setting: setup 2 channels and validate they are created
    return_value, _ = communicate("meshtastic --configure tests/ch_reset_config.yaml")
    assert return_value == 0
    waitFor(WAIT_FOR_REBOOT)

    pat = "CgcSAQE6AggNCjASIOKjX3f5UXnz8zkcXi6MxfIsnNof5sUAW4FQQi_IXsLdGgRUZXN0KAEwAToCCBESDwgBOANAA0gBUBtoAcAGAQ"
    setAndTestUrl(pat)
    # check qr output
    with tempfile.NamedTemporaryFile('w+b', delete=True, delete_on_close=False) as f:
        return_value, _ = communicate(f"meshtastic --qr-all >{f.name}")
        assert return_value == 0
        checkQr(f, pat)


@pytest.mark.smoke1
def test_smoke1_seturl_3_to_2_chan():
    """Test --seturl with 3 channels, then reconfigure 2 channels"""
    # prepare test setting: setup 2 channels and validate they are created
    return_value, out = communicate("meshtastic --configure tests/ch_reset_config.yaml")
    assert return_value == 0
    waitFor(WAIT_FOR_REBOOT)

    pat = "CgcSAQE6AggNCjESIOKjX3f5UXnz8zkcXi6MxfIsnNof5sUAW4FQQi_IXsLdGgV0ZXN0MSgBMAE6AggRCi0SIGyPI2Gbw3v6rl9H\
    Q8SL3LvRx7ScovIdU6pahs_l59CoGgV0ZXN0MigBMAESDwgBOANAA0gBUBtoAcAGAQ"
    setAndTestUrl(pat)
    # check that we have 3 channels
    return_value, out = communicate("meshtastic --info", repeatTimes=2)
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"test1", out, re.MULTILINE)
    assert re.search(r"test2", out, re.MULTILINE)
    waitFor(PAUSE_AFTER_COMMAND)

    # now configure 2 channels only
    patSet = "CgcSAQE6AggNCjASIOKjX3f5UXnz8zkcXi6MxfIsnNof5sUAW4FQQi_IXsLdGgRUZXN0KAEwAToCCBESDwgBOANAA0gBUBtoAcAGAQ"
    setAndTestUrl(patSet, skipTest=True)

    # now test for patComp (url will be diefferent because of not deleted channel 2)
    return_value, out = communicate("meshtastic --info", repeatTimes=2)
    assert return_value == 0
    assert re.match(r"Connected to radio", out)
    assert re.search(r"SECONDARY", out, re.MULTILINE)
    assert re.search(r"Test", out, re.MULTILINE)        # Test for changed channel
    assert re.search(r"test2", out, re.MULTILINE)       # this one should remain as before
    waitFor(PAUSE_AFTER_COMMAND)
    # Note: keep one secondary channel in order to send the hello to it

@pytest.mark.smoke1
def test_smoke1_send_hello():
    """Test --sendtext hello, use channel 1 to not bother other participants with testing messages"""
    return_value, out = communicate('meshtastic --sendtext "hello from smoke test" --ch-index 1')
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Sending text message hello from smoke test to \^all on channelIndex:1", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_configure():
    """Test --configure"""
    cfgPth = Path('example_config.yaml')
    if not cfgPth.exists():
        cfgPth = Path.cwd().parent / cfgPth
        if not cfgPth.exists():
            pytest.fail(f"Cannot access config: actual path: {Path.cwd()}. Execute tests from base folder.")

    _, out = communicate(f"meshtastic --configure {str(cfgPth)}")
    vprint(f"out: {out}")
    assert re.search("Connected to radio", out)
    assert re.search("^Setting owner properties: Bob TBeam - BOB - True", out, re.MULTILINE)
    assert re.search("^Setting channel url to https://www.meshtastic.org/e/#CgQ6AggNEg8IATgBQANIAVAeaAHABgE", out, re.MULTILINE)
    assert re.search("^Setting fixed device position to lat 35.88888 lon -93.88888 alt 304", out, re.MULTILINE)
    assert re.search("^Set lora.region to US", out, re.MULTILINE)
    assert re.search("^Set display.screen_on_secs to 781", out, re.MULTILINE)
    assert re.search("^Set power.wait_bluetooth_secs to 344", out, re.MULTILINE)
    assert re.search("^Committing modified configuration to device", out, re.MULTILINE)
    # pause for the radio
    waitFor(WAIT_FOR_REBOOT)
    return_value, out = communicate("meshtastic --info", repeatTimes=2)
    assert re.search('Bob TBeam', out, re.MULTILINE)
    assert re.search('"latitude": 35.8', out, re.MULTILINE)
    assert re.search('"longitude": -93.8', out, re.MULTILINE)
    assert re.search('"gpsMode": "ENABLED"', out, re.MULTILINE)
    assert re.search('"region": "US"', out, re.MULTILINE)
    assert re.search('"screenOnSecs": 781', out, re.MULTILINE)
    assert re.search('"waitBluetoothSecs": 344', out, re.MULTILINE)
    assert re.search("CgQ6AggNEg8IATgBQANIAVAeaAHABgE", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_set_ham():
    """Test --set-ham
    Note: Do a factory reset after this setting so it is very short-lived.
    """
    return_value, out = communicate("meshtastic --set-ham KI1234")
    assert re.search(r"Setting Ham ID", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(WAIT_FOR_REBOOT)
    return_value, out = communicate("meshtastic --info")
    assert re.search(r"Owner: KI1234", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_set_wifi_settings():
    """Test --set wifi_ssid and --set wifi_password"""
    return_value, out = communicate(
        'meshtastic --set network.wifi_ssid "some_ssid" --set network.wifi_psk "temp1234"'
    )
    assert re.match(r"Connected to radio", out)
    assert re.search(r"^Set network.wifi_ssid to some_ssid", out, re.MULTILINE)
    assert re.search(r"^Set network.wifi_psk to temp1234", out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    waitFor(WAIT_FOR_REBOOT)
    return_value, out = communicate(
        "meshtastic --get network.wifi_ssid --get network.wifi_psk"
    )
    assert re.search(r"^network.wifi_ssid:\s*some_ssid", out, re.MULTILINE)
    assert re.search(r"^network.wifi_psk:\s*temp1234", out, re.MULTILINE)
    assert return_value == 0
    waitFor(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_factory_reset():
    """Test factory reset"""
    return_value, out = communicate("meshtastic --factory-reset")
    assert re.search("Connected to radio", out)
    assert re.search(r"(factory reset).+config\sreset", out, re.MULTILINE)
    assert return_value == 0
    # NOTE: The radio may not be responsive after this, may need to do a manual reboot
    # by pressing the button
    waitFor(WAIT_FOR_REBOOT)

@pytest.mark.smoke1
def test_smoke1_config_reset(temporaryCfgFile):
    """Restore original settings"""
    vprint(f"Got temp file: {temporaryCfgFile.name}")
    return_value, out = communicate(f"meshtastic --config {temporaryCfgFile.name}")
    vprint(f"ret: {return_value} out: {out}")
    assert re.search(r"Connected to radio", out)
    assert re.search(r"Configuration finished", out)


if TEMPFILE is not None:
    Path(TEMPFILE).unlink(missing_ok=True)
