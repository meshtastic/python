"""Meshtastic smoke tests with a single device via USB"""
import re
import subprocess
import time
import os

# Do not like using hard coded sleeps, but it probably makes
# sense to pause for the radio at apprpriate times
import pytest

import meshtastic

# seconds to pause after running a meshtastic command
PAUSE_AFTER_COMMAND = 2
PAUSE_AFTER_REBOOT = 7


@pytest.mark.smoke1
def test_smoke1_reboot():
    """Test reboot"""
    return_value, _ = subprocess.getstatusoutput('meshtastic --reboot')
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
def test_smoke1_sendping():
    """Test --sendping"""
    return_value, out = subprocess.getstatusoutput('meshtastic --sendping')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Sending ping message', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_pos_fields():
    """Test --pos-fields (with some values POS_ALTITUDE POS_ALT_MSL POS_BATTERY)"""
    return_value, out = subprocess.getstatusoutput('meshtastic --pos-fields POS_ALTITUDE POS_ALT_MSL POS_BATTERY')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Setting position fields to 35', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput('meshtastic --pos-fields')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'POS_ALTITUDE', out, re.MULTILINE)
    assert re.search(r'POS_ALT_MSL', out, re.MULTILINE)
    assert re.search(r'POS_BATTERY', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_test_no_arg():
    """Test --test
       Note: Test without arg.
    """
    return_value, _ = subprocess.getstatusoutput('meshtastic --test')
    assert return_value == 2


@pytest.mark.smoke1
def test_smoke1_test_with_arg_but_no_hardware():
    """Test --test
       Note: Since only one device is connected, it will not do much.
    """
    return_value, out = subprocess.getstatusoutput('meshtastic --test 5')
    assert re.search(r'^Warning: Must have at least two devices', out, re.MULTILINE)
    assert return_value == 1


@pytest.mark.smoke1
def test_smoke1_debug():
    """Test --debug"""
    return_value, out = subprocess.getstatusoutput('meshtastic --info --debug')
    assert re.search(r'^Owner', out, re.MULTILINE)
    assert re.search(r'^DEBUG:root', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_seriallog_to_file():
    """Test --seriallog to a file creates a file"""
    filename = 'tmpoutput.txt'
    if os.path.exists(f"{filename}"):
        os.remove(f"{filename}")
    return_value, _ = subprocess.getstatusoutput(f'meshtastic --info --seriallog {filename}')
    assert os.path.exists(f"{filename}")
    assert return_value == 0
    os.remove(f"{filename}")


@pytest.mark.smoke1
def test_smoke1_qr():
    """Test --qr"""
    filename = 'tmpqr'
    if os.path.exists(f"{filename}"):
        os.remove(f"{filename}")
    return_value, _ = subprocess.getstatusoutput(f'meshtastic --qr > {filename}')
    assert os.path.exists(f"{filename}")
    # not really testing that a valid qr code is created, just that the file size
    # is reasonably big enough for a qr code
    assert os.stat(f"{filename}").st_size > 20000
    assert return_value == 0
    os.remove(f"{filename}")


@pytest.mark.smoke1
def test_smoke1_nodes():
    """Test --nodes"""
    return_value, out = subprocess.getstatusoutput('meshtastic --nodes')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^│   N │ User', out, re.MULTILINE)
    assert re.search(r'^│   1 │', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_send_hello():
    """Test --sendtext hello"""
    return_value, out = subprocess.getstatusoutput('meshtastic --sendtext hello')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Sending text message hello to \^all', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_port():
    """Test --port"""
    # first, get the ports
    ports = meshtastic.util.findPorts()
    # hopefully there is just one
    assert len(ports) == 1
    port = ports[0]
    return_value, out = subprocess.getstatusoutput(f'meshtastic --port {port} --info')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Owner', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_set_is_router_true():
    """Test --set is_router true"""
    return_value, out = subprocess.getstatusoutput('meshtastic --set is_router true')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Set is_router to true', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
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
    time.sleep(PAUSE_AFTER_COMMAND)
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
    time.sleep(PAUSE_AFTER_COMMAND)
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
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert not re.search(r'Owner: Joe', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput('meshtastic --set-owner Joe')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Setting device owner to Joe', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert re.search(r'Owner: Joe', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_set_team():
    """Test --set-team """
    # unset the team
    return_value, out = subprocess.getstatusoutput('meshtastic --set-team CLEAR')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Setting team to CLEAR', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    return_value, out = subprocess.getstatusoutput('meshtastic --set-team CYAN')
    assert re.search(r'Setting team to CYAN', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert re.search(r'CYAN', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_ch_values():
    """Test --ch-longslow, --ch-longfast, --ch-mediumslow, --ch-mediumsfast,
       --ch-shortslow, and --ch-shortfast arguments
    """
    exp = {
            '--ch-longslow': 'Bw125Cr48Sf4096',
            # TODO: not sure why these fail thru tests, but ok manually
            #'--ch-longfast': 'Bw31_25Cr48Sf512',
            #'--ch-mediumslow': 'Bw250Cr46Sf2048',
            #'--ch-mediumfast': 'Bw250Cr47Sf1024',
            # TODO '--ch-shortslow': '?',
            '--ch-shortfast': 'Bw500Cr45Sf128'
          }

    for key, val in exp.items():
        print(key, val)
        return_value, out = subprocess.getstatusoutput(f'meshtastic {key}')
        assert re.match(r'Connected to radio', out)
        assert re.search(r'Writing modified channels to device', out, re.MULTILINE)
        assert return_value == 0
        # pause for the radio (might reboot)
        time.sleep(PAUSE_AFTER_REBOOT)
        return_value, out = subprocess.getstatusoutput('meshtastic --info')
        assert re.search(val, out, re.MULTILINE)
        assert return_value == 0
        # pause for the radio
        time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_ch_set_name():
    """Test --ch-set name"""
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert not re.search(r'MyChannel', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput('meshtastic --ch-set name MyChannel')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Set name to MyChannel', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert re.search(r'MyChannel', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_ch_add_and_ch_del():
    """Test --ch-add"""
    return_value, out = subprocess.getstatusoutput('meshtastic --ch-add testing')
    assert re.search(r'Writing modified channels to device', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'SECONDARY', out, re.MULTILINE)
    assert re.search(r'testing', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput('meshtastic --ch-index 1 --ch-del')
    assert re.search(r'Deleting channel 1', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    # make sure the secondar channel is not there
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert re.match(r'Connected to radio', out)
    assert not re.search(r'SECONDARY', out, re.MULTILINE)
    assert not re.search(r'testing', out, re.MULTILINE)
    assert return_value == 0


@pytest.mark.smoke1
def test_smoke1_ch_set_modem_config():
    """Test --ch-set modem_config"""
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert not re.search(r'Bw31_25Cr48Sf512', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
    return_value, out = subprocess.getstatusoutput('meshtastic --ch-set modem_config Bw31_25Cr48Sf512')
    assert re.match(r'Connected to radio', out)
    assert re.search(r'^Set modem_config to Bw31_25Cr48Sf512', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
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
    time.sleep(PAUSE_AFTER_COMMAND)
    # ensure we no longer have a default primary channel
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert not re.search('CgUYAyIBAQ', out, re.MULTILINE)
    assert return_value == 0
    url = "https://www.meshtastic.org/d/#CgUYAyIBAQ"
    return_value, out = subprocess.getstatusoutput(f"meshtastic --seturl {url}")
    assert re.match(r'Connected to radio', out)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)
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
    assert re.search('Warning: There were no settings', out, re.MULTILINE)
    assert return_value == 1
    # pause for the radio
    time.sleep(PAUSE_AFTER_COMMAND)


@pytest.mark.smoke1
def test_smoke1_configure():
    """Test --configure"""
    _ , out = subprocess.getstatusoutput(f"meshtastic --configure example_config.yaml")
    assert re.match(r'Connected to radio', out)
    assert re.search('^Setting device owner to Bob TBeam', out, re.MULTILINE)
    assert re.search('^Fixing altitude at 304 meters', out, re.MULTILINE)
    assert re.search('^Fixing latitude at 35.8', out, re.MULTILINE)
    assert re.search('^Fixing longitude at -93.8', out, re.MULTILINE)
    assert re.search('^Setting device position', out, re.MULTILINE)
    assert re.search('^Set region to 1', out, re.MULTILINE)
    assert re.search('^Set is_always_powered to true', out, re.MULTILINE)
    assert re.search('^Set send_owner_interval to 2', out, re.MULTILINE)
    assert re.search('^Set screen_on_secs to 31536000', out, re.MULTILINE)
    assert re.search('^Set wait_bluetooth_secs to 31536000', out, re.MULTILINE)
    assert re.search('^Writing modified preferences to device', out, re.MULTILINE)
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)


@pytest.mark.smoke1
def test_smoke1_set_ham():
    """Test --set-ham
       Note: Do a factory reset after this setting so it is very short-lived.
    """
    return_value, out = subprocess.getstatusoutput('meshtastic --set-ham KI1234')
    assert re.search(r'Setting HAM ID', out, re.MULTILINE)
    assert return_value == 0
    # pause for the radio
    time.sleep(PAUSE_AFTER_REBOOT)
    return_value, out = subprocess.getstatusoutput('meshtastic --info')
    assert re.search(r'Owner: KI1234', out, re.MULTILINE)
    assert return_value == 0


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
