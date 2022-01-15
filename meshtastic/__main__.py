#!python3
""" Main Meshtastic
"""

import argparse
import platform
import logging
import os
import sys
import time
import yaml
from pubsub import pub
import pyqrcode
import pkg_resources
import meshtastic.util
import meshtastic.test
from meshtastic import remote_hardware
from meshtastic.ble_interface import BLEInterface
from meshtastic import portnums_pb2, channel_pb2, radioconfig_pb2
from meshtastic.globals import Globals
from meshtastic.__init__ import BROADCAST_ADDR

def onReceive(packet, interface):
    """Callback invoked when a packet arrives"""
    our_globals = Globals.getInstance()
    args = our_globals.get_args()
    try:
        d = packet.get('decoded')
        logging.debug(f'in onReceive() d:{d}')

        # Exit once we receive a reply
        if args and args.sendtext and packet["to"] == interface.myInfo.my_node_num and d["portnum"] == portnums_pb2.PortNum.TEXT_MESSAGE_APP:
            interface.close()  # after running command then exit

        # Reply to every received message with some stats
        if args and args.reply:
            msg = d.get('text')
            if msg:
                rxSnr = packet['rxSnr']
                hopLimit = packet['hopLimit']
                print(f"message: {msg}")
                reply = f"got msg \'{msg}\' with rxSnr: {rxSnr} and hopLimit: {hopLimit}"
                print("Sending reply: ", reply)
                interface.sendText(reply)

    except Exception as ex:
        print(f'Warning: There is no field {ex} in the packet.')


def onConnection(interface, topic=pub.AUTO_TOPIC): # pylint: disable=W0613
    """Callback invoked when we connect/disconnect from a radio"""
    print(f"Connection changed: {topic.getName()}")


def getPref(attributes, name):
    """Get a channel or preferences value"""

    camel_name = meshtastic.util.snake_to_camel(name)
    # Note: protobufs has the keys in snake_case, so snake internally
    snake_name = meshtastic.util.camel_to_snake(name)
    logging.debug(f'snake_name:{snake_name} camel_name:{camel_name}')
    logging.debug(f'use camel:{Globals.getInstance().get_camel_case()}')

    objDesc = attributes.DESCRIPTOR
    field = objDesc.fields_by_name.get(snake_name)
    if not field:
        if Globals.getInstance().get_camel_case():
            print(f"{attributes.__class__.__name__} does not have an attribute called {camel_name}, so you can not get it.")
        else:
            print(f"{attributes.__class__.__name__} does not have an attribute called {snake_name}, so you can not get it.")
        print(f"Choices in sorted order are:")
        names = []
        for f in objDesc.fields:
            tmp_name = f'{f.name}'
            if Globals.getInstance().get_camel_case():
                tmp_name = meshtastic.util.snake_to_camel(tmp_name)
            names.append(tmp_name)
        for temp_name in sorted(names):
            print(f"    {temp_name}")
        return

    # read the value
    val = getattr(attributes, snake_name)

    if Globals.getInstance().get_camel_case():
        print(f"{camel_name}: {str(val)}")
        logging.debug(f"{camel_name}: {str(val)}")
    else:
        print(f"{snake_name}: {str(val)}")
        logging.debug(f"{snake_name}: {str(val)}")


