"""Meshtastic smoke tests with a single device"""
import re
import subprocess
import platform
import time

# Do not like using hard coded sleeps, but it probably makes
# sense to pause for the radio at apprpriate times
import pytest


@pytest.mark.smoke1
def test_smoke1_reboot():
    """Test reboot"""
    return_value, out = subprocess.getstatusoutput('meshtastic --reboot')
    assert return_value == 0
    # pause for the radio to reset (10 seconds for the pause, and a few more seconds to be back up)
    time.sleep(18)


@pytest.mark.smoke1
def test_smoke1_info():
    """Test --info"""
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Owner', out, re.MULTILINE)
    assert re.search(r'^My info', out, re.MULTILINE)
    assert re.search(r'^Nodes in mesh', out, re.MULTILINE)
    assert re.search(r'^Preferences', out, re.MULTILINE)
    assert re.search(r'^Channels', out, re.MULTILINE)
    assert re.search(r'^  PRIMARY', out, re.MULTILINE)
    assert re.search(r'^Primary channel URL', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_send_hello():
    """Test --sendtext hello"""
    return_value, out = subprocess.getstatusoutput('meshtastic --sendtext hello')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Sending text message hello to \^all', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_set_is_router_true():
    """Test --set is_router true"""
    return_value, out = subprocess.getstatusoutput('meshtastic --set is_router true')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Set is_router to true', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    return_value, out = subprocess.getstatusoutput('meshtastic --get is_router')
    assert re.search(r'^is_router: True', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_set_location_info():
    """Test --setlat, --setlon and --setalt """
    return_value, out = subprocess.getstatusoutput('meshtastic --setlat 32.7767 --setlon -96.7970 --setalt 1337')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Fixing altitude', out, re.MULTILINE)
    assert re.search(r'^Fixing latitude', out, re.MULTILINE)
    assert re.search(r'^Fixing longitude', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    return_value, out2 = subprocess.getstatusoutput('meshtastic --info')
    assert re.search(r'1337', out2, re.MULTILINE)
    assert re.search(r'32.7767', out2, re.MULTILINE)
    assert re.search(r'-96.797', out2, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_set_is_router_false():
    """Test --set is_router false"""
    return_value, out = subprocess.getstatusoutput('meshtastic --set is_router false')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Set is_router to false', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    return_value, out = subprocess.getstatusoutput('meshtastic --get is_router')
    assert re.search(r'^is_router: False', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_set_owner():
    """Test --set-owner name"""
    # make sure the owner is not Joe
    return_value, out = subprocess.getstatusoutput('meshtastic --set-owner Bob')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Setting device owner to Bob', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert not re.search(r'Owner: Joe', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    return_value, out = subprocess.getstatusoutput('meshtastic --set-owner Joe')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Setting device owner to Joe', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert re.search(r'Owner: Joe', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_ch_set_name():
    """Test --ch-set name"""
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert not re.search(r'MyChannel', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    return_value, out = subprocess.getstatusoutput('meshtastic --ch-set name MyChannel')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Set name to MyChannel', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert re.search(r'MyChannel', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_ch_set_modem_config():
    """Test --ch-set modem_config"""
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert not re.search(r'Bw31_25Cr48Sf512', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    return_value, out = subprocess.getstatusoutput('meshtastic --ch-set modem_config Bw31_25Cr48Sf512')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Set modem_config to Bw31_25Cr48Sf512', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert re.search(r'Bw31_25Cr48Sf512', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_seturl_default():
    """Test --seturl with default value"""
    # set some channel value so we no longer have a default channel
    return_value, out = subprocess.getstatusoutput('meshtastic --ch-set name foo')
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    # ensure we no longer have a default primary channel
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert not re.search('CgUYAyIBAQ', out, re.MULTILINE)
    assert return_value == 0
    url = "https://www.meshtastic.org/d/#CgUYAyIBAQ"
    return_value, out = subprocess.getstatusoutput(f"meshtastic --seturl {url}")
    assert re.match(r'Connected to radio', out)
    assert return_value == 0
    # pause for the radio
    time.sleep(1)
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert re.search('CgUYAyIBAQ', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_seturl_invalid_url():
    """Test --seturl with invalid url"""
    # Note: This url is no longer a valid url.
    url = "https://www.meshtastic.org/c/#GAMiENTxuzogKQdZ8Lz_q89Oab8qB0RlZmF1bHQ="
    return_value, out = subprocess.getstatusoutput(f"meshtastic --seturl {url}")
    assert re.match(r'Connected to radio', out)
    assert re.search('Aborting', out, re.MULTILINE)


@pytest.mark.smoke1
def test_smoke1_factory_reset():
    """Test factory reset"""
    return_value, out = subprocess.getstatusoutput('meshtastic --set factory_reset true')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Set factory_reset to true', out, re.MULTILINE)
    assert re.search(r'^Writing modified preferences to device', out, re.MULTILINE)
    assert return_value == 0
    # NOTE: The radio may not be responsive after this, may need to do a manual reboot
    # by pressing the button
