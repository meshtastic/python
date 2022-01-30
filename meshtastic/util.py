"""Utility functions.
"""
import traceback
from queue import Queue
import os
import re
import sys
import base64
import time
import platform
import logging
import threading
import subprocess
import serial
import serial.tools.list_ports
import pkg_resources
from meshtastic.supported_device import get_unique_vendor_ids, get_devices_with_vendor_id

"""Some devices such as a seger jlink we never want to accidentally open"""
blacklistVids = dict.fromkeys([0x1366])


def quoteBooleans(a_string):
    """Quote booleans
        given a string that contains ": true", replace with ": 'true'" (or false)
    """
    tmp = a_string.replace(": true", ": 'true'")
    tmp = tmp.replace(": false", ": 'false'")
    return tmp

def genPSK256():
    """Generate a random preshared key"""
    return os.urandom(32)


def fromPSK(valstr):
    """A special version of fromStr that assumes the user is trying to set a PSK.
    In that case we also allow "none", "default" or "random" (to have python generate one), or simpleN
    """
    if valstr == "random":
        return genPSK256()
    elif valstr == "none":
        return bytes([0])  # Use the 'no encryption' PSK
    elif valstr == "default":
        return bytes([1])  # Use default channel psk
    elif valstr.startswith("simple"):
        # Use one of the single byte encodings
        return bytes([int(valstr[6:]) + 1])
    else:
        return fromStr(valstr)


def fromStr(valstr):
    """Try to parse as int, float or bool (and fallback to a string as last resort)

    Returns: an int, bool, float, str or byte array (for strings of hex digits)

    Args:
        valstr (string): A user provided string
    """
    if len(valstr) == 0:  # Treat an emptystring as an empty bytes
        val = bytes()
    elif valstr.startswith('0x'):
        # if needed convert to string with asBytes.decode('utf-8')
        val = bytes.fromhex(valstr[2:])
    elif valstr.lower() in {"t", "true", "yes"}:
        val = True
    elif valstr.lower() in {"f", "false", "no"}:
        val = False
    else:
        try:
            val = int(valstr)
        except ValueError:
            try:
                val = float(valstr)
            except ValueError:
                val = valstr  # Not a float or an int, assume string
    return val


def pskToString(psk: bytes):
    """Given an array of PSK bytes, decode them into a human readable (but privacy protecting) string"""
    if len(psk) == 0:
        return "unencrypted"
    elif len(psk) == 1:
        b = psk[0]
        if b == 0:
            return "unencrypted"
        elif b == 1:
            return "default"
        else:
            return f"simple{b - 1}"
    else:
        return "secret"


def stripnl(s):
    """Remove newlines from a string (and remove extra whitespace)"""
    s = str(s).replace("\n", " ")
    return ' '.join(s.split())


def fixme(message):
    """Raise an exception for things that needs to be fixed"""
    raise Exception(f"FIXME: {message}")


def catchAndIgnore(reason, closure):
    """Call a closure but if it throws an exception print it and continue"""
    try:
        closure()
    except BaseException as ex:
        logging.error(f"Exception thrown in {reason}: {ex}")


def findPorts():
    """Find all ports that might have meshtastic devices

    Returns:
        list -- a list of device paths
    """
    l = list(map(lambda port: port.device,
                 filter(lambda port: port.vid is not None and port.vid not in blacklistVids,
                        serial.tools.list_ports.comports())))
    l.sort()
    return l


class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class Timeout:
    """Timeout class"""
    def __init__(self, maxSecs=20):
        self.expireTime = 0
        self.sleepInterval = 0.1
        self.expireTimeout = maxSecs

    def reset(self):
        """Restart the waitForSet timer"""
        self.expireTime = time.time() + self.expireTimeout

    def waitForSet(self, target, attrs=()):
        """Block until the specified attributes are set. Returns True if config has been received."""
        self.reset()
        while time.time() < self.expireTime:
            if all(map(lambda a: getattr(target, a, None), attrs)):
                return True
            time.sleep(self.sleepInterval)
        return False


class DeferredExecution():
    """A thread that accepts closures to run, and runs them as they are received"""

    def __init__(self, name=None):
        self.queue = Queue()
        self.thread = threading.Thread(target=self._run, args=(), name=name)
        self.thread.daemon = True
        self.thread.start()

    def queueWork(self, runnable):
        """ Queue up the work"""
        self.queue.put(runnable)

    def _run(self):
        while True:
            try:
                o = self.queue.get()
                o()
            except:
                logging.error(f"Unexpected error in deferred execution {sys.exc_info()[0]}")
                print(traceback.format_exc())


def our_exit(message, return_value = 1):
    """Print the message and return a value.
       return_value defaults to 1 (non-successful)
    """
    print(message)
    sys.exit(return_value)


def support_info():
    """Print out info that helps troubleshooting of the cli."""
    print('')
    print('If having issues with meshtastic cli or python library')
    print('or wish to make feature requests, visit:')
    print('https://github.com/meshtastic/Meshtastic-python/issues')
    print('When adding an issue, be sure to include the following info:')
    print(f' System: {platform.system()}')
    print(f'   Platform: {platform.platform()}')
    print(f'   Release: {platform.uname().release}')
    print(f'   Machine: {platform.uname().machine}')
    print(f'   Encoding (stdin): {sys.stdin.encoding}')
    print(f'   Encoding (stdout): {sys.stdout.encoding}')
    the_version = pkg_resources.get_distribution("meshtastic").version
    print(f' meshtastic: v{the_version}')
    print(f' Executable: {sys.argv[0]}')
    print(f' Python: {platform.python_version()} {platform.python_implementation()} {platform.python_compiler()}')
    print('')
    print('Please add the output from the command: meshtastic --info')