def setPref(attributes, name, valStr):
    """Set a channel or preferences value"""

    snake_name = meshtastic.util.camel_to_snake(name)
    camel_name = meshtastic.util.snake_to_camel(name)
    logging.debug(f'snake_name:{snake_name}')
    logging.debug(f'camel_name:{camel_name}')

    objDesc = attributes.DESCRIPTOR
    field = objDesc.fields_by_name.get(snake_name)
    if not field:
        if Globals.getInstance().get_camel_case():
            print(f"{attributes.__class__.__name__} does not have an attribute called {camel_name}, so you can not set it.")
        else:
            print(f"{attributes.__class__.__name__} does not have an attribute called {snake_name}, so you can not set it.")
        print(f"Choices in sorted order are:")
        names = []
        for f in objDesc.fields:
            tmp_name = f'{f.name}'
            if Globals.getInstance().get_camel_case():
                tmp_name = meshtastic.util.snake_to_camel(tmp_name)
            names.append(tmp_name)
        for temp_name in sorted(names):
            print(f"    {temp_name}")
        return

    val = meshtastic.util.fromStr(valStr)
    logging.debug(f'valStr:{valStr} val:{val}')

    enumType = field.enum_type
    # pylint: disable=C0123
    if enumType and type(val) == str:
        # We've failed so far to convert this string into an enum, try to find it by reflection
        e = enumType.values_by_name.get(val)
        if e:
            val = e.number
        else:
            if Globals.getInstance().get_camel_case():
                print(f"{camel_name} does not have an enum called {val}, so you can not set it.")
            else:
                print(f"{snake_name} does not have an enum called {val}, so you can not set it.")
            print(f"Choices in sorted order are:")
            names = []
            for f in enumType.values:
                tmp_name = f'{f.name}'
                if Globals.getInstance().get_camel_case():
                    tmp_name = meshtastic.util.snake_to_camel(tmp_name)
                names.append(name)
            for temp_name in sorted(names):
                print(f"    {temp_name}")
            return
    try:
        setattr(attributes, snake_name, val)
    except TypeError:
        # The setter didn't like our arg type guess try again as a string
        setattr(attributes, snake_name, valStr)

    if Globals.getInstance().get_camel_case():
        print(f"Set {camel_name} to {valStr}")
    else:
        print(f"Set {snake_name} to {valStr}")


