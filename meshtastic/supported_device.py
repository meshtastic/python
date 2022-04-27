""" Supported Meshtastic Devices - This is a class and collection of Meshtastic devices.
    It is used for auto detection as to which device might be connected.
"""

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
tlora_v1 = SupportedDevice(name="T-Lora", version="1", for_firmware="tlora-v1",
                             baseport_on_linux="ttyUSB", baseport_on_mac="cu.usbserial",
                             usb_vendor_id_in_hex="1a86", usb_product_id_in_hex="55d4")
tlora_v1_3 = SupportedDevice(name="T-Lora", version="1.3", for_firmware="tlora-v1-3",
                             baseport_on_linux="ttyUSB", baseport_on_mac="cu.usbserial",
                             usb_vendor_id_in_hex="10c4", usb_product_id_in_hex="ea60")
tlora_v2 = SupportedDevice(name="T-Lora", version="2", for_firmware="tlora-v2",
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
rak11200 = SupportedDevice(name="RAK 11200", version="", for_firmware="rak11200",
                              baseport_on_linux="ttyUSB", baseport_on_mac="cu.usbserial-",
                              usb_vendor_id_in_hex="1a86", usb_product_id_in_hex="7523")
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
rak4631_5005_epaper = SupportedDevice(name="RAK 4631 5005 14000 epaper", version="", for_firmware="rak4631_5005_epaper",
                               device_class="nrf52",
                               baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                               usb_vendor_id_in_hex="239a", usb_product_id_in_hex="0029")
# Note: The 19003 reports same product id as 5005 in boot mode
rak4631_19003 = SupportedDevice(name="RAK 4631 19003", version="", for_firmware="rak4631_19003",
                                device_class="nrf52",
                                baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                                usb_vendor_id_in_hex="239a", usb_product_id_in_hex="8029")
nano_g1 = SupportedDevice(name="Nano G1", version="", for_firmware="nano-g1",
                              baseport_on_linux="ttyACM", baseport_on_mac="cu.usbmodem",
                              usb_vendor_id_in_hex="1a86", usb_product_id_in_hex="55d4")

supported_devices = [tbeam_v0_7, tbeam_v1_1, tbeam_M8N, tbeam_M8N_SX1262,
                     tlora_v1, tlora_v1_3, tlora_v2, tlora_v2_1_1_6,
                     heltec_v1, heltec_v2_0, heltec_v2_1,
                     meshtastic_diy_v1, techo_1, rak4631_5005, rak4631_5005_epaper, rak4631_19003,
                     rak11200, nano_g1]
