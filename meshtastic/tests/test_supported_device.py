"""Meshtastic unit tests for supported_device.py"""


from unittest.mock import patch
import pytest

from meshtastic.supported_device import active_ports_on_supported_devices, SupportedDevice


@pytest.mark.unit
@patch('platform.system', return_value='Linux')
def test_active_ports_on_supported_devices_empty(mock_platform):
    """Test active_ports_on_supported_devices()"""
    sds = set()
    assert active_ports_on_supported_devices(sds) == set()
    mock_platform.assert_called()


@pytest.mark.unit
@patch('subprocess.getstatusoutput')
@patch('platform.system', return_value='Linux')
def test_active_ports_on_supported_devices_linux(mock_platform, mock_sp):
    """Test active_ports_on_supported_devices()"""
    mock_sp.return_value = (None, 'crw-rw-rw-  1 root        wheel   0x9000000 Feb  8 22:22 /dev/ttyUSBfake')
    fake_device = SupportedDevice(name='a', for_firmware='heltec-v2.1', baseport_on_linux='ttyUSB')
    fake_supported_devices = [fake_device]
    assert active_ports_on_supported_devices(fake_supported_devices) == {'/dev/ttyUSBfake'}
    mock_platform.assert_called()
    mock_sp.assert_called()


@pytest.mark.unit
@patch('subprocess.getstatusoutput')
@patch('platform.system', return_value='Darwin')
def test_active_ports_on_supported_devices_mac(mock_platform, mock_sp):
    """Test active_ports_on_supported_devices()"""
    mock_sp.return_value = (None, 'crw-rw-rw-  1 root        wheel   0x9000000 Feb  8 22:22 /dev/cu.usbserial-foo')
    fake_device = SupportedDevice(name='a', for_firmware='heltec-v2.1', baseport_on_linux='cu.usbserial-')
    fake_supported_devices = [fake_device]
    assert active_ports_on_supported_devices(fake_supported_devices) == {'/dev/cu.usbserial-foo'}
    mock_platform.assert_called()
    mock_sp.assert_called()


@pytest.mark.unit
@patch('meshtastic.supported_device.detect_windows_port', return_value={'COM2'})
@patch('platform.system', return_value='Windows')
def test_active_ports_on_supported_devices_win(mock_platform, mock_dwp):
    """Test active_ports_on_supported_devices()"""
    fake_device = SupportedDevice(name='a', for_firmware='heltec-v2.1')
    fake_supported_devices = [fake_device]
    assert active_ports_on_supported_devices(fake_supported_devices) == {'COM2'}
    mock_platform.assert_called()
    mock_dwp.assert_called()


@pytest.mark.unit
@patch('subprocess.getstatusoutput')
@patch('platform.system', return_value='Darwin')
def test_active_ports_on_supported_devices_mac_no_duplicates_check(mock_platform, mock_sp):
    """Test active_ports_on_supported_devices()"""
    mock_sp.return_value = (None, ('crw-rw-rw-  1 root  wheel  0x9000005 Mar  8 10:05 /dev/cu.usbmodem53230051441\n'
                                   'crw-rw-rw-  1 root  wheel  0x9000003 Mar  8 10:06 /dev/cu.wchusbserial53230051441'))
    fake_device = SupportedDevice(name='a', for_firmware='tbeam', baseport_on_mac='cu.usbmodem')
    fake_supported_devices = [fake_device]
    assert active_ports_on_supported_devices(fake_supported_devices, False) == {'/dev/cu.usbmodem53230051441', '/dev/cu.wchusbserial53230051441'}
    mock_platform.assert_called()
    mock_sp.assert_called()


@pytest.mark.unit
@patch('subprocess.getstatusoutput')
@patch('platform.system', return_value='Darwin')
def test_active_ports_on_supported_devices_mac_duplicates_check(mock_platform, mock_sp):
    """Test active_ports_on_supported_devices()"""
    mock_sp.return_value = (None, ('crw-rw-rw-  1 root  wheel  0x9000005 Mar  8 10:05 /dev/cu.usbmodem53230051441\n'
                                   'crw-rw-rw-  1 root  wheel  0x9000003 Mar  8 10:06 /dev/cu.wchusbserial53230051441'))
    fake_device = SupportedDevice(name='a', for_firmware='tbeam', baseport_on_mac='cu.usbmodem')
    fake_supported_devices = [fake_device]
    assert active_ports_on_supported_devices(fake_supported_devices, True) == {'/dev/cu.wchusbserial53230051441'}
    mock_platform.assert_called()
    mock_sp.assert_called()
