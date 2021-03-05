#!python3

import argparse
import platform
import logging
import sys
import codecs
import base64
from . import SerialInterface, TCPInterface, BLEInterface, test, remote_hardware
from pubsub import pub
from . import mesh_pb2, portnums_pb2, channel_pb2
import google.protobuf.json_format
import pyqrcode
import traceback
import pkg_resources
from datetime import datetime
from easy_table import EasyTable
from google.protobuf.json_format import MessageToJson

"""We only import the tunnel code if we are on a platform that can run it"""
have_tunnel = platform.system() == 'Linux'

"""The command line arguments"""
args = None

"""The parser for arguments"""
parser = argparse.ArgumentParser()

channelIndex = 0


def onReceive(packet, interface):
    """Callback invoked when a packet arrives"""
    try:
        d = packet.get('decoded')

        # Exit once we receive a reply
        if args.sendtext and packet["to"] == interface.myInfo.my_node_num and d["portnum"] == portnums_pb2.PortNum.TEXT_MESSAGE_APP:
            interface.close()  # after running command then exit

        # Reply to every received message with some stats
        if args.reply:
            msg = d.get('text')
            if msg:
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


trueTerms = {"t", "true", "yes"}
falseTerms = {"f", "false", "no"}


def fromStr(valstr):
    """try to parse as int, float or bool (and fallback to a string as last resort)

    Returns: an int, bool, float, str or byte array (for strings of hex digits)

    Args:
        valstr (string): A user provided string
    """
    if(valstr.startswith('0x')):
        # if needed convert to string with asBytes.decode('utf-8')
        val = bytes.fromhex(valstr[2:])
    elif valstr in trueTerms:
        val = True
    elif valstr in falseTerms:
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


never = 0xffffffff
oneday = 24 * 60 * 60

# Returns formatted value


def formatFloat(value, formatStr="{:.2f}", unit="", default="N/A"):
    return formatStr.format(value)+unit if value else default

# Returns Last Heard Time in human readable format


def getLH(ts, default="N/A"):
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else default

# Print Nodes


def printNodes(nodes):
    # Create the table and define the structure
    table = EasyTable("Nodes")
    table.setCorners("/", "\\", "\\", "/")
    table.setOuterStructure("|", "-")
    table.setInnerStructure("|", "-", "+")

    tableData = []
    for node in nodes:
        # aux var to get not defined keys
        LH = getLH(node['position'].get("time"))
        lat = formatFloat(node['position'].get("latitude"), "{:.4f}", "°")
        lon = formatFloat(node['position'].get("longitude"), "{:.4f}", "°")
        alt = formatFloat(node['position'].get("altitude"), "{:.0f}", " m")
        batt = formatFloat(node['position'].get("batteryLevel"), "{:.2f}", "%")
        snr = formatFloat(node.get("snr"), "{:.2f}", " dB")
        tableData.append({"User": node['user']['longName'],
                          "Position": "Lat:"+lat+", Lon:"+lon+", Alt:"+alt,
                          "Battery": batt, "SNR": snr, "LastHeard": LH})
    table.setData(tableData)
    table.displayTable()


def setPref(attributes, name, valStr):
    """Set a channel or preferences value"""
    val = fromStr(valStr)
    try:
        try:
            setattr(attributes, name, val)
        except TypeError as ex:
            # The setter didn't like our arg type guess try again as a string
            setattr(attributes, name, valStr)

        # succeeded!
        print(f"Set {name} to {valStr}")
    except Exception as ex:
        print(f"Can't set {name} due to {ex}")


