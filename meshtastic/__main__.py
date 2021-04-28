#!python3

import argparse
import platform
import logging
import sys
import codecs
import time
import base64
import os
from . import SerialInterface, TCPInterface, BLEInterface, test, remote_hardware
from pubsub import pub
from . import mesh_pb2, portnums_pb2, channel_pb2
from .util import stripnl
import google.protobuf.json_format
import pyqrcode
import traceback
import pkg_resources

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
                #shortName = packet['decoded']['shortName']
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


def genPSKS256():
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
    """try to parse as int, float or bool (and fallback to a string as last resort)

    Returns: an int, bool, float, str or byte array (for strings of hex digits)

    Args:
        valstr (string): A user provided string
    """
    if(len(valstr) == 0):  # Treat an emptystring as an empty bytes
        val = bytes()
    elif(valstr.startswith('0x')):
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


def setPref(attributes, name, valStr):
    """Set a channel or preferences value"""

    objDesc = attributes.DESCRIPTOR
    field = objDesc.fields_by_name.get(name)
    if not field:
        print(f"{attributes.__class__.__name__} doesn't have an attribute called {name}, so you can not set it.")
        print(f"Choices are:")
        for f in objDesc.fields:
            print(f"  {f.name}")
        return

    val = fromStr(valStr)

    enumType = field.enum_type
    if enumType and type(val) == str:
        # We've failed so far to convert this string into an enum, try to find it by reflection
        e = enumType.values_by_name.get(val)
        if e:
            val = e.number
        else:
            print(f"{name} doesn't have an enum called {val}, so you can not set it.")
            print(f"Choices are:")
            for f in enumType.values:
                print(f"  {f.name}")
            return

    # okay - try to read the value
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


targetNode = None