def onConnected(interface):
    """Callback invoked when we connect to a radio"""
    closeNow = False  # Should we drop the connection after we finish?
    try:
        our_globals = Globals.getInstance()
        args = our_globals.get_args()

        # do not print this line if we are exporting the config
        if not args.export_config:
            print("Connected to radio")

        if args.setlat or args.setlon or args.setalt:
            closeNow = True

            alt = 0
            lat = 0.0
            lon = 0.0
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
            interface.sendPosition(lat, lon, alt)
            interface.localNode.writeConfig()
        elif not args.no_time:
            # We normally provide a current time to the mesh when we connect
            interface.sendPosition()

        if args.set_owner:
            closeNow = True
            print(f"Setting device owner to {args.set_owner}")
            interface.getNode(args.dest).setOwner(args.set_owner)

        if args.pos_fields:
            # If --pos-fields invoked with args, set position fields
            closeNow = True
            prefs = interface.getNode(args.dest).radioConfig.preferences
            allFields = 0

            try:
                for field in args.pos_fields:
                    v_field = radioconfig_pb2.PositionFlags.Value(field)
                    allFields |= v_field

            except ValueError:
                print("ERROR: supported position fields are:")
                print(radioconfig_pb2.PositionFlags.keys())
                print("If no fields are specified, will read and display current value.")

            else:
                print(f"Setting position fields to {allFields}")
                setPref(prefs, 'position_flags', f'{allFields:d}')
                print("Writing modified preferences to device")
                interface.getNode(args.dest).writeConfig()

        elif args.pos_fields is not None:
            # If --pos-fields invoked without args, read and display current value
            closeNow = True
            prefs = interface.getNode(args.dest).radioConfig.preferences

            fieldNames = []
            for bit in radioconfig_pb2.PositionFlags.values():
                if prefs.position_flags & bit:
                    fieldNames.append(radioconfig_pb2.PositionFlags.Name(bit))
            print(' '.join(fieldNames))

        if args.set_team:
            closeNow = True
            try:
                v_team = meshtastic.mesh_pb2.Team.Value(args.set_team.upper())
            except ValueError:
                v_team = 0
                print(f"ERROR: Team \'{args.set_team}\' not found.")
                print("Try a team name from the sorted list below, or use 'CLEAR' for unaffiliated:")
                print(sorted(meshtastic.mesh_pb2.Team.keys()))
            else:
                print(f"Setting team to {meshtastic.mesh_pb2.Team.Name(v_team)}")
                interface.getNode(args.dest).setOwner(team=v_team)

        if args.set_ham:
            closeNow = True
            print(f"Setting Ham ID to {args.set_ham} and turning off encryption")
            interface.getNode(args.dest).setOwner(args.set_ham, is_licensed=True)
            # Must turn off encryption on primary channel
            interface.getNode(args.dest).turnOffEncryptionOnPrimaryChannel()

        if args.reboot:
            closeNow = True
            interface.getNode(args.dest).reboot()

        if args.sendtext:
            closeNow = True
            channelIndex = 0
            if args.ch_index is not None:
                channelIndex = int(args.ch_index)
            ch = interface.localNode.getChannelByChannelIndex(channelIndex)
            logging.debug(f'ch:{ch}')
            if ch and ch.role != channel_pb2.Channel.Role.DISABLED:
                print(f"Sending text message {args.sendtext} to {args.dest} on channelIndex:{channelIndex}")
                interface.sendText(args.sendtext, args.dest, wantAck=True, channelIndex=channelIndex)
            else:
                meshtastic.util.our_exit(f"Warning: {channelIndex} is not a valid channel. Channel must not be DISABLED.")

        if args.sendping:
            payload = str.encode("test string")
            print(f"Sending ping message to {args.dest}")
            interface.sendData(payload, args.dest, portNum=portnums_pb2.PortNum.REPLY_APP,
                               wantAck=True, wantResponse=True)

        if args.gpio_wrb or args.gpio_rd or args.gpio_watch:
            if args.dest == BROADCAST_ADDR:
                meshtastic.util.our_exit("Warning: Must use a destination node ID.")
            else:
                rhc = remote_hardware.RemoteHardwareClient(interface)

                if args.gpio_wrb:
                    bitmask = 0
                    bitval = 0
                    for wrpair in (args.gpio_wrb or []):
                        bitmask |= 1 << int(wrpair[0])
                        bitval |= int(wrpair[1]) << int(wrpair[0])
                    print(f"Writing GPIO mask 0x{bitmask:x} with value 0x{bitval:x} to {args.dest}")
                    rhc.writeGPIOs(args.dest, bitmask, bitval)
                    closeNow = True

                if args.gpio_rd:
                    bitmask = int(args.gpio_rd, 16)
                    print(f"Reading GPIO mask 0x{bitmask:x} from {args.dest}")
                    interface.mask = bitmask
                    rhc.readGPIOs(args.dest, bitmask, None)
                    if not interface.noProto:
                        # wait up to X seconds for a response
                        for _ in range(10):
                            time.sleep(1)
                            if interface.gotResponse:
                                break
                    logging.debug(f'end of gpio_rd')

                if args.gpio_watch:
                    bitmask = int(args.gpio_watch, 16)
                    print(f"Watching GPIO mask 0x{bitmask:x} from {args.dest}. Press ctrl-c to exit")
                    while True:
                        rhc.watchGPIOs(args.dest, bitmask)
                        time.sleep(1)

        # handle settings
        if args.set:
            closeNow = True
            prefs = interface.getNode(args.dest).radioConfig.preferences

            # Handle the int/float/bool arguments
            for pref in args.set:
                setPref(prefs, pref[0], pref[1])

            print("Writing modified preferences to device")
            interface.getNode(args.dest).writeConfig()

        if args.configure:
            with open(args.configure[0], encoding='utf8') as file:
                configuration = yaml.safe_load(file)
                closeNow = True

                if 'owner' in configuration:
                    print(f"Setting device owner to {configuration['owner']}")
                    interface.getNode(args.dest).setOwner(configuration['owner'])

                if 'channel_url' in configuration:
                    print("Setting channel url to", configuration['channel_url'])
                    interface.getNode(args.dest).setURL(configuration['channel_url'])

                if 'channelUrl' in configuration:
                    print("Setting channel url to", configuration['channelUrl'])
                    interface.getNode(args.dest).setURL(configuration['channelUrl'])

                if 'location' in configuration:
                    alt = 0
                    lat = 0.0
                    lon = 0.0
                    prefs = interface.localNode.radioConfig.preferences

                    if 'alt' in configuration['location']:
                        alt = int(configuration['location']['alt'])
                        prefs.fixed_position = True
                        print(f"Fixing altitude at {alt} meters")
                    if 'lat' in configuration['location']:
                        lat = float(configuration['location']['lat'])
                        prefs.fixed_position = True
                        print(f"Fixing latitude at {lat} degrees")
                    if 'lon' in configuration['location']:
                        lon = float(configuration['location']['lon'])
                        prefs.fixed_position = True
                        print(f"Fixing longitude at {lon} degrees")
                    print("Setting device position")
                    interface.sendPosition(lat, lon, alt)
                    interface.localNode.writeConfig()

                if 'user_prefs' in configuration:
                    prefs = interface.getNode(args.dest).radioConfig.preferences
                    for pref in configuration['user_prefs']:
                        setPref(prefs, pref, str(configuration['user_prefs'][pref]))
                    print("Writing modified preferences to device")
                    interface.getNode(args.dest).writeConfig()

                if 'userPrefs' in configuration:
                    prefs = interface.getNode(args.dest).radioConfig.preferences
                    for pref in configuration['userPrefs']:
                        setPref(prefs, pref, str(configuration['userPrefs'][pref]))
                    print("Writing modified preferences to device")
                    interface.getNode(args.dest).writeConfig()

        if args.export_config:
            # export the configuration (the opposite of '--configure')
            closeNow = True
            export_config(interface)

        if args.seturl:
            closeNow = True
            interface.getNode(args.dest).setURL(args.seturl)

        # handle changing channels

        if args.ch_add:
            closeNow = True
            if len(args.ch_add) > 10:
                meshtastic.util.our_exit("Warning: Channel name must be shorter. Channel not added.")
            n = interface.getNode(args.dest)
            ch = n.getChannelByName(args.ch_add)
            if ch:
                meshtastic.util.our_exit(f"Warning: This node already has a '{args.ch_add}' channel. No changes were made.")
            else:
                # get the first channel that is disabled (i.e., available)
                ch = n.getDisabledChannel()
                if not ch:
                    meshtastic.util.our_exit("Warning: No free channels were found")
                chs = channel_pb2.ChannelSettings()
                chs.psk = meshtastic.util.genPSK256()
                chs.name = args.ch_add
                ch.settings.CopyFrom(chs)
                ch.role = channel_pb2.Channel.Role.SECONDARY
                print(f"Writing modified channels to device")
                n.writeChannel(ch.index)

        if args.ch_del:
            closeNow = True

            channelIndex = our_globals.get_channel_index()
            if channelIndex is None:
                meshtastic.util.our_exit("Warning: Need to specify '--ch-index' for '--ch-del'.", 1)
            else:
                if channelIndex == 0:
                    meshtastic.util.our_exit("Warning: Cannot delete primary channel.", 1)
                else:
                    print(f"Deleting channel {channelIndex}")
                    ch = interface.getNode(args.dest).deleteChannel(channelIndex)

        ch_changes = [args.ch_longslow, args.ch_longfast,
                      args.ch_mediumslow, args.ch_mediumfast,
                      args.ch_shortslow, args.ch_shortfast]
        any_primary_channel_changes = any(x for x in ch_changes)
        if args.ch_set or any_primary_channel_changes or args.ch_enable or args.ch_disable:
            closeNow = True

            channelIndex = our_globals.get_channel_index()
            if channelIndex is None:
                if any_primary_channel_changes:
                    # we assume that they want the primary channel if they're setting range values
                    channelIndex = 0
                else:
                    meshtastic.util.our_exit("Warning: Need to specify '--ch-index'.", 1)
            ch = interface.getNode(args.dest).channels[channelIndex]

            if any_primary_channel_changes or args.ch_enable or args.ch_disable:

                if channelIndex == 0 and not any_primary_channel_changes:
                    meshtastic.util.our_exit("Warning: Cannot enable/disable PRIMARY channel.")

                if channelIndex != 0:
                    if any_primary_channel_changes:
                        meshtastic.util.our_exit("Warning: Standard channel settings can only be applied to the PRIMARY channel")

                enable = True  # default to enable
                if args.ch_enable:
                    enable = True
                if args.ch_disable:
                    enable = False

                def setSimpleChannel(modem_config):
                    """Set one of the simple modem_config only based channels"""

                    # Completely new channel settings
                    chs = channel_pb2.ChannelSettings()
                    chs.modem_config = modem_config
                    chs.psk = bytes([1])  # Use default channel psk 1

                    ch.settings.CopyFrom(chs)

                # handle the simple channel set commands
                if args.ch_longslow:
                    setSimpleChannel(channel_pb2.ChannelSettings.ModemConfig.Bw125Cr48Sf4096)

                if args.ch_longfast:
                    setSimpleChannel(channel_pb2.ChannelSettings.ModemConfig.Bw31_25Cr48Sf512)

                if args.ch_mediumslow:
                    setSimpleChannel(channel_pb2.ChannelSettings.ModemConfig.Bw250Cr46Sf2048)

                if args.ch_mediumfast:
                    setSimpleChannel(channel_pb2.ChannelSettings.ModemConfig.Bw250Cr47Sf1024)

                if args.ch_shortslow:
                    setSimpleChannel(channel_pb2.ChannelSettings.ModemConfig.Bw125Cr45Sf128)

                if args.ch_shortfast:
                    setSimpleChannel(channel_pb2.ChannelSettings.ModemConfig.Bw500Cr45Sf128)

            # Handle the channel settings
            for pref in (args.ch_set or []):
                if pref[0] == "psk":
                    ch.settings.psk = meshtastic.util.fromPSK(pref[1])
                else:
                    setPref(ch.settings, pref[0], pref[1])
                enable = True  # If we set any pref, assume the user wants to enable the channel

            if enable:
                ch.role = channel_pb2.Channel.Role.PRIMARY if (
                    channelIndex == 0) else channel_pb2.Channel.Role.SECONDARY
            else:
                ch.role = channel_pb2.Channel.Role.DISABLED

            print(f"Writing modified channels to device")
            interface.getNode(args.dest).writeChannel(channelIndex)

        if args.info:
            print("")
            # If we aren't trying to talk to our local node, don't show it
            if args.dest == BROADCAST_ADDR:
                interface.showInfo()

            print("")
            interface.getNode(args.dest).showInfo()
            closeNow = True  # FIXME, for now we leave the link up while talking to remote nodes
            print("")

        if args.get:
            closeNow = True
            prefs = interface.getNode(args.dest).radioConfig.preferences

            # Handle the int/float/bool arguments
            for pref in args.get:
                getPref(prefs, pref[0])

            print("Completed getting preferences")

        if args.nodes:
            closeNow = True
            interface.showNodes()

        if args.qr:
            closeNow = True
            url = interface.localNode.getURL(includeAll=False)
            print(f"Primary channel URL {url}")
            qr = pyqrcode.create(url)
            print(qr.terminal())

        have_tunnel = platform.system() == 'Linux'
        if have_tunnel and args.tunnel:
            # pylint: disable=C0415
            from . import tunnel
            # Even if others said we could close, stay open if the user asked for a tunnel
            closeNow = False
            if interface.noProto:
                logging.warning(f"Not starting Tunnel - disabled by noProto")
            else:
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


