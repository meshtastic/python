"""Utility functions.
"""
import base64
import logging
import os
import platform
import re
import subprocess
import sys
import threading
import time
import traceback
from queue import Queue
from typing import List, NoReturn, Union

from google.protobuf.json_format import MessageToJson
from google.protobuf.message import Message

import packaging.version as pkg_version
import requests
import serial # type: ignore[import-untyped]
import serial.tools.list_ports # type: ignore[import-untyped]

from meshtastic.supported_device import supported_devices
from meshtastic.version import get_active_version

"""Some devices such as a seger jlink or st-link we never want to accidentally open
0x1915 NordicSemi (PPK2)
"""
blacklistVids = dict.fromkeys([0x1366, 0x0483, 0x1915])

"""Some devices are highly likely to be meshtastic.
0x239a RAK4631
0x303a Heltec tracker"""
whitelistVids = dict.fromkeys([0x239a, 0x303a])


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
    elif valstr.startswith("0x"):
        # if needed convert to string with asBytes.decode('utf-8')
        val = bytes.fromhex(valstr[2:])
    elif valstr.startswith("base64:"):
        val = base64.b64decode(valstr[7:])
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


def stripnl(s) -> str:
    """Remove newlines from a string (and remove extra whitespace)"""
    s = str(s).replace("\n", " ")
    return " ".join(s.split())


def fixme(message):
    """Raise an exception for things that needs to be fixed"""
    raise Exception(f"FIXME: {message}") # pylint: disable=W0719


def catchAndIgnore(reason, closure):
    """Call a closure but if it throws an exception print it and continue"""
    try:
        closure()
    except BaseException as ex:
        logging.error(f"Exception thrown in {reason}: {ex}")


def findPorts(eliminate_duplicates: bool=False) -> List[str]:
    """Find all ports that might have meshtastic devices
       eliminate_duplicates will run the eliminate_duplicate_port() on the collection

    Returns:
        list -- a list of device paths
    """
    all_ports = serial.tools.list_ports.comports()

    # look for 'likely' meshtastic devices
    ports = list(
        map(
            lambda port: port.device,
            filter(
                lambda port: port.vid is not None and port.vid in whitelistVids,
                all_ports,
            ),
        )
    )

    # if no likely devices, just list everything not blacklisted
    if len(ports) == 0:
        ports = list(
            map(
                lambda port: port.device,
                filter(
                    lambda port: port.vid is not None and port.vid not in blacklistVids,
                    all_ports,
                ),
            )
        )

    ports.sort()
    if eliminate_duplicates:
        ports = eliminate_duplicate_port(ports)
    return ports


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__ # type: ignore[assignment]
    __delattr__ = dict.__delitem__ # type: ignore[assignment]


class Timeout:
    """Timeout class"""

    def __init__(self, maxSecs: int=20):
        self.expireTime: Union[int, float] = 0
        self.sleepInterval: float = 0.1
        self.expireTimeout: int = maxSecs

    def reset(self):
        """Restart the waitForSet timer"""
        self.expireTime = time.time() + self.expireTimeout

    def waitForSet(self, target, attrs=()) -> bool:
        """Block until the specified attributes are set. Returns True if config has been received."""
        self.reset()
        while time.time() < self.expireTime:
            if all(map(lambda a: getattr(target, a, None), attrs)):
                return True
            time.sleep(self.sleepInterval)
        return False

    def waitForAckNak(
        self, acknowledgment, attrs=("receivedAck", "receivedNak", "receivedImplAck")
    ) -> bool:
        """Block until an ACK or NAK has been received. Returns True if ACK or NAK has been received."""
        self.reset()
        while time.time() < self.expireTime:
            if any(map(lambda a: getattr(acknowledgment, a, None), attrs)):
                acknowledgment.reset()
                return True
            time.sleep(self.sleepInterval)
        return False

    def waitForTraceRoute(self, waitFactor, acknowledgment, attr="receivedTraceRoute") -> bool:
        """Block until traceroute response is received. Returns True if traceroute response has been received."""
        self.expireTimeout *= waitFactor
        self.reset()
        while time.time() < self.expireTime:
            if getattr(acknowledgment, attr, None):
                acknowledgment.reset()
                return True
            time.sleep(self.sleepInterval)
        return False

    def waitForTelemetry(self, acknowledgment) -> bool:
        """Block until telemetry response is received. Returns True if telemetry response has been received."""
        self.reset()
        while time.time() < self.expireTime:
            if getattr(acknowledgment, "receivedTelemetry", None):
                acknowledgment.reset()
                return True
            time.sleep(self.sleepInterval)
        return False

    def waitForPosition(self, acknowledgment) -> bool:
        """Block until position response is received. Returns True if position response has been received."""
        self.reset()
        while time.time() < self.expireTime:
            if getattr(acknowledgment, "receivedPosition", None):
                acknowledgment.reset()
                return True
            time.sleep(self.sleepInterval)
        return False