def onConnected(interface):
    """Callback invoked when we connect to a radio"""
    closeNow = False  # Should we drop the connection after we finish?
    try:
        global args
        print("Connected to radio")

        def getNode():
            """This operation could be expensive, so we try to cache the results"""
            global targetNode
            if not targetNode:
                targetNode = interface.getNode(args.destOrLocal)
            return targetNode

        if args.setlat or args.setlon or args.setalt:
            closeNow = True

            alt = 0
            lat = 0.0
            lon = 0.0
            time = 0  # always set time, but based on the local clock
            prefs = interface.localNode.radioConfig.preferences
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

            print("Setting device position")
            # can include lat/long/alt etc: latitude = 37.5, longitude = -122.1
            interface.sendPosition(lat, lon, alt, time)
            interface.localNode.writeConfig()
        elif not args.no_time:
            # We normally provide a current time to the mesh when we connect
            interface.sendPosition()

        if args.set_owner:
            closeNow = True
            print(f"Setting device owner to {args.set_owner}")
            getNode().setOwner(args.set_owner)

        if args.set_ham:
            closeNow = True
            print(
                f"Setting HAM ID to {args.set_ham} and turning off encryption")
            getNode().setOwner(args.set_ham, is_licensed=True)
            # Must turn off crypt on primary channel
            ch = getNode().channels[0]
            ch.settings.psk = fromPSK("none")
            print(f"Writing modified channels to device")
            getNode().writeChannel(0)

        if args.reboot:
            closeNow = True
            getNode().reboot()

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

        if args.gpio_wrb or args.gpio_rd or args.gpio_watch:
            rhc = remote_hardware.RemoteHardwareClient(interface)

            if args.gpio_wrb:
                bitmask = 0
                bitval = 0
                for wrpair in (args.gpio_wrb or []):
                    bitmask |= 1 << int(wrpair[0])
                    bitval |= int(wrpair[1]) << int(wrpair[0])
                print(
                    f"Writing GPIO mask 0x{bitmask:x} with value 0x{bitval:x} to {args.dest}")
                rhc.writeGPIOs(args.dest, bitmask, bitval)
                closeNow = True

            if args.gpio_rd:
                bitmask = int(args.gpio_rd, 16)
                print(f"Reading GPIO mask 0x{bitmask:x} from {args.dest}")

                def onResponse(packet):
                    """A closure to handle the response packet"""
                    hw = packet["decoded"]["remotehw"]
                    print(f'GPIO read response gpio_value={hw["gpioValue"]}')
                    sys.exit(0)  # Just force an exit (FIXME - ugly)

                rhc.readGPIOs(args.dest, bitmask, onResponse)

            if args.gpio_watch:
                bitmask = int(args.gpio_watch, 16)
                print(f"Watching GPIO mask 0x{bitmask:x} from {args.dest}")
                rhc.watchGPIOs(args.dest, bitmask)

        # handle settings
        if args.set:
            closeNow = True
            prefs = getNode().radioConfig.preferences

            # Handle the int/float/bool arguments
            for pref in args.set:
                setPref(
                    prefs, pref[0], pref[1])

            print("Writing modified preferences to device")
            getNode().writeConfig()

        if args.seturl:
            closeNow = True
            getNode().setURL(args.seturl)

        # handle changing channels

        if args.ch_add:
            closeNow = True
            n = getNode()
            ch = n.getChannelByName(args.ch_add)
            if ch:
                logging.error(
                    f"This node already has a '{args.ch_add}' channel - no changes.")
            else:
                ch = n.getDisabledChannel()
                if not ch:
                    raise Exception("No free channels were found")
                chs = channel_pb2.ChannelSettings()
                chs.psk = genPSKS256()
                chs.name = args.ch_add
                ch.settings.CopyFrom(chs)
                ch.role = channel_pb2.Channel.Role.SECONDARY
                print(f"Writing modified channels to device")
                n.writeChannel(ch.index)

        if args.ch_del:
            closeNow = True

            print(f"Deleting channel {channelIndex}")
            ch = getNode().deleteChannel(channelIndex)

        if args.ch_set or args.ch_longslow or args.ch_shortfast:
            closeNow = True

            ch = getNode().channels[channelIndex]

            enable = args.ch_enable  # should we enable this channel?

            if args.ch_longslow or args.ch_shortfast:
                if channelIndex != 0:
                    raise Exception(
                        "standard channel settings can only be applied to the PRIMARY channel")

                enable = True  # force enable

                def setSimpleChannel(modem_config):
                    """Set one of the simple modem_config only based channels"""

                    # Completely new channel settings
                    chs = channel_pb2.ChannelSettings()
                    chs.modem_config = modem_config
                    chs.psk = bytes([1])  # Use default channel psk 1

                    ch.settings.CopyFrom(chs)

                # handle the simple channel set commands
                if args.ch_longslow:
                    setSimpleChannel(
                        channel_pb2.ChannelSettings.ModemConfig.Bw125Cr48Sf4096)

                if args.ch_shortfast:
                    setSimpleChannel(
                        channel_pb2.ChannelSettings.ModemConfig.Bw500Cr45Sf128)

            # Handle the channel settings
            for pref in (args.ch_set or []):
                if pref[0] == "psk":
                    ch.settings.psk = fromPSK(pref[1])
                else:
                    setPref(ch.settings, pref[0], pref[1])
                enable = True  # If we set any pref, assume the user wants to enable the channel

            if enable:
                ch.role = channel_pb2.Channel.Role.PRIMARY if (
                    channelIndex == 0) else channel_pb2.Channel.Role.SECONDARY
            else:
                ch.role = channel_pb2.Channel.Role.DISABLED

            print(f"Writing modified channels to device")
            getNode().writeChannel(channelIndex)

        if args.info:
            print("")
            if not args.dest:  # If we aren't trying to talk to our local node, don't show it
                interface.showInfo()

            print("")
            getNode().showInfo()
            closeNow = True  # FIXME, for now we leave the link up while talking to remote nodes
            print("")

        if args.nodes:
            closeNow = True
            interface.showNodes()

        if args.qr:
            closeNow = True
            url = interface.localNode.getURL(includeAll=False)
            print(f"Primary channel URL {url}")
            qr = pyqrcode.create(url)
            print(qr.terminal())

        if have_tunnel and args.tunnel:
            from . import tunnel
            # Even if others said we could close, stay open if the user asked for a tunnel
            closeNow = False
            tunnel.Tunnel(interface, subnet=args.tunnel_net)

        # if the user didn't ask for serial debugging output, we might want to exit after we've done our operation
        if (not args.seriallog) and closeNow:
            interface.close()  # after running command then exit

    except Exception as ex:
        print(f"Aborting due to: {ex}")
        interface.close()  # close the connection now, so that our app exits


def onNode(node):
    """Callback invoked when the node DB changes"""
    print(f"Node changed: {node}")


def subscribe():
    """Subscribe to the topics the user probably wants to see, prints output to stdout"""
    pub.subscribe(onReceive, "meshtastic.receive")
    # pub.subscribe(onConnection, "meshtastic.connection")

    # We now call onConnected from main
    # pub.subscribe(onConnected, "meshtastic.connection.established")

    # pub.subscribe(onNode, "meshtastic.node")


