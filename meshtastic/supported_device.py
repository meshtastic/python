""" Supported Meshtastic Devices - This is a class and collection of Meshtastic devices.
    It is used for auto detection as to which device might be connected.
"""

import platform
import subprocess
import re

# Goal is to detect which device and port to use from the supported devices
# without installing any libraries that are not currently in the python meshtastic library

class SupportedDevice():
    """Devices supported on Meshtastic"""

    def __init__(self, name, version=None, for_firmware=None, device_class="esp32",
                 baseport_on_linux=None, baseport_on_mac=None, baseport_on_windows="COM",
                 usb_vendor_id_in_hex=None, usb_product_id_in_hex=None):
        """ constructor """
        self.name = name
        self.version = version
        self.for_firmware = for_firmware
        self.device_class = device_class # could be "nrf52"

        # when you run "lsusb -d xxxx:" in linux
        self.usb_vendor_id_in_hex = usb_vendor_id_in_hex # store in lower case
        self.usb_product_id_in_hex = usb_product_id_in_hex # store in lower case

        self.baseport_on_linux = baseport_on_linux # ex: ttyUSB or ttyACM
        self.baseport_on_mac = baseport_on_mac
        self.baseport_on_windows = baseport_on_windows

# supported devices
tbeam_v0_7 = SupportedDevice(name="T-Beam", version="0.7", for_firmware="tbeam0.7",
                             baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                             usb_vendor_id_in_hex="1a86", usb_product_id_in_hex="55d4")
tbeam_v1_1 = SupportedDevice(name="T-Beam", version="1.1", for_firmware="tbeam",
                             baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                             usb_vendor_id_in_hex="1a86", usb_product_id_in_hex="55d4")
tbeam_M8N = SupportedDevice(name="T-Beam", version="M8N", for_firmware="tbeam",
                            baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                            usb_vendor_id_in_hex="1a86", usb_product_id_in_hex="55d4")
tbeam_M8N_SX1262 = SupportedDevice(name="T-Beam", version="M8N_SX1262", for_firmware="tbeam",
                                   baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                                   usb_vendor_id_in_hex="1a86", usb_product_id_in_hex="55d4")
tlora_v1_1 = SupportedDevice(name="T-Lora", version="1.1", for_firmware="tlora-v1",
                             baseport_on_linux="ttyUSB", baseport_on_mac="cu.usbserial",
                             usb_vendor_id_in_hex="10c4", usb_product_id_in_hex="ea60")
tlora_v1_3 = SupportedDevice(name="T-Lora", version="1.3", for_firmware="tlora-v1-3",
                             baseport_on_linux="ttyUSB", baseport_on_mac="cu.usbserial",
                             usb_vendor_id_in_hex="10c4", usb_product_id_in_hex="ea60")
tlora_v2_0 = SupportedDevice(name="T-Lora", version="2.0", for_firmware="tlora-v2-1",
                             baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                             usb_vendor_id_in_hex="1a86", usb_product_id_in_hex="55d4")
tlora_v2_1 = SupportedDevice(name="T-Lora", version="2.1", for_firmware="tlora-v2-1",
                             baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                             usb_vendor_id_in_hex="1a86", usb_product_id_in_hex="55d4")
tlora_v2_1_1_6 = SupportedDevice(name="T-Lora", version="2.1-1.6", for_firmware="tlora-v2-1-1.6",
                             baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                             usb_vendor_id_in_hex="1a86", usb_product_id_in_hex="55d4")
heltec_v1 = SupportedDevice(name="Heltec", version="1", for_firmware="heltec-v1",
                            baseport_on_linux="ttyUSB", baseport_on_mac="cu.usbserial-",
                            usb_vendor_id_in_hex="10c4", usb_product_id_in_hex="ea60")
heltec_v2_0 = SupportedDevice(name="Heltec", version="2.0", for_firmware="heltec-v2.0",
                              baseport_on_linux="ttyUSB", baseport_on_mac="cu.usbserial-",
                              usb_vendor_id_in_hex="10c4", usb_product_id_in_hex="ea60")
heltec_v2_1 = SupportedDevice(name="Heltec", version="2.1", for_firmware="heltec-v2.1",
                              baseport_on_linux="ttyUSB", baseport_on_mac="cu.usbserial-",
                              usb_vendor_id_in_hex="10c4", usb_product_id_in_hex="ea60")
meshtastic_diy_v1 = SupportedDevice(name="Meshtastic DIY", version="1", for_firmware="meshtastic-diy-v1",
                              baseport_on_linux="ttyUSB", baseport_on_mac="cu.usbserial-",
                              usb_vendor_id_in_hex="10c4", usb_product_id_in_hex="ea60")
