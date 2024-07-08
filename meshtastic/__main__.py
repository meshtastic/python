#!python3
""" Main Meshtastic
"""

import argparse
import logging
import os
import platform
import sys
import time

import pyqrcode # type: ignore[import-untyped]
import yaml
from google.protobuf.json_format import MessageToDict
from pubsub import pub # type: ignore[import-untyped]

import meshtastic.test
import meshtastic.util
from meshtastic import mt_config
from meshtastic.protobuf import channel_pb2, config_pb2, portnums_pb2
from meshtastic import remote_hardware, BROADCAST_ADDR
from meshtastic.version import get_active_version
from meshtastic.ble_interface import BLEInterface
from meshtastic.mesh_interface import MeshInterface

def onReceive(packet, interface):
    """Callback invoked when a packet arrives"""
    args = mt_config.args
    try:
        d = packet.get("decoded")
        logging.debug(f"in onReceive() d:{d}")

        # Exit once we receive a reply
        if (
            args
            and args.sendtext
            and packet["to"] == interface.myInfo.my_node_num
            and d["portnum"] == portnums_pb2.PortNum.TEXT_MESSAGE_APP
        ):
            interface.close()  # after running command then exit

        # Reply to every received message with some stats
        if d is not None and args and args.reply:
            msg = d.get("text")
            if msg:
                rxSnr = packet["rxSnr"]
                hopLimit = packet["hopLimit"]
                print(f"message: {msg}")
                reply = f"got msg '{msg}' with rxSnr: {rxSnr} and hopLimit: {hopLimit}"
                print("Sending reply: ", reply)
                interface.sendText(reply)

    except Exception as ex:
        print(f"Warning: There is no field {ex} in the packet.")


def onConnection(interface, topic=pub.AUTO_TOPIC):  # pylint: disable=W0613
    """Callback invoked when we connect/disconnect from a radio"""
    print(f"Connection changed: {topic.getName()}")

def checkChannel(interface: MeshInterface, channelIndex: int) -> bool:
    """Given an interface and channel index, return True if that channel is non-disabled on the local node"""
    ch = interface.localNode.getChannelByChannelIndex(channelIndex)
    logging.debug(f"ch:{ch}")
    return (ch and ch.role != channel_pb2.Channel.Role.DISABLED)

def getPref(node, comp_name):
    """Get a channel or preferences value"""

    name = splitCompoundName(comp_name)
    wholeField = name[0] == name[1]  # We want the whole field

    camel_name = meshtastic.util.snake_to_camel(name[1])
    # Note: protobufs has the keys in snake_case, so snake internally
    snake_name = meshtastic.util.camel_to_snake(name[1])
    logging.debug(f"snake_name:{snake_name} camel_name:{camel_name}")
    logging.debug(f"use camel:{mt_config.camel_case}")

    # First validate the input
    localConfig = node.localConfig
    moduleConfig = node.moduleConfig
    found = False
    for config in [localConfig, moduleConfig]:
        objDesc = config.DESCRIPTOR
        config_type = objDesc.fields_by_name.get(name[0])
        pref = False
        if config_type:
            pref = config_type.message_type.fields_by_name.get(snake_name)
            if pref or wholeField:
                found = True
                break

    if not found:
        if mt_config.camel_case:
            print(
                f"{localConfig.__class__.__name__} and {moduleConfig.__class__.__name__} do not have an attribute {snake_name}."
            )
        else:
            print(
                f"{localConfig.__class__.__name__} and {moduleConfig.__class__.__name__} do not have attribute {snake_name}."
            )
        print("Choices are...")
        printConfig(localConfig)
        printConfig(moduleConfig)
        return False

    # Check if we need to request the config
    if len(config.ListFields()) != 0:
        # read the value
        config_values = getattr(config, config_type.name)
        if not wholeField:
            pref_value = getattr(config_values, pref.name)
            if mt_config.camel_case:
                print(f"{str(config_type.name)}.{camel_name}: {str(pref_value)}")
                logging.debug(
                    f"{str(config_type.name)}.{camel_name}: {str(pref_value)}"
                )
            else:
                print(f"{str(config_type.name)}.{snake_name}: {str(pref_value)}")
                logging.debug(
                    f"{str(config_type.name)}.{snake_name}: {str(pref_value)}"
                )
        else:
            print(f"{str(config_type.name)}:\n{str(config_values)}")
            logging.debug(f"{str(config_type.name)}: {str(config_values)}")
    else:
        # Always show whole field for remote node
        node.requestConfig(config_type)

    return True


def splitCompoundName(comp_name):
    """Split compound (dot separated) preference name into parts"""
    name = comp_name.split(".")
    if len(name) < 2:
        name[0] = comp_name
        name.append(comp_name)
    return name

def traverseConfig(config_root, config, interface_config):
    """Iterate through current config level preferences and either traverse deeper if preference is a dict or set preference"""
    snake_name = meshtastic.util.camel_to_snake(config_root)
    for pref in config:
        pref_name = f"{snake_name}.{pref}"
        if isinstance(config[pref], dict):
            traverseConfig(pref_name, config[pref], interface_config)
        else:
            setPref(
                interface_config,
                pref_name,
                str(config[pref])
            )

    return True