def export_config(interface):
    """used in--export-config"""
    owner = interface.getLongName()
    channel_url = interface.localNode.getURL()
    myinfo = interface.getMyNodeInfo()
    pos = myinfo.get('position')
    lat = None
    lon = None
    alt = None
    if pos:
        lat = pos.get('latitude')
        lon = pos.get('longitude')
        alt = pos.get('altitude')

    config = "# start of Meshtastic configure yaml\n"
    if owner:
        config += f"owner: {owner}\n\n"
    if channel_url:
        if Globals.getInstance().get_camel_case():
            config += f"channelUrl: {channel_url}\n\n"
        else:
            config += f"channel_url: {channel_url}\n\n"
    if lat or lon or alt:
        config += "location:\n"
        if lat:
            config += f"  lat: {lat}\n"
        if lon:
            config += f"  lon: {lon}\n"
        if alt:
            config += f"  alt: {alt}\n"
        config += "\n"
    preferences = f'{interface.localNode.radioConfig.preferences}'
    prefs = preferences.splitlines()
    if prefs:
        if Globals.getInstance().get_camel_case():
            config += "userPrefs:\n"
        else:
            config += "user_prefs:\n"
        for pref in prefs:
            if Globals.getInstance().get_camel_case():
                # Note: This may not work if the value has '_'
                config += f"  {meshtastic.util.snake_to_camel(meshtastic.util.quoteBooleans(pref))}\n"
            else:
                config += f"  {meshtastic.util.quoteBooleans(pref)}\n"
    print(config)
    return config