# Note: The T-Echo reports product id in boot mode
techo_1 = SupportedDevice(name="T-Echo", version="1", for_firmware="t-echo-1", device_class="nrf52",
                              baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                              usb_vendor_id_in_hex="239a", usb_product_id_in_hex="0029")
rak4631_5005 = SupportedDevice(name="RAK 4631 5005", version="", for_firmware="rak4631_5005",
                               device_class="nrf52",
                               baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                               usb_vendor_id_in_hex="239a", usb_product_id_in_hex="0029")
# Note: The 19003 reports same product id as 5005 in boot mode
rak4631_19003 = SupportedDevice(name="RAK 4631 19003", version="", for_firmware="rak4631_19003",
                                device_class="nrf52",
                                baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                                usb_vendor_id_in_hex="239a", usb_product_id_in_hex="8029")

supported_devices = [tbeam_v0_7, tbeam_v1_1, tbeam_M8N, tbeam_M8N_SX1262,
                     tlora_v1_1, tlora_v1_3, tlora_v2_0, tlora_v2_1, tlora_v2_1_1_6,
                     heltec_v1, heltec_v2_0, heltec_v2_1,
                     meshtastic_diy_v1, techo_1, rak4631_5005, rak4631_19003]


def get_unique_vendor_ids():
    """Return a set of unique vendor ids"""
    vids = set()
    for d in supported_devices:
        if d.usb_vendor_id_in_hex:
            vids.add(d.usb_vendor_id_in_hex)
    return vids

def get_devices_with_vendor_id(vid):
    """Return a set of unique devices with the vendor id"""
    sd = set()
    for d in supported_devices:
        if d.usb_vendor_id_in_hex == vid:
            sd.add(d)
    return sd

def active_ports_on_supported_devices(sds):
    """Return a set of active ports based on the supplied supported devices"""
    ports = set()
    baseports = set()
    system = platform.system()

    # figure out what possible base ports there are
    for d in sds:
        if system == "Linux":
            baseports.add(d.baseport_on_linux)
        elif system == "Darwin":
            baseports.add(d.baseport_on_mac)
        elif system == "Windows":
            baseports.add(d.baseport_on_windows)

    for bp in baseports:
        if system == "Linux":
            # see if we have any devices (ignoring any stderr output)
            command = f'ls -al /dev/{bp}* 2> /dev/null'
            #print(f'command:{command}')
            _, ls_output = subprocess.getstatusoutput(command)
            #print(f'ls_output:{ls_output}')
            # if we got output, there are ports
            if len(ls_output) > 0:
                #print('got output')
                # for each line of output
                lines = ls_output.split('\n')
                #print(f'lines:{lines}')
                for line in lines:
                    parts = line.split(' ')
                    #print(f'parts:{parts}')
                    port = parts[-1]
                    #print(f'port:{port}')
                    ports.add(port)
        elif system == "Darwin":
            # see if we have any devices (ignoring any stderr output)
            command = f'ls -al /dev/{bp}* 2> /dev/null'
            #print(f'command:{command}')
            _, ls_output = subprocess.getstatusoutput(command)
            #print(f'ls_output:{ls_output}')
            # if we got output, there are ports
            if len(ls_output) > 0:
                #print('got output')
                # for each line of output
                lines = ls_output.split('\n')
                #print(f'lines:{lines}')
                for line in lines:
                    parts = line.split(' ')
                    #print(f'parts:{parts}')
                    port = parts[-1]
                    #print(f'port:{port}')
                    ports.add(port)
        elif system == "Windows":
            # for each device in supported devices found
            for d in sds:
                # find the port(s)
                com_ports = detect_windows_port(d)
                #print(f'com_ports:{com_ports}')
                # add all ports
                for com_port in com_ports:
                    ports.add(com_port)
    return ports


def detect_windows_port(sd):
    """detect if Windows port"""
    ports = set()

    if sd:
        system = platform.system()

        if system == "Windows":
            command = ('powershell.exe "[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8;'
                       'Get-PnpDevice -PresentOnly | Where-Object{ ($_.DeviceId -like ')
            command += f"'*{sd.usb_vendor_id_in_hex.upper()}*'"
            command += ')} | Format-List"'

            #print(f'command:{command}')
            _, sp_output = subprocess.getstatusoutput(command)
            #print(f'sp_output:{sp_output}')
            p = re.compile(r'\(COM(.*)\)')
            for x in p.findall(sp_output):
                #print(f'x:{x}')
                ports.add(f'COM{x}')
    return ports