class Acknowledgment:
    "A class that records which type of acknowledgment was just received, if any."

    def __init__(self):
        """initialize"""
        self.receivedAck = False
        self.receivedNak = False
        self.receivedImplAck = False
        self.receivedTraceRoute = False
        self.receivedTelemetry = False
        self.receivedPosition = False

    def reset(self):
        """reset"""
        self.receivedAck = False
        self.receivedNak = False
        self.receivedImplAck = False
        self.receivedTraceRoute = False
        self.receivedTelemetry = False
        self.receivedPosition = False


class DeferredExecution:
    """A thread that accepts closures to run, and runs them as they are received"""

    def __init__(self, name=None):
        self.queue = Queue()
        self.thread = threading.Thread(target=self._run, args=(), name=name)
        self.thread.daemon = True
        self.thread.start()

    def queueWork(self, runnable):
        """Queue up the work"""
        self.queue.put(runnable)

    def _run(self):
        while True:
            try:
                o = self.queue.get()
                o()
            except:
                logging.error(
                    f"Unexpected error in deferred execution {sys.exc_info()[0]}"
                )
                print(traceback.format_exc())


def our_exit(message, return_value=1) -> NoReturn:
    """Print the message and return a value.
    return_value defaults to 1 (non-successful)
    """
    print(message)
    sys.exit(return_value)


def support_info():
    """Print out info that helps troubleshooting of the cli."""
    print("")
    print("If having issues with meshtastic cli or python library")
    print("or wish to make feature requests, visit:")
    print("https://github.com/meshtastic/python/issues")
    print("When adding an issue, be sure to include the following info:")
    print(f" System: {platform.system()}")
    print(f"   Platform: {platform.platform()}")
    print(f"   Release: {platform.uname().release}")
    print(f"   Machine: {platform.uname().machine}")
    print(f"   Encoding (stdin): {sys.stdin.encoding}")
    print(f"   Encoding (stdout): {sys.stdout.encoding}")
    the_version = get_active_version()
    pypi_version = check_if_newer_version()
    if pypi_version:
        print(
            f" meshtastic: v{the_version} (*** newer version v{pypi_version} available ***)"
        )
    else:
        print(f" meshtastic: v{the_version}")
    if sys.version_info[0] == 3 and sys.version_info[1] < 9:
        print("  *** this version of the CLI is the last that supports python 3.8 ***")
        print("  *** please update your python installation ***")
    print(f" Executable: {sys.argv[0]}")
    print(
        f" Python: {platform.python_version()} {platform.python_implementation()} {platform.python_compiler()}"
    )
    print("")
    print("Please add the output from the command: meshtastic --info")


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
    return ":".join(f"{x:02x}" for x in barray)


def ipstr(barray):
    """Print a string of ip digits"""
    return ".".join(f"{x}" for x in barray)


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
    temp = a_string.split("_")
    # joining result
    result = temp[0] + "".join(ele.title() for ele in temp[1:])
    return result


def camel_to_snake(a_string):
    """convert camelCase to snake_case"""
    return "".join(["_" + i.lower() if i.isupper() else i for i in a_string]).lstrip(
        "_"
    )