def onConnected(interface):
    """Callback invoked when we connect to a radio"""
    closeNow = False  # Should we drop the connection after we finish?
    try:
        global args
        print("Connected to radio")
        prefs = interface.radioConfig.preferences

        if args.settime or args.setlat or args.setlon or args.setalt:
            closeNow = True

            alt = 0
            lat = 0.0
            lon = 0.0
            time = 0
            if args.settime:
                time = int(args.settime)
            if args.setalt:
                alt = int(args.setalt)
                prefs.fixed_position = True
                print(f"Fixing altitude at {alt} meters")
            if args.setlat:
                lat = float(args.setlat)
                prefs.fixed_position = True
                print(f"Fixing latitude at {lat} degrees")
            if args.setlon:
                lon = float(args.setlon)
                prefs.fixed_position = True
                print(f"Fixing longitude at {lon} degrees")

            print("Setting device time/position")
            # can include lat/long/alt etc: latitude = 37.5, longitude = -122.1
            interface.sendPosition(lat, lon, alt, time)
            interface.writeConfig()

        if args.setowner:
            closeNow = True
            print(f"Setting device owner to {args.setowner}")
            interface.setOwner(args.setowner)

        if args.sendtext:
            closeNow = True
            print(f"Sending text message {args.sendtext} to {args.destOrAll}")
            interface.sendText(args.sendtext, args.destOrAll,
                               wantAck=True)

        if args.sendping:
            print(f"Sending ping message {args.sendtext} to {args.destOrAll}")
            payload = str.encode("test string")
            interface.sendData(payload, args.destOrAll, portNum=portnums_pb2.PortNum.REPLY_APP,
                               wantAck=True, wantResponse=True)

        if args.gpiowrb or args.gpiord or args.gpiowatch:
            rhc = remote_hardware.RemoteHardwareClient(interface)

            if args.gpiowrb:
                bitmask = 0
                bitval = 0
                for wrpair in (args.gpiowrb or []):
                    bitmask |= 1 << int(wrpair[0])
                    bitval |= int(wrpair[1]) << int(wrpair[0])
                print(
                    f"Writing GPIO mask 0x{bitmask:x} with value 0x{bitval:x} to {args.dest}")
                rhc.writeGPIOs(args.dest, bitmask, bitval)

            if args.gpiord:
                bitmask = int(args.gpiord)
                print(f"Reading GPIO mask 0x{bitmask:x} from {args.dest}")
                rhc.readGPIOs(args.dest, bitmask)

            if args.gpiowatch:
                bitmask = int(args.gpiowatch)
                print(f"Watching GPIO mask 0x{bitmask:x} from {args.dest}")
                rhc.watchGPIOs(args.dest, bitmask)

        # handle settings
        if args.set:
            closeNow = True

            # Handle the int/float/bool arguments
            for pref in args.set:
                setPref(
                    prefs, pref[0], pref[1])

            print("Writing modified preferences to device")
            interface.writeConfig()

        if args.seturl:
            closeNow = True
            interface.setURL(args.seturl)

        # handle changing channels
        if args.setchan or args.setch_longslow or args.setch_shortfast \
                or args.seturl != None:
            closeNow = True

            ch = interface.channels[channelIndex]

            def setSimpleChannel(modem_config):
                """Set one of the simple modem_config only based channels"""

                # Completely new channel settings
                chs = channel_pb2.ChannelSettings()
                chs.modem_config = modem_config
                chs.psk = bytes([1])  # Use default channel psk 1

                ch.settings.CopyFrom(chs)

            # handle the simple channel set commands
            if args.setch_longslow:
                setSimpleChannel(
                    channel_pb2.ChannelSettings.ModemConfig.Bw125Cr48Sf4096)

            if args.setch_shortfast:
                setSimpleChannel(
                    channel_pb2.ChannelSettings.ModemConfig.Bw500Cr45Sf128)

            # Handle the channel settings
            for pref in (args.setchan or []):
                setPref(ch.settings, pref[0], pref[1])

            print("Writing modified channels to device")
            interface.writeChannel(channelIndex)

        if args.info:
            closeNow = True
            print(interface.myInfo)
            print(interface.radioConfig)
            print("Channels:")
            for c in interface.channels:
                if c.role != channel_pb2.Channel.Role.DISABLED:
                    cStr = MessageToJson(c.settings).replace("\n", "")
                    print(f"  {channel_pb2.Channel.Role.Name(c.role)} {cStr}")
            print(f"\nChannel URL {interface.channelURL}")
            print("Nodes in mesh:")
            for n in interface.nodes.values():
                print(n)

        if args.nodes:
            closeNow = True
            printNodes(interface.nodes.values())

        if args.qr:
            closeNow = True
            print(f"Channel URL {interface.channelURL}")
            url = pyqrcode.create(interface.channelURL)
            print(url.terminal())

        if have_tunnel and args.tunnel:
            from . import tunnel
            # Even if others said we could close, stay open if the user asked for a tunnel
            closeNow = False
            tunnel.Tunnel(interface, subnet=args.tunnel_net)

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
    # pub.subscribe(onNode, "meshtastic.node")