def common():
    """Shared code for all of our command line wrappers"""
    logfile = None
    our_globals = Globals.getInstance()
    args = our_globals.get_args()
    parser = our_globals.get_parser()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='%(levelname)s file:%(filename)s %(funcName)s line:%(lineno)s %(message)s')

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        meshtastic.util.our_exit("", 1)
    else:
        if args.support:
            meshtastic.util.support_info()
            meshtastic.util.our_exit("", 0)

        if args.ch_index is not None:
            channelIndex = int(args.ch_index)
            our_globals.set_channel_index(channelIndex)

        if not args.dest:
            args.dest = BROADCAST_ADDR

        if not args.seriallog:
            if args.noproto:
                args.seriallog = "stdout"
            else:
                args.seriallog = "none"  # assume no debug output in this case

        if args.deprecated is not None:
            logging.error(
                'This option has been deprecated, see help below for the correct replacement...')
            parser.print_help(sys.stderr)
            meshtastic.util.our_exit('', 1)
        elif args.test:
            result = meshtastic.test.testAll()
            if not result:
                meshtastic.util.our_exit("Warning: Test was not successful.")
            else:
                meshtastic.util.our_exit("Test was a success.", 0)
        else:
            if args.seriallog == "stdout":
                logfile = sys.stdout
            elif args.seriallog == "none":
                args.seriallog = None
                logging.debug("Not logging serial output")
                logfile = None
            else:
                logging.info(f"Logging serial output to {args.seriallog}")
                # Note: using "line buffering"
                # pylint: disable=R1732
                logfile = open(args.seriallog, 'w+', buffering=1, encoding='utf8')
                our_globals.set_logfile(logfile)

            subscribe()
            if args.ble:
                client = BLEInterface(args.ble, debugOut=logfile, noProto=args.noproto)
            elif args.host:
                client = meshtastic.tcp_interface.TCPInterface(args.host, debugOut=logfile, noProto=args.noproto)
            else:
                try:
                    client = meshtastic.serial_interface.SerialInterface(args.port, debugOut=logfile, noProto=args.noproto)
                except PermissionError as ex:
                    username = os.getlogin()
                    message = "Permission Error:\n"
                    message += "  Need to add yourself to the 'dialout' group by running:\n"
                    message += f"     sudo usermod -a -G dialout {username}\n"
                    message += "  After running that command, log out and re-login for it to take effect.\n"
                    message += f"Error was:{ex}"
                    meshtastic.util.our_exit(message)

            # We assume client is fully connected now
            onConnected(client)

            have_tunnel = platform.system() == 'Linux'
            if args.noproto or args.reply or (have_tunnel and args.tunnel):  # loop until someone presses ctrlc
                while True:
                    time.sleep(1000)

        # don't call exit, background threads might be running still
        # sys.exit(0)


