"""Utility functions.
"""
import traceback
from queue import Queue
import os
import sys
import base64
import time
import platform
import logging
import threading
import serial
import serial.tools.list_ports
import pkg_resources

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
    print(' System: {0}'.format(platform.system()))
    print('   Platform: {0}'.format(platform.platform()))
    print('   Release: {0}'.format(platform.uname().release))
    print('   Machine: {0}'.format(platform.uname().machine))
    print('   Encoding (stdin): {0}'.format(sys.stdin.encoding))
    print('   Encoding (stdout): {0}'.format(sys.stdout.encoding))
    print(' meshtastic: v{0}'.format(pkg_resources.require('meshtastic')[0].version))
    print(' Executable: {0}'.format(sys.argv[0]))
    print(' Python: {0} {1} {2}'.format(platform.python_version(),
          platform.python_implementation(), platform.python_compiler()))
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
    return ":".join('{:02x}'.format(x) for x in barray)


def ipstr(barray):
    """Print a string of ip digits"""
    return ".".join('{}'.format(x) for x in barray)


def readnet_u16(p, offset):
    """Read big endian u16 (network byte order)"""
    return p[offset] * 256 + p[offset + 1]


def convert_mac_addr(val):
    """Convert the base 64 encoded value to a mac address
       val - base64 encoded value (ex: '/c0gFyhb'))
       returns: a string formatted like a mac address (ex: 'fd:cd:20:17:28:5b')
    """
    val_as_bytes = base64.b64decode(val)
    return hexstr(val_as_bytes)