def setPref(config, comp_name, valStr) -> bool:
    """Set a channel or preferences value"""

    name = splitCompoundName(comp_name)

    snake_name = meshtastic.util.camel_to_snake(name[-1])
    camel_name = meshtastic.util.snake_to_camel(name[-1])
    logging.debug(f"snake_name:{snake_name}")
    logging.debug(f"camel_name:{camel_name}")

    objDesc = config.DESCRIPTOR
    config_part = config
    config_type = objDesc.fields_by_name.get(name[0])
    if config_type and config_type.message_type is not None:
        for name_part in name[1:-1]:
            part_snake_name = meshtastic.util.camel_to_snake((name_part))
            config_part = getattr(config, config_type.name)
            config_type = config_type.message_type.fields_by_name.get(part_snake_name)
    pref = None
    if config_type and config_type.message_type is not None:
        pref = config_type.message_type.fields_by_name.get(snake_name)
    # Others like ChannelSettings are standalone
    elif config_type:
        pref = config_type

    if (not pref) or (not config_type):
        return False

    val = meshtastic.util.fromStr(valStr)
    logging.debug(f"valStr:{valStr} val:{val}")

    if snake_name == "wifi_psk" and len(valStr) < 8:
        print(f"Warning: network.wifi_psk must be 8 or more characters.")
        return False

    enumType = pref.enum_type
    # pylint: disable=C0123
    if enumType and type(val) == str:
        # We've failed so far to convert this string into an enum, try to find it by reflection
        e = enumType.values_by_name.get(val)
        if e:
            val = e.number
        else:
            if mt_config.camel_case:
                print(
                    f"{name[0]}.{camel_name} does not have an enum called {val}, so you can not set it."
                )
            else:
                print(
                    f"{name[0]}.{snake_name} does not have an enum called {val}, so you can not set it."
                )
            print(f"Choices in sorted order are:")
            names = []
            for f in enumType.values:
                # Note: We must use the value of the enum (regardless if camel or snake case)
                names.append(f"{f.name}")
            for temp_name in sorted(names):
                print(f"    {temp_name}")
            return False

    # note: 'ignore_incoming' is a repeating field
    if snake_name != "ignore_incoming":
        try:
            if config_type.message_type is not None:
                config_values = getattr(config_part, config_type.name)
                setattr(config_values, pref.name, val)
            else:
                setattr(config_part, snake_name, val)
        except TypeError:
            # The setter didn't like our arg type guess try again as a string
            config_values = getattr(config_part, config_type.name)
            setattr(config_values, pref.name, valStr)
    else:
        config_values = getattr(config, config_type.name)
        if val == 0:
            # clear values
            print("Clearing ignore_incoming list")
            del config_values.ignore_incoming[:]
        else:
            print(f"Adding '{val}' to the ignore_incoming list")
            config_values.ignore_incoming.extend([int(valStr)])

    prefix = f"{'.'.join(name[0:-1])}." if config_type.message_type is not None else ""
    if mt_config.camel_case:
        print(f"Set {prefix}{camel_name} to {valStr}")
    else:
        print(f"Set {prefix}{snake_name} to {valStr}")

    return True


