import inspect
import math
import time
import sys
import curses


def error_handler(ErrorMessage, TraceMessage, AdditionalInfo, stdscr):
    calling_function = inspect.stack()[1][3]
    final_cleanup(stdscr)
    print("")
    print("")
    print("--------------------------------------------------------------")
    print("ERROR - Function (", calling_function, ") has encountered an error. ")
    print(ErrorMessage)
    print("")
    print("")
    print("TRACE")
    print(TraceMessage)
    print("")
    print("")
    if (AdditionalInfo != ""):
        print("Additonal info:", AdditionalInfo)
        print("")
        print("")
    print("--------------------------------------------------------------")
    print("")
    print("")
    time.sleep(1)
    sys.exit('Meshwatch exiting...')


def final_cleanup(stdscr):
    stdscr.keypad(0)
    curses.echo()
    curses.nocbreak()
    curses.curs_set(1)
    curses.endwin()


def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def from_str(valstr):
    """try to parse as int, float or bool (and fallback to a string as last resort)
    Returns: an int, bool, float, str or byte array (for strings of hex digits)
    Args:
        valstr (string): A user provided string
    """
    if (len(valstr) == 0):  # Treat an empty string as an empty bytes
        val = bytes()
    elif (valstr.startswith('0x')):
        # if needed convert to string with asBytes.decode('utf-8')
        val = bytes.fromhex(valstr[2:])
    elif valstr == True:
        val = True
    elif valstr == False:
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