def initParser():
    """Initialize the command line argument parsing."""
    our_globals = Globals.getInstance()
    parser = our_globals.get_parser()
    args = our_globals.get_args()

    parser.add_argument(
        "--configure",
        help="Specify a path to a yaml(.yml) file containing the desired settings for the connected device.",
        action='append')

    parser.add_argument(
        "--export-config",
        help="Export the configuration in yaml(.yml) format.",
        action='store_true')

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
        "--get", help=("Get a preferences field. Use an invalid field such as '0' to get a list of all fields."
                       " Can use either snake_case or camelCase format. (ex: 'ls_secs' or 'lsSecs')"),
                       nargs=1, action='append')

    parser.add_argument(
        "--set", help="Set a preferences field. Can use either snake_case or camelCase format. (ex: 'ls_secs' or 'lsSecs')", nargs=2, action='append')

    parser.add_argument(
        "--seturl", help="Set a channel URL", action="store")

    parser.add_argument(
        "--ch-index", help="Set the specified channel index. Channels start at 0 (0 is the PRIMARY channel).", action="store")

    parser.add_argument(
        "--ch-add", help="Add a secondary channel, you must specify a channel name", default=None)

    parser.add_argument(
        "--ch-del", help="Delete the ch-index channel", action='store_true')

    parser.add_argument(
        "--ch-enable", help="Enable the specified channel", action="store_true", dest="ch_enable", default=False)

    # Note: We are doing a double negative here (Do we want to disable? If ch_disable==True, then disable.)
    parser.add_argument(
        "--ch-disable", help="Disable the specified channel", action="store_true", dest="ch_disable", default=False)

    parser.add_argument(
        "--ch-set", help="Set a channel parameter", nargs=2, action='append')

    parser.add_argument(
        "--ch-longslow", help="Change to the long-range and slow channel", action='store_true')

    parser.add_argument(
        "--ch-longfast", help="Change to the long-range and fast channel", action='store_true')

    parser.add_argument(
        "--ch-mediumslow", help="Change to the medium-range and slow channel", action='store_true')

    parser.add_argument(
        "--ch-mediumfast", help="Change to the medium-range and fast channel", action='store_true')

    parser.add_argument(
        "--ch-shortslow", help="Change to the short-range and slow channel", action='store_true')

    parser.add_argument(
        "--ch-shortfast", help="Change to the short-range and fast channel", action='store_true')


    parser.add_argument(
        "--set-owner", help="Set device owner name", action="store")

    parser.add_argument(
        "--set-team", help="Set team affiliation (an invalid team will list valid values)", action="store")

    parser.add_argument(
        "--set-ham", help="Set licensed Ham ID and turn off encryption", action="store")

    parser.add_argument(
        "--dest", help="The destination node id for any sent commands, if not set '^all' or '^local' is assumed as appropriate", default=None)

    parser.add_argument(
        "--sendtext", help="Send a text message. Can specify a destination '--dest' and/or channel index '--ch-index'.")

    parser.add_argument(
        "--sendping", help="Send a ping message (which requests a reply)", action="store_true")

    parser.add_argument(
        "--reboot", help="Tell the destination node to reboot", action="store_true")

    parser.add_argument(
        "--reply", help="Reply to received messages",
        action="store_true")

    parser.add_argument(
        "--gpio-wrb", nargs=2, help="Set a particular GPIO # to 1 or 0", action='append')

    parser.add_argument(
        "--gpio-rd", help="Read from a GPIO mask (ex: '0x10')")

    parser.add_argument(
        "--gpio-watch", help="Start watching a GPIO mask for changes (ex: '0x10')")

    parser.add_argument(
        "--no-time", help="Suppress sending the current time to the mesh", action="store_true")

    parser.add_argument(
        "--setalt", help="Set device altitude (allows use without GPS)")

    parser.add_argument(
        "--setlat", help="Set device latitude (allows use without GPS)")

    parser.add_argument(
        "--setlon", help="Set device longitude (allows use without GPS)")

    parser.add_argument(
        "--pos-fields", help="Specify fields to send when sending a position. Use no argument for a list of valid values. "\
                             "Can pass multiple values as a space separated list like "\
                             "this: '--pos-fields POS_ALTITUDE POS_ALT_MSL'",
        nargs="*", action="store")

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

    have_tunnel = platform.system() == 'Linux'
    if have_tunnel:
        parser.add_argument('--tunnel', action='store_true',
                            help="Create a TUN tunnel device for forwarding IP packets over the mesh")
        parser.add_argument("--subnet", dest='tunnel_net',
                            help="Sets the local-end subnet address for the TUN IP bridge. (ex: 10.115' which is the default)",
                            default=None)

    parser.set_defaults(deprecated=None)

    the_version = pkg_resources.get_distribution("meshtastic").version
    parser.add_argument('--version', action='version', version=f"{the_version}")

    parser.add_argument(
        "--support", action='store_true', help="Show support info (useful when troubleshooting an issue)")

    args = parser.parse_args()
    our_globals.set_args(args)
    our_globals.set_parser(parser)


def main():
    """Perform command line meshtastic operations"""
    our_globals = Globals.getInstance()
    parser = argparse.ArgumentParser()
    our_globals.set_parser(parser)
    initParser()
    common()
    logfile = our_globals.get_logfile()
    if logfile:
        logfile.close()



def tunnelMain():
    """Run a meshtastic IP tunnel"""
    our_globals = Globals.getInstance()
    parser = argparse.ArgumentParser()
    our_globals.set_parser(parser)
    initParser()
    args = our_globals.get_args()
    args.tunnel = True
    our_globals.set_args(args)
    common()


if __name__ == "__main__":
    main()