def detect_supported_devices():
    """detect supported devices based on vendor id"""
    system = platform.system()
    # print(f'system:{system}')

    possible_devices = set()
    if system == "Linux":
        # if linux, run lsusb and list ports

        # linux: use lsusb
        # Bus 001 Device 091: ID 10c4:ea60 Silicon Labs CP210x UART Bridge
        _, lsusb_output = subprocess.getstatusoutput("lsusb")
        vids = get_unique_vendor_ids()
        for vid in vids:
            # print(f'looking for {vid}...')
            search = f" {vid}:"
            # print(f'search:"{search}"')
            if re.search(search, lsusb_output, re.MULTILINE):
                # print(f'Found vendor id that matches')
                devices = get_devices_with_vendor_id(vid)
                for device in devices:
                    possible_devices.add(device)

    elif system == "Windows":
        # if windows, run Get-PnpDevice
        _, sp_output = subprocess.getstatusoutput(
            'powershell.exe "[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8;'
            'Get-PnpDevice -PresentOnly | Format-List"'
        )
        # print(f'sp_output:{sp_output}')
        vids = get_unique_vendor_ids()
        for vid in vids:
            # print(f'looking for {vid.upper()}...')
            search = f"DeviceID.*{vid.upper()}&"
            # search = f'{vid.upper()}'
            # print(f'search:"{search}"')
            if re.search(search, sp_output, re.MULTILINE):
                # print(f'Found vendor id that matches')
                devices = get_devices_with_vendor_id(vid)
                for device in devices:
                    possible_devices.add(device)

    elif system == "Darwin":
        # run: system_profiler SPUSBDataType
        # Note: If in boot mode, the 19003 reports same product ID as 5005.

        _, sp_output = subprocess.getstatusoutput("system_profiler SPUSBDataType")
        vids = get_unique_vendor_ids()
        for vid in vids:
            # print(f'looking for {vid}...')
            search = f"Vendor ID: 0x{vid}"
            # print(f'search:"{search}"')
            if re.search(search, sp_output, re.MULTILINE):
                # print(f'Found vendor id that matches')
                devices = get_devices_with_vendor_id(vid)
                for device in devices:
                    possible_devices.add(device)
    return possible_devices


def detect_windows_needs_driver(sd, print_reason=False):
    """detect if Windows user needs to install driver for a supported device"""
    need_to_install_driver = False

    if sd:
        system = platform.system()
        # print(f'in detect_windows_needs_driver system:{system}')

        if system == "Windows":
            # if windows, see if we can find a DeviceId with the vendor id
            # Get-PnpDevice  | Where-Object{ ($_.DeviceId -like '*10C4*')} | Format-List
            command = 'powershell.exe "[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8; Get-PnpDevice | Where-Object{ ($_.DeviceId -like '
            command += f"'*{sd.usb_vendor_id_in_hex.upper()}*'"
            command += ')} | Format-List"'

            # print(f'command:{command}')
            _, sp_output = subprocess.getstatusoutput(command)
            # print(f'sp_output:{sp_output}')
            search = f"CM_PROB_FAILED_INSTALL"
            # print(f'search:"{search}"')
            if re.search(search, sp_output, re.MULTILINE):
                need_to_install_driver = True
                # if the want to see the reason
                if print_reason:
                    print(sp_output)
    return need_to_install_driver


def eliminate_duplicate_port(ports):
    """Sometimes we detect 2 serial ports, but we really only need to use one of the ports.

    ports is a list of ports
    return a list with a single port to use, if it meets the duplicate port conditions

     examples:
         Ports: ['/dev/cu.usbserial-1430', '/dev/cu.wchusbserial1430'] => ['/dev/cu.wchusbserial1430']
         Ports: ['/dev/cu.usbmodem11301', '/dev/cu.wchusbserial11301'] => ['/dev/cu.wchusbserial11301']
         Ports: ['/dev/cu.SLAB_USBtoUART', '/dev/cu.usbserial-0001'] => ['/dev/cu.usbserial-0001']
    """
    new_ports = []
    if len(ports) != 2:
        new_ports = ports
    else:
        ports.sort()
        if "usbserial" in ports[0] and "wchusbserial" in ports[1]:
            first = ports[0].replace("usbserial-", "")
            second = ports[1].replace("wchusbserial", "")
            if first == second:
                new_ports.append(ports[1])
        elif "usbmodem" in ports[0] and "wchusbserial" in ports[1]:
            first = ports[0].replace("usbmodem", "")
            second = ports[1].replace("wchusbserial", "")
            if first == second:
                new_ports.append(ports[1])
        elif "SLAB_USBtoUART" in ports[0] and "usbserial" in ports[1]:
            new_ports.append(ports[1])
        else:
            new_ports = ports
    return new_ports


