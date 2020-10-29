#!python3

import argparse
from . import SerialInterface, TCPInterface, BLEInterface, test
import logging
import sys
from pubsub import pub
from . import mesh_pb2
import google.protobuf.json_format
import pyqrcode
import traceback
import codecs
import base64

"""The command line arguments"""
args = None


def onReceive(packet, interface):
    """Callback invoked when a packet arrives"""
    print(f"Received: {packet}")

    try:
        # Exit once we receive a reply
        if args.sendtext and packet["to"] == interface.myInfo.my_node_num:
            interface.close()  # after running command then exit

        # Reply to every received message with some stats
        if args.reply:
            if packet['decoded']['data'] is not None:
                msg = packet['decoded']['data']['text']
                #shortName = packet['decoded']['data']['shortName']
                rxSnr = packet['rxSnr']
                hopLimit = packet['hopLimit']
                print(f"message: {msg}")
                reply = "got msg \'{}\' with rxSnr: {} and hopLimit: {}".format(
                    msg, rxSnr, hopLimit)
                print("Sending reply: ", reply)
                interface.sendText(reply)

    except Exception as ex:
        print(ex)


def onConnection(interface, topic=pub.AUTO_TOPIC):
    """Callback invoked when we connect/disconnect from a radio"""
    print(f"Connection changed: {topic.getName()}")


def fromStr(valstr):
    """try to parse as int, float or bool (and fallback to a string as last resort)

    Returns: an int, bool, float or str

    Args:
        valstr (string): A user provided string
    """
    try:
        val = int(valstr)
    except ValueError:
        try:
            val = float(valstr)
        except ValueError:
            trueTerms = {"t", "true", "yes"}
            falseTerms = {"f", "false", "no"}
            if valstr in trueTerms:
                val = True
            elif valstr in falseTerms:
                val = False
            else:
                val = valstr  # Try to treat the parameter as a string
    return val


never = 0xffffffff
oneday = 24 * 60 * 60


def setRouter(interface, on):
    """Turn router mode on or off"""
    prefs = interface.radioConfig.preferences
    if on:
        print("Setting router mode")
        prefs.is_router = True
        prefs.is_low_power = True
        prefs.gps_operation = mesh_pb2.GpsOpMobile

        # FIXME - after tuning, move these params into the on-device defaults based on is_router and is_low_power

        # prefs.position_broadcast_secs = FIXME possibly broadcast only once an hr
        prefs.wait_bluetooth_secs = 1  # Don't stay in bluetooth mode
        prefs.screen_on_secs = 60  # default to only keep screen & bluetooth on for one minute
        prefs.mesh_sds_timeout_secs = never
        prefs.phone_sds_timeout_sec = never
        # try to stay in light sleep one full day, then briefly wake and sleep again

        prefs.ls_secs = oneday

        # if a message wakes us from light sleep, stay awake for 10 secs in hopes of other processing
        prefs.min_wake_secs = 10

        # allow up to five minutes for each new GPS lock attempt
        prefs.gps_attempt_time = 300

        # get a new GPS position once per day
        prefs.gps_update_interval = oneday

    else:
        print("Unsetting router mode")
        prefs.is_router = False
        prefs.is_low_power = False
        prefs.gps_operation = mesh_pb2.GpsOpUnset

        # Set defaults
        prefs.wait_bluetooth_secs = 0
        prefs.screen_on_secs = 0
        prefs.mesh_sds_timeout_secs = 0
        prefs.phone_sds_timeout_sec = 0
        prefs.ls_secs = 0
        prefs.min_wake_secs = 0
        prefs.gps_attempt_time = 0
        prefs.gps_update_interval = 0


def onConnected(interface):
    """Callback invoked when we connect to a radio"""
    global args
    print("Connected to radio")
    closeNow = False  # Should we drop the connection after we finish?
    try:
        if args.reset:
            interface.factoryReset()

        if args.resetstate:
            interface.factoryReset(True, True)

        if args.settime:
            print("Setting device RTC time")
            # can include lat/long/alt etc: latitude = 37.5, longitude = -122.1
            interface.sendPosition()

        if args.setowner:
            print(f"Setting device owner to {args.setowner}")
            interface.setOwner(args.setowner)

        if args.sendtext:
            print(f"Sending text message {args.sendtext} to {args.dest}")
            interface.sendText(args.sendtext, args.dest,
                               wantAck=True, wantResponse=True)

        if args.set or args.setstr or args.setchan or args.seturl or args.router != None:
            closeNow = True

            def setPref(attributes, name, val):
                """Set a preferences value"""
                print(f"Setting {name} to {val}")
                try:
                    try:
                        setattr(attributes, name, val)
                    except TypeError as ex:
                        # The setter didn't like our arg type - try again as a byte array (so we can convert strings to bytearray)
                        if isinstance(val, str):
                            setattr(attributes, name,
                                    codecs.decode(val, "hex"))
                        else:
                            print(f"Incorrect type for {name} {ex}")
                except Exception as ex:
                    print(f"Can't set {name} due to {ex}")

            if args.router != None:
                setRouter(interface, args.router)

            # Handle the int/float/bool arguments
            for pref in (args.set or []):
                setPref(
                    interface.radioConfig.preferences, pref[0], fromStr(pref[1]))

            # Handle the string arguments
            for pref in (args.setstr or []):
                setPref(interface.radioConfig.preferences, pref[0], pref[1])

            # Handle the channel settings
            for pref in (args.setchan or []):
                setPref(interface.radioConfig.channel_settings,
                        pref[0], fromStr(pref[1]))

            # Handle set URL
            if args.seturl:
                interface.setURL(args.seturl, False)

            print("Writing modified preferences to device")
            interface.writeConfig()

        if args.info:
            closeNow = True
            print(interface.myInfo)
            print(interface.radioConfig)
            print(f"Channel URL {interface.channelURL}")
            print("Nodes in mesh:")
            for n in interface.nodes.values():
                print(n)

        if args.qr:
            closeNow = True
            print(f"Channel URL {interface.channelURL}")
            url = pyqrcode.create(interface.channelURL)
            print(url.terminal())
    except Exception as ex:
        print(ex)

    # if the user didn't ask for serial debugging output, we might want to exit after we've done our operation
    if (not args.seriallog) and closeNow:
        interface.close()  # after running command then exit