def common():
    """Shared code for all of our command line wrappers"""
    global args
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Some commands require dest to be set, so we now use destOrAll for more lenient commands
    args.destOrAll = args.dest
    if not args.destOrAll:
        args.destOrAll = "^all"

    if not args.seriallog:
        if args.info or args.nodes or args.set or args.seturl or args.setowner or args.setlat or args.setlon or \
                args.settime or \
                args.setch_longslow or args.setch_shortfast or args.setchan or args.sendtext or \
                args.qr:
            args.seriallog = "none"  # assume no debug output in this case
        else:
            args.seriallog = "stdout"  # default to stdout

    if args.router != None:
        logging.error(
            '--set-router has been deprecated. Use "--set router true" or "--set router false" instead')
    elif args.test:
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


def initParser():
    global parser, args

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

    parser.add_argument("--nodes", help="Print Node List in a pretty formatted table",
                        action="store_true")

    parser.add_argument("--qr", help="Display the QR code that corresponds to the current channel",
                        action="store_true")

    parser.add_argument(
        "--set", help="Set a preferences field", nargs=2, action='append')

    parser.add_argument(
        "--setchan", help="Set a channel parameter", nargs=2, action='append')

    parser.add_argument(
        "--setch-longslow", help="Change to the standard long-range (but slow) channel", action='store_true')

    parser.add_argument(
        "--setch-shortfast", help="Change to the standard fast (but short range) channel", action='store_true')

    parser.add_argument(
        "--seturl", help="Set a channel URL", action="store")

    parser.add_argument(
        "--setowner", help="Set device owner name", action="store")

    parser.add_argument(
        "--dest", help="The destination node id for any sent commands, if not set '^all' is assumed", default=None)

    parser.add_argument(
        "--sendtext", help="Send a text message")

    parser.add_argument(
        "--sendping", help="Send a ping message (which requests a reply)", action="store_true")

    # parser.add_argument(
    #    "--repeat", help="Normally the send commands send only one message, use this option to request repeated sends")

    parser.add_argument(
        "--reply", help="Reply to received messages",
        action="store_true")

    parser.add_argument(
        "--gpiowrb", nargs=2, help="Set a particlar GPIO # to 1 or 0", action='append')

    parser.add_argument(
        "--gpiord", help="Read from a GPIO mask")

    parser.add_argument(
        "--gpiowatch", help="Start watching a GPIO mask for changes")

    parser.add_argument(
        "--settime", help="Set the real time clock on the device", action="store_true")

    parser.add_argument(
        "--setalt", help="Set device altitude (allows use without GPS)")

    parser.add_argument(
        "--setlat", help="Set device latitude (allows use without GPS)")

    parser.add_argument(
        "--setlon", help="Set device longitude (allows use without GPS)")

    parser.add_argument("--debug", help="Show API library debug log messages",
                        action="store_true")

    parser.add_argument("--test", help="Run stress test against all connected Meshtastic devices",
                        action="store_true")

    parser.add_argument("--ble", help="BLE mac address to connect to (BLE is not yet supported for this tool)",
                        default=None)

    parser.add_argument("--noproto", help="Don't start the API, just function as a dumb serial terminal.",
                        action="store_true")

    parser.add_argument('--set-router', dest='router',
                        action='store_true', help="Deprecated, use --set router true instead")
    parser.add_argument('--unset-router', dest='router',
                        action='store_false', help="Deprecated, use --set router false instead")

    if have_tunnel:
        parser.add_argument('--tunnel',
                            action='store_true', help="Create a TUN tunnel device for forwarding IP packets over the mesh")
        parser.add_argument(
            "--subnet", dest='tunnel_net', help="Read from a GPIO mask", default=None)

    parser.set_defaults(router=None)

    parser.add_argument('--version', action='version',
                        version=f"{pkg_resources.require('meshtastic')[0].version}")

    args = parser.parse_args()


def main():
    """Perform command line meshtastic operations"""
    initParser()
    common()


def tunnelMain():
    """Run a meshtastic IP tunnel"""
    global args
    initParser()
    args.tunnel = True
    common()


if __name__ == "__main__":
    main()