def common():
    """Shared code for all of our command line wrappers"""
    global args
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    else:
        if args.ch_index is not None:
            global channelIndex
            channelIndex = int(args.ch_index)

        # Some commands require dest to be set, so we now use destOrAll/destOrLocal for more lenient commands
        if not args.dest:
            args.destOrAll = "^all"
            args.destOrLocal = "^local"
        else:
            args.destOrAll = args.dest
            args.destOrLocal = args.dest  # FIXME, temp hack for debugging remove

        if not args.seriallog:
            if args.noproto:
                args.seriallog = "stdout"
            else:
                args.seriallog = "none"  # assume no debug output in this case

        if args.deprecated != None:
            logging.error(
                'This option has been deprecated, see help below for the correct replacement...')
            parser.print_help(sys.stderr)
            sys.exit(1)
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
                logfile = open(args.seriallog, 'w+',
                               buffering=1)  # line buffering

            subscribe()
            if args.ble:
                client = BLEInterface(args.ble, debugOut=logfile)
            elif args.host:
                client = TCPInterface(
                    args.host, debugOut=logfile, noProto=args.noproto)
            else:
                client = SerialInterface(
                    args.port, debugOut=logfile, noProto=args.noproto)

            # We assume client is fully connected now
            onConnected(client)

            if args.noproto:  # loop until someone presses ctrlc
                while True:
                    time.sleep(1000)

        # don't call exit, background threads might be running still
        # sys.exit(0)


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
        help="Log device serial output to either 'stdout', 'none' or a filename to append to.")

    parser.add_argument("--info", help="Read and display the radio config information",
                        action="store_true")

    parser.add_argument("--nodes", help="Print Node List in a pretty formatted table",
                        action="store_true")

    parser.add_argument("--qr", help="Display the QR code that corresponds to the current channel",
                        action="store_true")

    parser.add_argument(
        "--set", help="Set a preferences field", nargs=2, action='append')

    parser.add_argument(
        "--seturl", help="Set a channel URL", action="store")

    parser.add_argument(
        "--ch-index", help="Set the specified channel index", action="store")

    parser.add_argument(
        "--ch-add", help="Add a secondary channel, you must specify a channel name", default=None)

    parser.add_argument(
        "--ch-del", help="Delete the ch-index channel", action='store_true')

    parser.add_argument(
        "--ch-enable", help="Enable the specified channel", action="store_true", dest="ch_enable")

    parser.add_argument(
        "--ch-disable", help="Disable the specified channel", action="store_false", dest="ch_enable")

    parser.add_argument(
        "--ch-set", help="Set a channel parameter", nargs=2, action='append')

    parser.add_argument(
        "--ch-longslow", help="Change to the standard long-range (but slow) channel", action='store_true')

    parser.add_argument(
        "--ch-shortfast", help="Change to the standard fast (but short range) channel", action='store_true')

    parser.add_argument(
        "--set-owner", help="Set device owner name", action="store")

    parser.add_argument(
        "--set-ham", help="Set licensed HAM ID and turn off encryption", action="store")

    parser.add_argument(
        "--dest", help="The destination node id for any sent commands, if not set '^all' or '^local' is assumed as appropriate", default=None)

    parser.add_argument(
        "--sendtext", help="Send a text message")

    parser.add_argument(
        "--sendping", help="Send a ping message (which requests a reply)", action="store_true")

    parser.add_argument(
        "--reboot", help="Tell the destination node to reboot", action="store_true")

    # parser.add_argument(
    #    "--repeat", help="Normally the send commands send only one message, use this option to request repeated sends")

    parser.add_argument(
        "--reply", help="Reply to received messages",
        action="store_true")

    parser.add_argument(
        "--gpio-wrb", nargs=2, help="Set a particlar GPIO # to 1 or 0", action='append')

    parser.add_argument(
        "--gpio-rd", help="Read from a GPIO mask")

    parser.add_argument(
        "--gpio-watch", help="Start watching a GPIO mask for changes")

    parser.add_argument(
        "--no-time", help="Suppress sending the current time to the mesh", action="store_true")

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

    parser.add_argument('--setchan', dest='deprecated', nargs=2, action='append',
                        help='Deprecated, use "--ch-set param value" instead')
    parser.add_argument('--set-router', dest='deprecated',
                        action='store_true', help='Deprecated, use "--set is_router true" instead')
    parser.add_argument('--unset-router', dest='deprecated',
                        action='store_false', help='Deprecated, use "--set is_router false" instead')

    if have_tunnel:
        parser.add_argument('--tunnel',
                            action='store_true', help="Create a TUN tunnel device for forwarding IP packets over the mesh")
        parser.add_argument(
            "--subnet", dest='tunnel_net', help="Read from a GPIO mask", default=None)

    parser.set_defaults(deprecated=None)

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