def onConnected(interface):
    """Callback invoked when we connect to a radio"""
    closeNow = False  # Should we drop the connection after we finish?
    waitForAckNak = (
        False  # Should we wait for an acknowledgment if we send to a remote node?
    )
    try:
        args = mt_config.args

        # do not print this line if we are exporting the config
        if not args.export_config:
            print("Connected to radio")

        if args.remove_position:
            if args.dest != BROADCAST_ADDR:
                print("Setting positions of remote nodes is not supported.")
                return
            closeNow = True
            print("Removing fixed position and disabling fixed position setting")
            interface.localNode.removeFixedPosition()
        elif args.setlat or args.setlon or args.setalt:
            if args.dest != BROADCAST_ADDR:
                print("Setting latitude, longitude, and altitude of remote nodes is not supported.")
                return
            closeNow = True

            alt = 0
            lat = 0
            lon = 0
            if args.setalt:
                alt = int(args.setalt)
                print(f"Fixing altitude at {alt} meters")
            if args.setlat:
                try:
                    lat = int(args.setlat)
                except ValueError:
                    lat = float(args.setlat)
                print(f"Fixing latitude at {lat} degrees")
            if args.setlon:
                try:
                    lon = int(args.setlon)
                except ValueError:
                    lon = float(args.setlon)
                print(f"Fixing longitude at {lon} degrees")

            print("Setting device position and enabling fixed position setting")
            # can include lat/long/alt etc: latitude = 37.5, longitude = -122.1
            interface.localNode.setFixedPosition(lat, lon, alt)
        elif not args.no_time:
            # We normally provide a current time to the mesh when we connect
            if interface.localNode.nodeNum in interface.nodesByNum and "position" in interface.nodesByNum[interface.localNode.nodeNum]:
                # send the same position the node already knows, just to update time
                position = interface.nodesByNum[interface.localNode.nodeNum]["position"]
                interface.sendPosition(position.get("latitude", 0.0), position.get("longitude", 0.0), position.get("altitude", 0.0))
            else:
                interface.sendPosition()

        if args.set_owner:
            closeNow = True
            waitForAckNak = True
            print(f"Setting device owner to {args.set_owner}")
            interface.getNode(args.dest, False).setOwner(args.set_owner)

        if args.set_owner_short:
            closeNow = True
            waitForAckNak = True
            print(f"Setting device owner short to {args.set_owner_short}")
            interface.getNode(args.dest, False).setOwner(
                long_name=None, short_name=args.set_owner_short
            )

        # TODO: add to export-config and configure
        if args.set_canned_message:
            closeNow = True
            waitForAckNak = True
            print(f"Setting canned plugin message to {args.set_canned_message}")
            interface.getNode(args.dest, False).set_canned_message(
                args.set_canned_message
            )

        # TODO: add to export-config and configure
        if args.set_ringtone:
            closeNow = True
            waitForAckNak = True
            print(f"Setting ringtone to {args.set_ringtone}")
            interface.getNode(args.dest, False).set_ringtone(args.set_ringtone)

        if args.pos_fields:
            # If --pos-fields invoked with args, set position fields
            closeNow = True
            positionConfig = interface.getNode(args.dest).localConfig.position
            allFields = 0

            try:
                for field in args.pos_fields:
                    v_field = positionConfig.PositionFlags.Value(field)
                    allFields |= v_field

            except ValueError:
                print("ERROR: supported position fields are:")
                print(positionConfig.PositionFlags.keys())
                print(
                    "If no fields are specified, will read and display current value."
                )

            else:
                print(f"Setting position fields to {allFields}")
                setPref(positionConfig, "position_flags", f"{allFields:d}")
                print("Writing modified preferences to device")
                interface.getNode(args.dest).writeConfig("position")

        elif args.pos_fields is not None:
            # If --pos-fields invoked without args, read and display current value
            closeNow = True
            positionConfig = interface.getNode(args.dest).localConfig.position

            fieldNames = []
            for bit in positionConfig.PositionFlags.values():
                if positionConfig.position_flags & bit:
                    fieldNames.append(positionConfig.PositionFlags.Name(bit))
            print(" ".join(fieldNames))

        if args.set_ham:
            closeNow = True
            print(f"Setting Ham ID to {args.set_ham} and turning off encryption")
            interface.getNode(args.dest).setOwner(args.set_ham, is_licensed=True)
            # Must turn off encryption on primary channel
            interface.getNode(args.dest).turnOffEncryptionOnPrimaryChannel()

        if args.reboot:
            closeNow = True
            waitForAckNak = True
            interface.getNode(args.dest, False).reboot()

        if args.reboot_ota:
            closeNow = True
            waitForAckNak = True
            interface.getNode(args.dest, False).rebootOTA()

        if args.enter_dfu:
            closeNow = True
            waitForAckNak = True
            interface.getNode(args.dest, False).enterDFUMode()

        if args.shutdown:
            closeNow = True
            waitForAckNak = True
            interface.getNode(args.dest, False).shutdown()

        if args.device_metadata:
            closeNow = True
            interface.getNode(args.dest, False).getMetadata()

        if args.begin_edit:
            closeNow = True
            interface.getNode(args.dest, False).beginSettingsTransaction()

        if args.commit_edit:
            closeNow = True
            interface.getNode(args.dest, False).commitSettingsTransaction()

        if args.factory_reset:
            closeNow = True
            waitForAckNak = True
            interface.getNode(args.dest, False).factoryReset()

        if args.remove_node:
            closeNow = True
            waitForAckNak = True
            interface.getNode(args.dest, False).removeNode(args.remove_node)

        if args.reset_nodedb:
            closeNow = True
            waitForAckNak = True
            interface.getNode(args.dest, False).resetNodeDb()

        if args.sendtext:
            closeNow = True
            channelIndex = mt_config.channel_index or 0
            if checkChannel(interface, channelIndex):
                print(
                    f"Sending text message {args.sendtext} to {args.dest} on channelIndex:{channelIndex}"
                )
                interface.sendText(
                    args.sendtext,
                    args.dest,
                    wantAck=True,
                    channelIndex=channelIndex,
                    onResponse=interface.getNode(args.dest, False).onAckNak,
                )
            else:
                meshtastic.util.our_exit(
                    f"Warning: {channelIndex} is not a valid channel. Channel must not be DISABLED."
                )

        if args.traceroute:
            loraConfig = getattr(interface.localNode.localConfig, "lora")
            hopLimit = getattr(loraConfig, "hop_limit")
            dest = str(args.traceroute)
            channelIndex = mt_config.channel_index or 0
            if checkChannel(interface, channelIndex):
                print(f"Sending traceroute request to {dest} on channelIndex:{channelIndex} (this could take a while)")
                interface.sendTraceRoute(dest, hopLimit, channelIndex=channelIndex)

        if args.request_telemetry:
            if args.dest == BROADCAST_ADDR:
                meshtastic.util.our_exit("Warning: Must use a destination node ID.")
            else:
                channelIndex = mt_config.channel_index or 0
                if checkChannel(interface, channelIndex):
                    print(f"Sending telemetry request to {args.dest} on channelIndex:{channelIndex} (this could take a while)")
                    interface.sendTelemetry(destinationId=args.dest, wantResponse=True, channelIndex=channelIndex)

        if args.request_position:
            if args.dest == BROADCAST_ADDR:
                meshtastic.util.our_exit("Warning: Must use a destination node ID.")
            else:
                channelIndex = mt_config.channel_index or 0
                if checkChannel(interface, channelIndex):
                    print(f"Sending position request to {args.dest} on channelIndex:{channelIndex} (this could take a while)")
                    interface.sendPosition(destinationId=args.dest, wantResponse=True, channelIndex=channelIndex)

        if args.gpio_wrb or args.gpio_rd or args.gpio_watch:
            if args.dest == BROADCAST_ADDR:
                meshtastic.util.our_exit("Warning: Must use a destination node ID.")
            else:
                rhc = remote_hardware.RemoteHardwareClient(interface)

                if args.gpio_wrb:
                    bitmask = 0
                    bitval = 0
                    for wrpair in args.gpio_wrb or []:
                        bitmask |= 1 << int(wrpair[0])
                        bitval |= int(wrpair[1]) << int(wrpair[0])
                    print(
                        f"Writing GPIO mask 0x{bitmask:x} with value 0x{bitval:x} to {args.dest}"
                    )
                    rhc.writeGPIOs(args.dest, bitmask, bitval)
                    closeNow = True

                if args.gpio_rd:
                    bitmask = int(args.gpio_rd, 16)
                    print(f"Reading GPIO mask 0x{bitmask:x} from {args.dest}")
                    interface.mask = bitmask
                    rhc.readGPIOs(args.dest, bitmask, None)
                    # wait up to X seconds for a response
                    for _ in range(10):
                        time.sleep(1)
                        if interface.gotResponse:
                            break
                    logging.debug(f"end of gpio_rd")

                if args.gpio_watch:
                    bitmask = int(args.gpio_watch, 16)
                    print(
                        f"Watching GPIO mask 0x{bitmask:x} from {args.dest}. Press ctrl-c to exit"
                    )
                    while True:
                        rhc.watchGPIOs(args.dest, bitmask)
                        time.sleep(1)

        # handle settings
        if args.set:
            closeNow = True
            waitForAckNak = True
            node = interface.getNode(args.dest, False)

            # Handle the int/float/bool arguments
            pref = None
            for pref in args.set:
                found = False
                field = splitCompoundName(pref[0].lower())[0]
                for config in [node.localConfig, node.moduleConfig]:
                    config_type = config.DESCRIPTOR.fields_by_name.get(field)
                    if config_type:
                        if len(config.ListFields()) == 0:
                            node.requestConfig(
                                config.DESCRIPTOR.fields_by_name.get(field)
                            )
                        found = setPref(config, pref[0], pref[1])
                        if found:
                            break

            if found:
                print("Writing modified preferences to device")
                node.writeConfig(field)
            else:
                if mt_config.camel_case:
                    print(
                        f"{node.localConfig.__class__.__name__} and {node.moduleConfig.__class__.__name__} do not have an attribute {pref[0]}."
                    )
                else:
                    print(
                        f"{node.localConfig.__class__.__name__} and {node.moduleConfig.__class__.__name__} do not have attribute {pref[0]}."
                    )
                print("Choices are...")
                printConfig(node.localConfig)
                printConfig(node.moduleConfig)

        if args.configure:
            with open(args.configure[0], encoding="utf8") as file:
                configuration = yaml.safe_load(file)
                closeNow = True

                interface.getNode(args.dest, False).beginSettingsTransaction()

                if "owner" in configuration:
                    print(f"Setting device owner to {configuration['owner']}")
                    waitForAckNak = True
                    interface.getNode(args.dest, False).setOwner(configuration["owner"])

                if "owner_short" in configuration:
                    print(
                        f"Setting device owner short to {configuration['owner_short']}"
                    )
                    waitForAckNak = True
                    interface.getNode(args.dest, False).setOwner(
                        long_name=None, short_name=configuration["owner_short"]
                    )

                if "ownerShort" in configuration:
                    print(
                        f"Setting device owner short to {configuration['ownerShort']}"
                    )
                    waitForAckNak = True
                    interface.getNode(args.dest, False).setOwner(
                        long_name=None, short_name=configuration["ownerShort"]
                    )

                if "channel_url" in configuration:
                    print("Setting channel url to", configuration["channel_url"])
                    interface.getNode(args.dest).setURL(configuration["channel_url"])

                if "channelUrl" in configuration:
                    print("Setting channel url to", configuration["channelUrl"])
                    interface.getNode(args.dest).setURL(configuration["channelUrl"])

                if "location" in configuration:
                    alt = 0
                    lat = 0.0
                    lon = 0.0
                    localConfig = interface.localNode.localConfig

                    if "alt" in configuration["location"]:
                        alt = int(configuration["location"]["alt"] or 0)
                        localConfig.position.fixed_position = True
                        print(f"Fixing altitude at {alt} meters")
                    if "lat" in configuration["location"]:
                        lat = float(configuration["location"]["lat"] or 0)
                        localConfig.position.fixed_position = True
                        print(f"Fixing latitude at {lat} degrees")
                    if "lon" in configuration["location"]:
                        lon = float(configuration["location"]["lon"] or 0)
                        localConfig.position.fixed_position = True
                        print(f"Fixing longitude at {lon} degrees")
                    print("Setting device position")
                    interface.sendPosition(lat, lon, alt)
                    interface.localNode.writeConfig("position")

                if "config" in configuration:
                    localConfig = interface.getNode(args.dest).localConfig
                    for section in configuration["config"]:
                        traverseConfig(section, configuration["config"][section], localConfig)
                        interface.getNode(args.dest).writeConfig(
                            meshtastic.util.camel_to_snake(section)
                        )

                if "module_config" in configuration:
                    moduleConfig = interface.getNode(args.dest).moduleConfig
                    for section in configuration["module_config"]:
                        traverseConfig(section, configuration["module_config"][section], moduleConfig)
                        interface.getNode(args.dest).writeConfig(
                            meshtastic.util.camel_to_snake(section)
                        )

                interface.getNode(args.dest, False).commitSettingsTransaction()
                print("Writing modified configuration to device")

        if args.export_config:
            if args.dest != BROADCAST_ADDR:
                print("Exporting configuration of remote nodes is not supported.")
                return
            # export the configuration (the opposite of '--configure')
            closeNow = True
            export_config(interface)

        if args.seturl:
            closeNow = True
            interface.getNode(args.dest).setURL(args.seturl)

        # handle changing channels

        if args.ch_add:
            channelIndex = mt_config.channel_index
            if channelIndex is not None:
                # Since we set the channel index after adding a channel, don't allow --ch-index
                meshtastic.util.our_exit(
                    "Warning: '--ch-add' and '--ch-index' are incompatible. Channel not added."
                )
            closeNow = True
            if len(args.ch_add) > 10:
                meshtastic.util.our_exit(
                    "Warning: Channel name must be shorter. Channel not added."
                )
            n = interface.getNode(args.dest)
            ch = n.getChannelByName(args.ch_add)
            if ch:
                meshtastic.util.our_exit(
                    f"Warning: This node already has a '{args.ch_add}' channel. No changes were made."
                )
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
                if channelIndex is None:
                    print(f"Setting newly-added channel's {ch.index} as '--ch-index' for further modifications")
                    mt_config.channel_index = ch.index

        if args.ch_del:
            closeNow = True

            channelIndex = mt_config.channel_index
            if channelIndex is None:
                meshtastic.util.our_exit(
                    "Warning: Need to specify '--ch-index' for '--ch-del'.", 1
                )
            else:
                if channelIndex == 0:
                    meshtastic.util.our_exit(
                        "Warning: Cannot delete primary channel.", 1
                    )
                else:
                    print(f"Deleting channel {channelIndex}")
                    ch = interface.getNode(args.dest).deleteChannel(channelIndex)

        def setSimpleConfig(modem_preset):
            """Set one of the simple modem_config"""
            channelIndex = mt_config.channel_index
            if channelIndex is not None and channelIndex > 0:
                meshtastic.util.our_exit(
                    "Warning: Cannot set modem preset for non-primary channel", 1
                )
            # Overwrite modem_preset
            prefs = interface.getNode(args.dest).localConfig
            prefs.lora.modem_preset = modem_preset
            interface.getNode(args.dest).writeConfig("lora")

        # handle the simple radio set commands
        if args.ch_vlongslow:
            setSimpleConfig(config_pb2.Config.LoRaConfig.ModemPreset.VERY_LONG_SLOW)

        if args.ch_longslow:
            setSimpleConfig(config_pb2.Config.LoRaConfig.ModemPreset.LONG_SLOW)

        if args.ch_longfast:
            setSimpleConfig(config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST)

        if args.ch_medslow:
            setSimpleConfig(config_pb2.Config.LoRaConfig.ModemPreset.MEDIUM_SLOW)

        if args.ch_medfast:
            setSimpleConfig(config_pb2.Config.LoRaConfig.ModemPreset.MEDIUM_FAST)

        if args.ch_shortslow:
            setSimpleConfig(config_pb2.Config.LoRaConfig.ModemPreset.SHORT_SLOW)

        if args.ch_shortfast:
            setSimpleConfig(config_pb2.Config.LoRaConfig.ModemPreset.SHORT_FAST)

        if args.ch_set or args.ch_enable or args.ch_disable:
            closeNow = True

            channelIndex = mt_config.channel_index
            if channelIndex is None:
                meshtastic.util.our_exit("Warning: Need to specify '--ch-index'.", 1)
            ch = interface.getNode(args.dest).channels[channelIndex]

            if args.ch_enable or args.ch_disable:
                print(
                    "Warning: --ch-enable and --ch-disable can produce noncontiguous channels, "
                    "which can cause errors in some clients. Whenever possible, use --ch-add and --ch-del instead."
                )
                if channelIndex == 0:
                    meshtastic.util.our_exit(
                        "Warning: Cannot enable/disable PRIMARY channel."
                    )

                enable = True  # default to enable
                if args.ch_enable:
                    enable = True
                if args.ch_disable:
                    enable = False

            # Handle the channel settings
            for pref in args.ch_set or []:
                if pref[0] == "psk":
                    found = True
                    ch.settings.psk = meshtastic.util.fromPSK(pref[1])
                else:
                    found = setPref(ch.settings, pref[0], pref[1])
                if not found:
                    category_settings = ['module_settings']
                    print(
                        f"{ch.settings.__class__.__name__} does not have an attribute {pref[0]}."
                    )
                    print("Choices are...")
                    for field in ch.settings.DESCRIPTOR.fields:
                        if field.name not in category_settings:
                            print(f"{field.name}")
                        else:
                            print(f"{field.name}:")
                            config = ch.settings.DESCRIPTOR.fields_by_name.get(field.name)
                            names = []
                            for sub_field in config.message_type.fields:
                                tmp_name = f"{field.name}.{sub_field.name}"
                                names.append(tmp_name)
                            for temp_name in sorted(names):
                                print(f"    {temp_name}")

                enable = True  # If we set any pref, assume the user wants to enable the channel

            if enable:
                ch.role = (
                    channel_pb2.Channel.Role.PRIMARY
                    if (channelIndex == 0)
                    else channel_pb2.Channel.Role.SECONDARY
                )
            else:
                ch.role = channel_pb2.Channel.Role.DISABLED

            print(f"Writing modified channels to device")
            interface.getNode(args.dest).writeChannel(channelIndex)

        if args.get_canned_message:
            closeNow = True
            print("")
            interface.getNode(args.dest).get_canned_message()

        if args.get_ringtone:
            closeNow = True
            print("")
            interface.getNode(args.dest).get_ringtone()

        if args.info:
            print("")
            # If we aren't trying to talk to our local node, don't show it
            if args.dest == BROADCAST_ADDR:
                interface.showInfo()
                print("")
                interface.getNode(args.dest).showInfo()
                closeNow = True
                print("")
                pypi_version = meshtastic.util.check_if_newer_version()
                if pypi_version:
                    print(
                        f"*** A newer version v{pypi_version} is available!"
                        ' Consider running "pip install --upgrade meshtastic" ***\n'
                    )
                if sys.version_info[0] == 3 and sys.version_info[1] < 9:
                    print("  *** this version of the CLI is the last that supports python 3.8 ***")
                    print("  *** please update your python installation ***")
            else:
                print("Showing info of remote node is not supported.")
                print(
                    "Use the '--get' command for a specific configuration (e.g. 'lora') instead."
                )

        if args.get:
            closeNow = True
            node = interface.getNode(args.dest, False)
            for pref in args.get:
                found = getPref(node, pref[0])

            if found:
                print("Completed getting preferences")

        if args.nodes:
            closeNow = True
            if args.dest != BROADCAST_ADDR:
                print("Showing node list of a remote node is not supported.")
                return
            interface.showNodes()

        if args.qr or args.qr_all:
            closeNow = True
            url = interface.getNode(args.dest, True).getURL(includeAll=args.qr_all)
            if args.qr_all:
                urldesc = "Complete URL (includes all channels)"
            else:
                urldesc = "Primary channel URL"
            print(f"{urldesc}: {url}")
            qr = pyqrcode.create(url)
            print(qr.terminal())

        if args.listen:
            closeNow = False

        have_tunnel = platform.system() == "Linux"
        if have_tunnel and args.tunnel:
            if args.dest != BROADCAST_ADDR:
                print("A tunnel can only be created using the local node.")
                return
            # pylint: disable=C0415
            from . import tunnel

            # Even if others said we could close, stay open if the user asked for a tunnel
            closeNow = False
            if interface.noProto:
                logging.warning(f"Not starting Tunnel - disabled by noProto")
            else:
                if args.tunnel_net:
                    tunnel.Tunnel(interface, subnet=args.tunnel_net)
                else:
                    tunnel.Tunnel(interface)

        if args.ack or (args.dest != BROADCAST_ADDR and waitForAckNak):
            print(
                f"Waiting for an acknowledgment from remote node (this could take a while)"
            )
            interface.getNode(args.dest, False).iface.waitForAckNak()

        if args.wait_to_disconnect:
            print(f"Waiting {args.wait_to_disconnect} seconds before disconnecting" )
            time.sleep(int(args.wait_to_disconnect))

        # if the user didn't ask for serial debugging output, we might want to exit after we've done our operation
        if (not args.seriallog) and closeNow:
            interface.close()  # after running command then exit

    except Exception as ex:
        print(f"Aborting due to: {ex}")
        interface.close()  # close the connection now, so that our app exits
        sys.exit(1)