def remove_keys_from_dict(keys, adict):
    """Return a dictionary without some keys in it.
       Will removed nested keys.
    """
    for key in keys:
        try:
            del adict[key]
        except:
            pass
    for val in adict.values():
        if isinstance(val, dict):
            remove_keys_from_dict(keys, val)
    return adict


def hexstr(barray):
    """Print a string of hex digits"""
    return ":".join(f'{x:02x}' for x in barray)


def ipstr(barray):
    """Print a string of ip digits"""
    return ".".join(f'{x}' for x in barray)


def readnet_u16(p, offset):
    """Read big endian u16 (network byte order)"""
    return p[offset] * 256 + p[offset + 1]


def convert_mac_addr(val):
    """Convert the base 64 encoded value to a mac address
       val - base64 encoded value (ex: '/c0gFyhb'))
       returns: a string formatted like a mac address (ex: 'fd:cd:20:17:28:5b')
    """
    if not re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", val):
        val_as_bytes = base64.b64decode(val)
        return hexstr(val_as_bytes)
    return val


def snake_to_camel(a_string):
    """convert snake_case to camelCase"""
    # split underscore using split
    temp = a_string.split('_')
    # joining result
    result = temp[0] + ''.join(ele.title() for ele in temp[1:])
    return result


def camel_to_snake(a_string):
    """convert camelCase to snake_case"""
    return ''.join(['_'+i.lower() if i.isupper() else i for i in a_string]).lstrip('_')


def detect_supported_devices():
    """detect supported devices"""
    system = platform.system()
    #print(f'system:{system}')

    possible_devices = set()
    if system == "Linux":
        # if linux, run lsusb and list ports

        # linux: use lsusb
        # Bus 001 Device 091: ID 10c4:ea60 Silicon Labs CP210x UART Bridge
        _, lsusb_output = subprocess.getstatusoutput('lsusb')
        vids = get_unique_vendor_ids()
        for vid in vids:
            #print(f'looking for {vid}...')
            search = f' {vid}:'
            #print(f'search:"{search}"')
            if re.search(search, lsusb_output, re.MULTILINE):
                #print(f'Found vendor id that matches')
                devices = get_devices_with_vendor_id(vid)
                # check device id
                for device in devices:
                    #print(f'device:{device} device.usb_product_id_in_hex:{device.usb_product_id_in_hex}')
                    if device.usb_product_id_in_hex:
                        search = f' {vid}:{device.usb_product_id_in_hex} '
                        #print(f'search:"{search}"')
                        if re.search(search, lsusb_output, re.MULTILINE):
                            # concatenate the devices with vendor id to possibles
                            possible_devices.add(device)
                    else:
                        # if there is a supported device witout a product id, then it
                        # might be a match... so, concatenate
                        possible_devices.add(device)

    elif system == "Windows":
        # if windows, run Get-PnpDevice
        pass

    elif system == "Darwin":
        # run: system_profiler SPUSBDataType
        # could also run ioreg
        # if mac air (eg: arm m1) do not know how to get info TODO: research

        _, sp_output = subprocess.getstatusoutput('system_profiler SPUSBDataType')
        vids = get_unique_vendor_ids()
        for vid in vids:
            #print(f'looking for {vid}...')
            search = f'Vendor ID: 0x{vid}'
            #print(f'search:"{search}"')
            if re.search(search, sp_output, re.MULTILINE):
                #print(f'Found vendor id that matches')
                devices = get_devices_with_vendor_id(vid)
                # check device id
                for device in devices:
                    #print(f'device:{device} device.usb_product_id_in_hex:{device.usb_product_id_in_hex}')
                    if device.usb_product_id_in_hex:
                        search = f'Product ID: 0x{device.usb_product_id_in_hex}'
                        #print(f'search:"{search}"')
                        if re.search(search, sp_output, re.MULTILINE):
                            # concatenate the devices with vendor id to possibles
                            possible_devices.add(device)
                    else:
                        # if there is a supported device witout a product id, then it
                        # might be a match... so, concatenate
                        possible_devices.add(device)

        # ls -al /dev/{tty,cu}.*
        # crw-rw-rw-  1 root  wheel  0x9000003 Jan 13 02:46 /dev/cu.Bluetooth-Incoming-Port
        # crw-rw-rw-  1 root  wheel  0x9000005 Jan 29 12:00 /dev/cu.usbserial-0001
        # crw-rw-rw-  1 root  wheel  0x9000001 Jan 13 02:45 /dev/cu.wlan-debug
        # crw-rw-rw-  1 root  wheel  0x9000002 Jan 13 02:46 /dev/tty.Bluetooth-Incoming-Port
        # crw-rw-rw-  1 root  wheel  0x9000004 Jan 29 12:00 /dev/tty.usbserial-0001
        # crw-rw-rw-  1 root  wheel  0x9000000 Jan 13 02:45 /dev/tty.wlan-debug
        # and exclude any "Bluetooth" or "wlan" files
        # TODO: which should we prefer: cu or tty devices?

        # mac: ioreg -p IOUSB
        # +-o Root  <class IORegistryEntry, id 0x100000100, retain 27>
        #   +-o AppleT8103USBXHCI@00000000  <class AppleT8103USBXHCI, id 0x10000031c, registered, matched, active, busy 0 (9$
        #   +-o AppleT8103USBXHCI@01000000  <class AppleT8103USBXHCI, id 0x100000320, registered, matched, active, busy 0 (8$
        #     +-o CP2102 USB to UART Bridge Controller@01100000  <class IOUSBHostDevice, id 0x10000d096, registered, matched$
    return possible_devices
