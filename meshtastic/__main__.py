#!python3

import argparse
from . import StreamInterface, BLEInterface, test
import logging
import sys
from pubsub import pub
import google.protobuf.json_format

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


def onConnected(interface):
    """Callback invoked when we connect to a radio"""
    global args
    print("Connected to radio")
    closeNow = False  # Should we drop the connection after we finish?
    try:
        if args.settime:
            print("Setting device RTC time")
            # can include lat/long/alt etc: latitude = 37.5, longitude = -122.1
            interface.sendPosition()

        if args.sendtext:
            print(f"Sending text message {args.sendtext} to {args.dest}")
            interface.sendText(args.sendtext, args.dest,
                               wantAck=True, wantResponse=True)

        if args.set or args.setstr or args.setchan:
            closeNow = True

            # Handle the int/float/bool arguments
            for pref in (args.set or []):
                name = pref[0]
                #
                try:
                    valstr = pref[1]
                    val = fromStr(valstr)
                    print(f"Setting preference {name} to {val}")
                    setattr(interface.radioConfig.preferences, name, val)
                except Exception as ex:
                    print(f"Can't set {name} due to {ex}")

            # Handle the string arguments
            for pref in (args.setstr or []):
                name = pref[0]
                # try to parse as int, float or bool
                try:
                    val = pref[1]
                    print(f"Setting preference {name} to {val}")
                    setattr(interface.radioConfig.preferences, name, val)
                except Exception as ex:
                    print(f"Can't set {name} due to {ex}")

            for pref in (args.setchan or []):
                name = pref[0]
                #
                try:
                    valstr = pref[1]
                    val = fromStr(valstr)
                    print(f"Setting channel parameter {name} to {val}")
                    setattr(interface.radioConfig.channel_settings, name, val)
                except Exception as ex:
                    print(f"Can't set {name} due to {ex}")

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
    except Exception as ex:
        print(ex)

    if closeNow:
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
        "--device",
        help="The port the Meshtastic device is connected to, i.e. /dev/ttyUSB0. If unspecified, we'll try to find it.",
        default=None)

    parser.add_argument(
        "--seriallog",
        help="Log device serial output to either 'stdout', 'none' or a filename to append to.  Defaults to stdout.",
        default="stdout")

    parser.add_argument("--info", help="Read and display the radio config information",
                        action="store_true")

    parser.add_argument(
        "--set", help="Set a numeric preferences field", nargs=2, action='append')

    parser.add_argument(
        "--setstr", help="Set a string preferences field", nargs=2, action='append')

    parser.add_argument(
        "--setchan", help="Set a channel parameter", nargs=2, action='append')

    parser.add_argument(
        "--dest", help="The destination node id for the --send commands, if not set '^all' is assumed", default="^all")

    parser.add_argument(
        "--sendtext", help="Send a text message")

    parser.add_argument(
        "--reply", help="Reply to received messages",
        action="store_true")

    parser.add_argument(
        "--settime", help="Set the real time clock on the device", action="store_true")

    parser.add_argument("--debug", help="Show API library debug log messages",
                        action="store_true")

    parser.add_argument("--test", help="Run stress test against all connected Meshtastic devices",
                        action="store_true")

    parser.add_argument("--ble", help="hack for testing BLE code (BLE is not yet supported for this tool)",
                        action="store_true")

    parser.add_argument("--noproto", help="Don't start the API, just function as a dumb serial terminal.",
                        action="store_true")

    global args
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    if (not args.seriallog) and (args.info or args.set or args.setstr or args.setchan or args.sendtext):
        args.seriallog = "none"  # assume no debug output in this case

    if args.test:
        test.testAll()
    else:
        if args.seriallog == "stdout":
            logfile = sys.stdout
        elif not args.seriallog or args.seriallog == "none":
            args.seriallog = None
            logging.debug("Not logging serial output")
            logfile = None
        else:
            logging.info(f"Logging serial output to {args.seriallog}")
            logfile = open(args.seriallog, 'w+', buffering=1)  # line buffering

        subscribe()
        if args.ble:
            client = BLEInterface(args.device, debugOut=logfile)
        else:
            client = StreamInterface(
                args.device, debugOut=logfile, noProto=args.noproto)


if __name__ == "__main__":
    main()