def printConfig(config):
    """print configuration"""
    objDesc = config.DESCRIPTOR
    for config_section in objDesc.fields:
        if config_section.name != "version":
            config = objDesc.fields_by_name.get(config_section.name)
            print(f"{config_section.name}:")
            names = []
            for field in config.message_type.fields:
                tmp_name = f"{config_section.name}.{field.name}"
                if mt_config.camel_case:
                    tmp_name = meshtastic.util.snake_to_camel(tmp_name)
                names.append(tmp_name)
            for temp_name in sorted(names):
                print(f"    {temp_name}")


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
    """used in --export-config"""
    configObj = {}

    owner = interface.getLongName()
    owner_short = interface.getShortName()
    channel_url = interface.localNode.getURL()
    myinfo = interface.getMyNodeInfo()
    pos = myinfo.get("position")
    lat = None
    lon = None
    alt = None
    if pos:
        lat = pos.get("latitude")
        lon = pos.get("longitude")
        alt = pos.get("altitude")

    if owner:
        configObj["owner"] = owner
    if owner_short:
        configObj["owner_short"] = owner_short
    if channel_url:
        if mt_config.camel_case:
            configObj["channelUrl"] = channel_url
        else:
            configObj["channel_url"] = channel_url
    # lat and lon don't make much sense without the other (so fill with 0s), and alt isn't meaningful without both
    if lat or lon:
        configObj["location"] = {"lat": lat or float(0), "lon": lon or float(0)}
        if alt:
            configObj["location"]["alt"] = alt

    config = MessageToDict(interface.localNode.localConfig)
    if config:
        # Convert inner keys to correct snake/camelCase
        prefs = {}
        for pref in config:
            if mt_config.camel_case:
                prefs[meshtastic.util.snake_to_camel(pref)] = config[pref]
            else:
                prefs[pref] = config[pref]
        if mt_config.camel_case:
            configObj["config"] = config
        else:
            configObj["config"] = config

    module_config = MessageToDict(interface.localNode.moduleConfig)
    if module_config:
        # Convert inner keys to correct snake/camelCase
        prefs = {}
        for pref in module_config:
            if len(module_config[pref]) > 0:
                prefs[pref] = module_config[pref]
        if mt_config.camel_case:
            configObj["module_config"] = prefs
        else:
            configObj["module_config"] = prefs

    config = "# start of Meshtastic configure yaml\n"
    config += yaml.dump(configObj)
    print(config)
    return config