def is_windows11():
    """Detect if Windows 11"""
    is_win11 = False
    if platform.system() == "Windows":
        if float(platform.release()) >= 10.0:
            patch = platform.version().split(".")[2]
            # in case they add some number suffix later, just get first 5 chars of patch
            patch = patch[:5]
            try:
                if int(patch) >= 22000:
                    is_win11 = True
            except Exception as e:
                print(f"problem detecting win11 e:{e}")
    return is_win11


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


def active_ports_on_supported_devices(sds, eliminate_duplicates=False):
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
            command = f"ls -al /dev/{bp}* 2> /dev/null"
            # print(f'command:{command}')
            _, ls_output = subprocess.getstatusoutput(command)
            # print(f'ls_output:{ls_output}')
            # if we got output, there are ports
            if len(ls_output) > 0:
                # print('got output')
                # for each line of output
                lines = ls_output.split("\n")
                # print(f'lines:{lines}')
                for line in lines:
                    parts = line.split(" ")
                    # print(f'parts:{parts}')
                    port = parts[-1]
                    # print(f'port:{port}')
                    ports.add(port)
        elif system == "Darwin":
            # see if we have any devices (ignoring any stderr output)
            command = f"ls -al /dev/{bp}* 2> /dev/null"
            # print(f'command:{command}')
            _, ls_output = subprocess.getstatusoutput(command)
            # print(f'ls_output:{ls_output}')
            # if we got output, there are ports
            if len(ls_output) > 0:
                # print('got output')
                # for each line of output
                lines = ls_output.split("\n")
                # print(f'lines:{lines}')
                for line in lines:
                    parts = line.split(" ")
                    # print(f'parts:{parts}')
                    port = parts[-1]
                    # print(f'port:{port}')
                    ports.add(port)
        elif system == "Windows":
            # for each device in supported devices found
            for d in sds:
                # find the port(s)
                com_ports = detect_windows_port(d)
                # print(f'com_ports:{com_ports}')
                # add all ports
                for com_port in com_ports:
                    ports.add(com_port)
    if eliminate_duplicates:
        ports = eliminate_duplicate_port(list(ports))
        ports.sort()
        ports = set(ports)
    return ports


def detect_windows_port(sd):
    """detect if Windows port"""
    ports = set()

    if sd:
        system = platform.system()

        if system == "Windows":
            command = (
                'powershell.exe "[Console]::OutputEncoding = [Text.UTF8Encoding]::UTF8;'
                "Get-PnpDevice -PresentOnly | Where-Object{ ($_.DeviceId -like "
            )
            command += f"'*{sd.usb_vendor_id_in_hex.upper()}*'"
            command += ')} | Format-List"'

            # print(f'command:{command}')
            _, sp_output = subprocess.getstatusoutput(command)
            # print(f'sp_output:{sp_output}')
            p = re.compile(r"\(COM(.*)\)")
            for x in p.findall(sp_output):
                # print(f'x:{x}')
                ports.add(f"COM{x}")
    return ports


def check_if_newer_version():
    """Check pip to see if we are running the latest version."""
    pypi_version = None
    try:
        url = "https://pypi.org/pypi/meshtastic/json"
        data = requests.get(url, timeout=5).json()
        pypi_version = data["info"]["version"]
    except Exception:
        pass
    act_version = get_active_version()

    try:
        parsed_act_version = pkg_version.parse(act_version)
        parsed_pypi_version = pkg_version.parse(pypi_version)
    except pkg_version.InvalidVersion:
        return pypi_version

    if parsed_pypi_version <= parsed_act_version:
        return None

    return pypi_version


def message_to_json(message: Message, multiline: bool=False) -> str:
    """Return protobuf message as JSON. Always print all fields, even when not present in data."""
    json = MessageToJson(message, always_print_fields_with_no_presence=True)
    return stripnl(json) if not multiline else json