def onNode(node):
    """Callback invoked when the node DB changes"""
    print(f"Node changed: {node}")


def subscribe():
    """Subscribe to the topics the user probably wants to see, prints output to stdout"""
    pub.subscribe(onReceive, "meshtastic.receive")
    # pub.subscribe(onConnection, "meshtastic.connection")
    pub.subscribe(onConnected, "meshtastic.connection.established")
    pub.subscribe(onNode, "meshtastic.node")


def main():
    """Perform command line meshtastic operations"""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--port",
        help="The port the Meshtastic device is connected to, i.e. /dev/ttyUSB0. If unspecified, we'll try to find it.",
        default=None)

    parser.add_argument(
        "--host",
        help="The hostname/ipaddr of the device to connect to (over TCP)",
        default=None)

    parser.add_argument(
        "--seriallog",
        help="Log device serial output to either 'stdout', 'none' or a filename to append to.  Defaults to stdout.")

    parser.add_argument("--info", help="Read and display the radio config information",
                        action="store_true")

    parser.add_argument("--qr", help="Display the QR code that corresponds to the current channel",
                        action="store_true")

    parser.add_argument(
        "--set", help="Set a numeric preferences field", nargs=2, action='append')

    parser.add_argument(
        "--setstr", help="Set a string preferences field", nargs=2, action='append')

    parser.add_argument(
        "--setchan", help="Set a channel parameter", nargs=2, action='append')

    parser.add_argument(
        "--seturl", help="Set a channel URL", action="store")

    parser.add_argument(
        "--setowner", help="Set device owner name", action="store")

    parser.add_argument(
        "--dest", help="The destination node id for the --send commands, if not set '^all' is assumed", default="^all")

    parser.add_argument(
        "--sendtext", help="Send a text message")

    parser.add_argument(
        "--reply", help="Reply to received messages",
        action="store_true")

    parser.add_argument(
        "--reset", help="Factory reset device", action="store_true")

    parser.add_argument(
        "--resetstate", help="Reset device but keep name and channel settings", action="store_true")

    parser.add_argument(
        "--settime", help="Set the real time clock on the device", action="store_true")

    parser.add_argument("--debug", help="Show API library debug log messages",
                        action="store_true")

    parser.add_argument("--test", help="Run stress test against all connected Meshtastic devices",
                        action="store_true")

    parser.add_argument("--ble", help="BLE mac address to connect to (BLE is not yet supported for this tool)",
                        default=None)

    parser.add_argument("--noproto", help="Don't start the API, just function as a dumb serial terminal.",
                        action="store_true")

    parser.add_argument('--set-router', dest='router',
                        action='store_true', help="Turns on router mode")
    parser.add_argument('--unset-router', dest='router',
                        action='store_false', help="Turns off router mode")

    parser.set_defaults(router=None)

    global args
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    if not args.seriallog:
        if args.info or args.set or args.setstr or args.setchan or args.sendtext or args.router != None or args.qr:
            args.seriallog = "none"  # assume no debug output in this case
        else:
            args.seriallog = "stdout"  # default to stdout

    if args.test:
        test.testAll()
    else:
        if args.seriallog == "stdout":
            logfile = sys.stdout
        elif args.seriallog == "none":
            args.seriallog = None
            logging.debug("Not logging serial output")
            logfile = None
        else:
            logging.info(f"Logging serial output to {args.seriallog}")
            logfile = open(args.seriallog, 'w+', buffering=1)  # line buffering

        subscribe()
        if args.ble:
            client = BLEInterface(args.ble, debugOut=logfile)
        elif args.host:
            client = TCPInterface(
                args.host, debugOut=logfile, noProto=args.noproto)
        else:
            client = SerialInterface(
                args.port, debugOut=logfile, noProto=args.noproto)


if __name__ == "__main__":
    main()