def common():
    """Shared code for all of our command line wrappers"""
    logfile = None
    args = mt_config.args
    parser = mt_config.parser
    logging.basicConfig(
        level=logging.DEBUG if (args.debug or args.listen) else logging.INFO,
        format="%(levelname)s file:%(filename)s %(funcName)s line:%(lineno)s %(message)s",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        meshtastic.util.our_exit("", 1)
    else:
        if args.support:
            meshtastic.util.support_info()
            meshtastic.util.our_exit("", 0)

        if args.ch_index is not None:
            channelIndex = int(args.ch_index)
            mt_config.channel_index = channelIndex

        if not args.dest:
            args.dest = BROADCAST_ADDR

        if not args.seriallog:
            if args.noproto:
                args.seriallog = "stdout"
            else:
                args.seriallog = "none"  # assume no debug output in this case

        if args.deprecated is not None:
            logging.error(
                "This option has been deprecated, see help below for the correct replacement..."
            )
            parser.print_help(sys.stderr)
            meshtastic.util.our_exit("", 1)
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
                logfile = open(args.seriallog, "w+", buffering=1, encoding="utf8")
                mt_config.logfile = logfile

            subscribe()
            if args.ble_scan:
                logging.debug("BLE scan starting")
                for x in BLEInterface.scan():
                    print(f"Found: name='{x.name}' address='{x.address}'")
                meshtastic.util.our_exit("BLE scan finished", 0)
            elif args.ble:
                client = BLEInterface(args.ble if args.ble != "any" else None, debugOut=logfile, noProto=args.noproto, noNodes=args.no_nodes)
            elif args.host:
                try:
                    client = meshtastic.tcp_interface.TCPInterface(
                        args.host, debugOut=logfile, noProto=args.noproto, noNodes=args.no_nodes
                    )
                except Exception as ex:
                    meshtastic.util.our_exit(
                        f"Error connecting to {args.host}:{ex}", 1
                    )
            else:
                try:
                    client = meshtastic.serial_interface.SerialInterface(
                        args.port, debugOut=logfile, noProto=args.noproto, noNodes=args.no_nodes
                    )
                except PermissionError as ex:
                    username = os.getlogin()
                    message = "Permission Error:\n"
                    message += (
                        "  Need to add yourself to the 'dialout' group by running:\n"
                    )
                    message += f"     sudo usermod -a -G dialout {username}\n"
                    message += "  After running that command, log out and re-login for it to take effect.\n"
                    message += f"Error was:{ex}"
                    meshtastic.util.our_exit(message)
                if client.devPath is None:
                    try:
                        client = meshtastic.tcp_interface.TCPInterface(
                            "localhost", debugOut=logfile, noProto=args.noproto, noNodes=args.no_nodes
                        )
                    except Exception as ex:
                        meshtastic.util.our_exit(
                            f"Error connecting to localhost:{ex}", 1
                        )


            # We assume client is fully connected now
            onConnected(client)

            have_tunnel = platform.system() == "Linux"
            if (
                args.noproto or args.reply or (have_tunnel and args.tunnel) or args.listen
            ):  # loop until someone presses ctrlc
                while True:
                    time.sleep(1000)

        # don't call exit, background threads might be running still
        # sys.exit(0)

def addConnectionArgs(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add connection specifiation arguments"""

    outer = parser.add_argument_group('Connection', 'Optional arguments that specify how to connect to a Meshtastic device.')
    group = outer.add_mutually_exclusive_group()
    group.add_argument(
        "--port", "--serial", "-s",
        help="The port of the device to connect to using serial, e.g. /dev/ttyUSB0. (defaults to trying to detect a port)",
        nargs="?",
        const=None,
        default=None,
    )

    group.add_argument(
        "--host", "--tcp", "-t",
        help="Connect to a device using TCP, optionally passing hostname or IP address to use. (defaults to '%(const)s')",
        nargs="?",
        default=None,
        const="localhost"
    )

    group.add_argument(
        "--ble", "-b",
        help="Connect to a BLE device, optionally specifying a device name (defaults to '%(const)s')",
        nargs="?",
        default=None,
        const="any"
    )

    return parser


def initParser():
    """Initialize the command line argument parsing."""
    parser = mt_config.parser
    args = mt_config.args

    # The "Help" group includes the help option and other informational stuff about the CLI itself
    outerHelpGroup = parser.add_argument_group('Help')
    helpGroup = outerHelpGroup.add_mutually_exclusive_group()
    helpGroup.add_argument("-h", "--help", action="help", help="show this help message and exit")

    the_version = get_active_version()
    helpGroup.add_argument("--version", action="version", version=f"{the_version}")

    helpGroup.add_argument(
        "--support",
        action="store_true",
        help="Show support info (useful when troubleshooting an issue)",
    )

    # Connection arguments to indicate a device to connect to
    parser = addConnectionArgs(parser)

    # Arguments concerning viewing and setting configuration

    # Arguments for sending or requesting things from the local device

    # Arguments for sending or requesting things from the mesh

    # All the rest of the arguments
    group = parser.add_argument_group("optional arguments")
    group.add_argument(
        "--configure",
        help="Specify a path to a yaml(.yml) file containing the desired settings for the connected device.",
        action="append",
    )

    group.add_argument(
        "--export-config",
        help="Export the configuration in yaml(.yml) format.",
        action="store_true",
    )

    group.add_argument(
        "--seriallog",
        help="Log device serial output to either 'none' or a filename to append to.  Defaults to 'stdout' if no filename specified.",
        nargs='?',
        const="stdout",
        default=None
    )

    group.add_argument(
        "--info",
        help="Read and display the radio config information",
        action="store_true",
    )

    group.add_argument(
        "--get-canned-message",
        help="Show the canned message plugin message",
        action="store_true",
    )

    group.add_argument(
        "--get-ringtone", help="Show the stored ringtone", action="store_true"
    )

    group.add_argument(
        "--nodes",
        help="Print Node List in a pretty formatted table",
        action="store_true",
    )

    group.add_argument(
        "--qr",
        help=(
            "Display a QR code for the node's primary channel (or all channels with --qr-all). "
            "Also shows the shareable channel URL."
        ),
        action="store_true",
    )

    group.add_argument(
        "--qr-all",
        help="Display a QR code and URL for all of the node's channels.",
        action="store_true",
    )

    group.add_argument(
        "--get",
        help=(
            "Get a preferences field. Use an invalid field such as '0' to get a list of all fields."
            " Can use either snake_case or camelCase format. (ex: 'ls_secs' or 'lsSecs')"
        ),
        nargs=1,
        action="append",
    )

    group.add_argument(
        "--set",
        help="Set a preferences field. Can use either snake_case or camelCase format. (ex: 'ls_secs' or 'lsSecs')",
        nargs=2,
        action="append",
    )

    group.add_argument("--seturl", help="Set a channel URL", action="store")

    group.add_argument(
        "--ch-index",
        help="Set the specified channel index. Channels start at 0 (0 is the PRIMARY channel).",
        action="store",
    )

    group.add_argument(
        "--ch-add",
        help="Add a secondary channel, you must specify a channel name",
        default=None,
    )

    group.add_argument(
        "--ch-del", help="Delete the ch-index channel", action="store_true"
    )

    group.add_argument(
        "--ch-enable",
        help="Enable the specified channel",
        action="store_true",
        dest="ch_enable",
        default=False,
    )

    # Note: We are doing a double negative here (Do we want to disable? If ch_disable==True, then disable.)
    group.add_argument(
        "--ch-disable",
        help="Disable the specified channel",
        action="store_true",
        dest="ch_disable",
        default=False,
    )

    group.add_argument(
        "--ch-set",
        help=(
            "Set a channel parameter. To see channel settings available:'--ch-set all all --ch-index 0'. "
            "Can set the 'psk' using this command. To disable encryption on primary channel:'--ch-set psk none --ch-index 0'. "
            "To set encryption with a new random key on second channel:'--ch-set psk random --ch-index 1'. "
            "To set encryption back to the default:'--ch-set psk default --ch-index 0'. To set encryption with your "
            "own key: '--ch-set psk 0x1a1a1a1a2b2b2b2b1a1a1a1a2b2b2b2b1a1a1a1a2b2b2b2b1a1a1a1a2b2b2b2b --ch-index 0'."
        ),
        nargs=2,
        action="append",
    )

    group.add_argument(
        "--ch-vlongslow",
        help="Change to the very long-range and slow channel",
        action="store_true",
    )

    group.add_argument(
        "--ch-longslow",
        help="Change to the long-range and slow channel",
        action="store_true",
    )

    group.add_argument(
        "--ch-longfast",
        help="Change to the long-range and fast channel",
        action="store_true",
    )

    group.add_argument(
        "--ch-medslow",
        help="Change to the med-range and slow channel",
        action="store_true",
    )

    group.add_argument(
        "--ch-medfast",
        help="Change to the med-range and fast channel",
        action="store_true",
    )

    group.add_argument(
        "--ch-shortslow",
        help="Change to the short-range and slow channel",
        action="store_true",
    )

    group.add_argument(
        "--ch-shortfast",
        help="Change to the short-range and fast channel",
        action="store_true",
    )

    group.add_argument("--set-owner", help="Set device owner name", action="store")

    group.add_argument(
        "--set-canned-message",
        help="Set the canned messages plugin message (up to 200 characters).",
        action="store",
    )

    group.add_argument(
        "--set-ringtone",
        help="Set the Notification Ringtone (up to 230 characters).",
        action="store",
    )

    group.add_argument(
        "--set-owner-short", help="Set device owner short name", action="store"
    )

    group.add_argument(
        "--set-ham", help="Set licensed Ham ID and turn off encryption", action="store"
    )

    group.add_argument(
        "--dest",
        help="The destination node id for any sent commands, if not set '^all' or '^local' is assumed as appropriate",
        default=None,
    )

    group.add_argument(
        "--sendtext",
        help="Send a text message. Can specify a destination '--dest' and/or channel index '--ch-index'.",
    )

    group.add_argument(
        "--traceroute",
        help="Traceroute from connected node to a destination. "
        "You need pass the destination ID as argument, like "
        "this: '--traceroute !ba4bf9d0' "
        "Only nodes that have the encryption key can be traced.",
    )

    group.add_argument(
        "--request-telemetry",
        help="Request telemetry from a node. "
        "You need to pass the destination ID as argument with '--dest'. "
        "For repeaters, the nodeNum is required.",
        action="store_true",
    )

    group.add_argument(
        "--request-position",
        help="Request the position from a node. "
        "You need to pass the destination ID as an argument with '--dest'. "
        "For repeaters, the nodeNum is required.",
        action="store_true",
    )

    group.add_argument(
        "--ack",
        help="Use in combination with --sendtext to wait for an acknowledgment.",
        action="store_true",
    )

    group.add_argument(
        "--reboot", help="Tell the destination node to reboot", action="store_true"
    )

    group.add_argument(
        "--reboot-ota",
        help="Tell the destination node to reboot into factory firmware (ESP32)",
        action="store_true",
    )

    group.add_argument(
        "--enter-dfu",
        help="Tell the destination node to enter DFU mode (NRF52)",
        action="store_true",
    )

    group.add_argument(
        "--shutdown", help="Tell the destination node to shutdown", action="store_true"
    )

    group.add_argument(
        "--device-metadata",
        help="Get the device metadata from the node",
        action="store_true",
    )

    group.add_argument(
        "--begin-edit",
        help="Tell the node to open a transaction to edit settings",
        action="store_true",
    )

    group.add_argument(
        "--commit-edit",
        help="Tell the node to commit open settings transaction",
        action="store_true",
    )

    group.add_argument(
        "--factory-reset",
        help="Tell the destination node to install the default config",
        action="store_true",
    )

    group.add_argument(
        "--remove-node",
        help="Tell the destination node to remove a specific node from its DB, by node number or ID"
    )
    group.add_argument(
        "--reset-nodedb",
        help="Tell the destination node to clear its list of nodes",
        action="store_true",
    )

    group.add_argument(
        "--reply", help="Reply to received messages", action="store_true"
    )

    group.add_argument(
        "--no-time",
        help="Suppress sending the current time to the mesh",
        action="store_true",
    )

    group.add_argument(
        "--no-nodes",
        help="Request that the node not send node info to the client. "
        "Will break things that depend on the nodedb, but will speed up startup. Requires 2.3.11+ firmware.",
        action="store_true",
    )

    group.add_argument(
        "--setalt",
        help="Set device altitude in meters (allows use without GPS), and enable fixed position.",
    )

    group.add_argument(
        "--setlat",
        help="Set device latitude (allows use without GPS), and enable fixed position. Accepts a decimal value or an integer premultiplied by 1e7.",
    )

    group.add_argument(
        "--setlon",
        help="Set device longitude (allows use without GPS), and enable fixed position. Accepts a decimal value or an integer premultiplied by 1e7.",
    )

    group.add_argument(
        "--remove-position",
        help="Clear any existing fixed position and disable fixed position.",
        action="store_true",
    )

    group.add_argument(
        "--pos-fields",
        help="Specify fields to send when sending a position. Use no argument for a list of valid values. "
        "Can pass multiple values as a space separated list like "
        "this: '--pos-fields ALTITUDE HEADING SPEED'",
        nargs="*",
        action="store",
    )

    group.add_argument(
        "--debug", help="Show API library debug log messages", action="store_true"
    )

    group.add_argument(
        "--test",
        help="Run stress test against all connected Meshtastic devices",
        action="store_true",
    )

    group.add_argument(
        "--ble-scan",
        help="Scan for Meshtastic BLE devices",
        action="store_true",
    )

    group.add_argument(
        "--wait-to-disconnect",
        help="How many seconds to wait before disconnecting from the device.",
        const="5",
        nargs="?",
        action="store",
    )

    group.add_argument(
        "--noproto",
        help="Don't start the API, just function as a dumb serial terminal.",
        action="store_true",
    )

    group.add_argument(
        "--listen",
        help="Just stay open and listen to the protobuf stream. Enables debug logging.",
        action="store_true",
    )

    remoteHardwareArgs = parser.add_argument_group('Remote Hardware', 'Arguments related to the Remote Hardware module')

    remoteHardwareArgs.add_argument(
        "--gpio-wrb", nargs=2, help="Set a particular GPIO # to 1 or 0", action="append"
    )

    remoteHardwareArgs.add_argument(
        "--gpio-rd", help="Read from a GPIO mask (ex: '0x10')"
    )

    remoteHardwareArgs.add_argument(
        "--gpio-watch", help="Start watching a GPIO mask for changes (ex: '0x10')"
    )


    have_tunnel = platform.system() == "Linux"
    if have_tunnel:
        tunnelArgs = parser.add_argument_group('Tunnel', 'Arguments related to establishing a tunnel device over the mesh.')
        tunnelArgs.add_argument(
            "--tunnel",
            action="store_true",
            help="Create a TUN tunnel device for forwarding IP packets over the mesh",
        )
        tunnelArgs.add_argument(
            "--subnet",
            dest="tunnel_net",
            help="Sets the local-end subnet address for the TUN IP bridge. (ex: 10.115' which is the default)",
            default=None,
        )

    parser.set_defaults(deprecated=None)


    args = parser.parse_args()
    mt_config.args = args
    mt_config.parser = parser


def main():
    """Perform command line meshtastic operations"""
    parser = argparse.ArgumentParser(
        add_help=False,
        epilog="If no connection arguments are specified, we search for a compatible serial device, "
               "and if none is found, then attempt a TCP connection to localhost.")
    mt_config.parser = parser
    initParser()
    common()
    logfile = mt_config.logfile
    if logfile:
        logfile.close()


def tunnelMain():
    """Run a meshtastic IP tunnel"""
    parser = argparse.ArgumentParser(add_help=False)
    mt_config.parser = parser
    initParser()
    args = mt_config.args
    args.tunnel = True
    mt_config.args = args
    common()


if __name__ == "__main__":
    main()
