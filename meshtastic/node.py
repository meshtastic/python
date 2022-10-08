"""Node class
"""

import logging
import base64
import time
from google.protobuf.json_format import MessageToJson
from meshtastic import portnums_pb2, apponly_pb2, admin_pb2, channel_pb2, localonly_pb2
from meshtastic.util import pskToString, stripnl, Timeout, our_exit, fromPSK


class Node:
    """A model of a (local or remote) node in the mesh

    Includes methods for localConfig, moduleConfig and channels
    """

    def __init__(self, iface, nodeNum, noProto=False):
        """Constructor"""
        self.iface = iface
        self.nodeNum = nodeNum
        self.localConfig = localonly_pb2.LocalConfig()
        self.moduleConfig = localonly_pb2.LocalModuleConfig()
        self.channels = None
        self._timeout = Timeout(maxSecs=300)
        self.partialChannels = None
        self.noProto = noProto
        self.cannedPluginMessage = None

        self.cannedPluginMessageMessages = None

        self.gotResponse = None

    def showChannels(self):
        """Show human readable description of our channels."""
        print("Channels:")
        if self.channels:
            logging.debug(f'self.channels:{self.channels}')
            for c in self.channels:
                #print('c.settings.psk:', c.settings.psk)
                cStr = stripnl(MessageToJson(c.settings))
                # only show if there is no psk (meaning disabled channel)
                if c.settings.psk:
                    print(f"  {channel_pb2.Channel.Role.Name(c.role)} psk={pskToString(c.settings.psk)} {cStr}")
        publicURL = self.getURL(includeAll=False)
        adminURL = self.getURL(includeAll=True)
        print(f"\nPrimary channel URL: {publicURL}")
        if adminURL != publicURL:
            print(f"Complete URL (includes all channels): {adminURL}")

    def showInfo(self):
        """Show human readable description of our node"""
        prefs = ""
        if self.localConfig:
            prefs = stripnl(MessageToJson(self.localConfig))
        print(f"Preferences: {prefs}\n")
        prefs = ""
        if self.moduleConfig:
            prefs = stripnl(MessageToJson(self.moduleConfig))
        print(f"Module preferences: {prefs}\n")
        self.showChannels()

    def requestConfig(self):
        """Send regular MeshPackets to ask for settings and channels."""
        logging.debug(f"requestConfig for nodeNum:{self.nodeNum}")
        self.channels = None
        self.partialChannels = []  # We keep our channels in a temp array until finished

        self._requestChannel(0)

    def turnOffEncryptionOnPrimaryChannel(self):
        """Turn off encryption on primary channel."""
        self.channels[0].settings.psk = fromPSK("none")
        print("Writing modified channels to device")
        self.writeChannel(0)

    def waitForConfig(self, attribute='channels'):
        """Block until radio config is received. Returns True if config has been received."""
        return self._timeout.waitForSet(self, attrs=('localConfig', attribute))

    def writeConfig(self):
        """Write the current (edited) localConfig to the device"""
        if self.localConfig is None:
            our_exit("Error: No localConfig has been read")

        if self.localConfig.device:
            p = admin_pb2.AdminMessage()
            p.set_config.device.CopyFrom(self.localConfig.device)
            self._sendAdmin(p)
            logging.debug("Wrote device")
            time.sleep(0.3)

        if self.localConfig.position:
            p = admin_pb2.AdminMessage()
            p.set_config.position.CopyFrom(self.localConfig.position)
            self._sendAdmin(p)
            logging.debug("Wrote position")
            time.sleep(0.3)

        if self.localConfig.power:
            p = admin_pb2.AdminMessage()
            p.set_config.power.CopyFrom(self.localConfig.power)
            self._sendAdmin(p)
            logging.debug("Wrote power")
            time.sleep(0.3)

        if self.localConfig.network:
            p = admin_pb2.AdminMessage()
            p.set_config.network.CopyFrom(self.localConfig.network)
            self._sendAdmin(p)
            logging.debug("Wrote network")
            time.sleep(0.3)

        if self.localConfig.display:
            p = admin_pb2.AdminMessage()
            p.set_config.display.CopyFrom(self.localConfig.display)
            self._sendAdmin(p)
            logging.debug("Wrote display")
            time.sleep(0.3)

        if self.localConfig.lora:
            p = admin_pb2.AdminMessage()
            p.set_config.lora.CopyFrom(self.localConfig.lora)
            self._sendAdmin(p)
            logging.debug("Wrote lora")
            time.sleep(0.3)

        if self.localConfig.bluetooth:
            p = admin_pb2.AdminMessage()
            p.set_config.bluetooth.CopyFrom(self.localConfig.bluetooth)
            self._sendAdmin(p)
            logging.debug("Wrote bluetooth")
            time.sleep(0.3)

        if self.moduleConfig.mqtt:
            p = admin_pb2.AdminMessage()
            p.set_module_config.mqtt.CopyFrom(self.moduleConfig.mqtt)
            self._sendAdmin(p)
            logging.debug("Wrote module: mqtt")
            time.sleep(0.3)

        if self.moduleConfig.serial:
            p = admin_pb2.AdminMessage()
            p.set_module_config.serial.CopyFrom(self.moduleConfig.serial)
            self._sendAdmin(p)
            logging.debug("Wrote module: serial")
            time.sleep(0.3)

        if self.moduleConfig.external_notification:
            p = admin_pb2.AdminMessage()
            p.set_module_config.external_notification.CopyFrom(self.moduleConfig.external_notification)
            self._sendAdmin(p)
            logging.debug("Wrote module: external_notification")
            time.sleep(0.3)
        
        if self.moduleConfig.store_forward:
            p = admin_pb2.AdminMessage()
            p.set_module_config.store_forward.CopyFrom(self.moduleConfig.store_forward)
            self._sendAdmin(p)
            logging.debug("Wrote module: store_forward")
            time.sleep(0.3)
        
        if self.moduleConfig.range_test:
            p = admin_pb2.AdminMessage()
            p.set_module_config.range_test.CopyFrom(self.moduleConfig.range_test)
            self._sendAdmin(p)
            logging.debug("Wrote module: range_test")
            time.sleep(0.3)

        if self.moduleConfig.telemetry:
            p = admin_pb2.AdminMessage()
            p.set_module_config.telemetry.CopyFrom(self.moduleConfig.telemetry)
            self._sendAdmin(p)
            logging.debug("Wrote module: telemetry")
            time.sleep(0.3)

        if self.moduleConfig.canned_message:
            p = admin_pb2.AdminMessage()
            p.set_module_config.canned_message.CopyFrom(self.moduleConfig.canned_message)
            self._sendAdmin(p)
            logging.debug("Wrote module: canned_message")
            time.sleep(0.3)

    def writeConfig(self, config_name):
        """Write the current (edited) localConfig to the device"""
        if self.localConfig is None:
            our_exit("Error: No localConfig has been read")

        p = admin_pb2.AdminMessage()

        if config_name == 'device':
            p.set_config.device.CopyFrom(self.localConfig.device)
        elif config_name == 'position':
            p.set_config.position.CopyFrom(self.localConfig.position)
        elif config_name == 'power':
            p.set_config.power.CopyFrom(self.localConfig.power)
        elif config_name == 'network':
            p.set_config.network.CopyFrom(self.localConfig.network)
        elif config_name == 'display':
            p.set_config.display.CopyFrom(self.localConfig.display)
        elif config_name == 'lora':
            p.set_config.lora.CopyFrom(self.localConfig.lora)
        elif config_name == 'bluetooth':
            p.set_config.bluetooth.CopyFrom(self.localConfig.bluetooth)
        elif config_name == 'mqtt':
            p.set_module_config.mqtt.CopyFrom(self.moduleConfig.mqtt)
        elif config_name == 'serial':
            p.set_module_config.serial.CopyFrom(self.moduleConfig.serial)
        elif config_name == 'external_notification':
            p.set_module_config.external_notification.CopyFrom(self.moduleConfig.external_notification)
        elif config_name == 'store_forward':
            p.set_module_config.store_forward.CopyFrom(self.moduleConfig.store_forward)
        elif config_name == 'range_test':
            p.set_module_config.range_test.CopyFrom(self.moduleConfig.range_test)
        elif config_name == 'telemetry':
            p.set_module_config.telemetry.CopyFrom(self.moduleConfig.telemetry)
        elif config_name == 'canned_message':
            p.set_module_config.canned_message.CopyFrom(self.moduleConfig.canned_message)
        else:
            our_exit(f"Error: No valid config with name {config_name}")
        
        logging.debug(f"Wrote: {config_name}")
        self._sendAdmin(p)

    def writeChannel(self, channelIndex, adminIndex=0):
        """Write the current (edited) channel to the device"""

        p = admin_pb2.AdminMessage()
        p.set_channel.CopyFrom(self.channels[channelIndex])
        self._sendAdmin(p, adminIndex=adminIndex)
        logging.debug(f"Wrote channel {channelIndex}")

    def getChannelByChannelIndex(self, channelIndex):
        """Get channel by channelIndex
            channelIndex: number, typically 0-7; based on max number channels
            returns: None if there is no channel found
        """
        ch = None
        if self.channels and 0 <= channelIndex < len(self.channels):
            ch = self.channels[channelIndex]
        return ch

    def deleteChannel(self, channelIndex):
        """Delete the specifed channelIndex and shift other channels up"""
        ch = self.channels[channelIndex]
        if ch.role not in (channel_pb2.Channel.Role.SECONDARY, channel_pb2.Channel.Role.DISABLED):
            our_exit("Warning: Only SECONDARY channels can be deleted")

        # we are careful here because if we move the "admin" channel the channelIndex we need to use
        # for sending admin channels will also change
        adminIndex = self.iface.localNode._getAdminChannelIndex()

        self.channels.pop(channelIndex)
        self._fixupChannels()  # expand back to 8 channels

        index = channelIndex
        while index < self.iface.myInfo.max_channels:
            self.writeChannel(index, adminIndex=adminIndex)
            index += 1

            # if we are updating the local node, we might end up
            # *moving* the admin channel index as we are writing
            if (self.iface.localNode == self) and index >= adminIndex:
                # We've now passed the old location for admin index
                # (and written it), so we can start finding it by name again
                adminIndex = 0

    def getChannelByName(self, name):
        """Try to find the named channel or return None"""
        for c in (self.channels or []):
            if c.settings and c.settings.name == name:
                return c
        return None

    def getDisabledChannel(self):
        """Return the first channel that is disabled (i.e. available for some new use)"""
        for c in self.channels:
            if c.role == channel_pb2.Channel.Role.DISABLED:
                return c
        return None

    def _getAdminChannelIndex(self):
        """Return the channel number of the admin channel, or 0 if no reserved channel"""
        c = self.getChannelByName("admin")
        if c:
            return c.index
        else:
            return 0

    def setOwner(self, long_name=None, short_name=None, is_licensed=False):
        """Set device owner name"""
        logging.debug(f"in setOwner nodeNum:{self.nodeNum}")
        nChars = 3
        minChars = 2
        if long_name is not None:
            long_name = long_name.strip()
            if short_name is None:
                words = long_name.split()
                if len(long_name) <= nChars:
                    short_name = long_name
                elif len(words) >= minChars:
                    short_name = ''.join(map(lambda word: word[0], words))
                else:
                    trans = str.maketrans(dict.fromkeys('aeiouAEIOU'))
                    short_name = long_name[0] + long_name[1:].translate(trans)
                    if len(short_name) < nChars:
                        short_name = long_name[:nChars]

        p = admin_pb2.AdminMessage()

        if long_name is not None:
            p.set_owner.long_name = long_name
        if short_name is not None:
            short_name = short_name.strip()
            if len(short_name) > nChars:
                short_name = short_name[:nChars]
            p.set_owner.short_name = short_name
            p.set_owner.is_licensed = is_licensed

        # Note: These debug lines are used in unit tests
        logging.debug(f'p.set_owner.long_name:{p.set_owner.long_name}:')
        logging.debug(f'p.set_owner.short_name:{p.set_owner.short_name}:')
        logging.debug(f'p.set_owner.is_licensed:{p.set_owner.is_licensed}')
        return self._sendAdmin(p)

    def getURL(self, includeAll: bool = True):
        """The sharable URL that describes the current channel"""
        # Only keep the primary/secondary channels, assume primary is first
        channelSet = apponly_pb2.ChannelSet()
        if self.channels:
            for c in self.channels:
                if c.role == channel_pb2.Channel.Role.PRIMARY or (includeAll and c.role == channel_pb2.Channel.Role.SECONDARY):
                    channelSet.settings.append(c.settings)

        channelSet.lora_config.CopyFrom(self.localConfig.lora)
        some_bytes = channelSet.SerializeToString()
        s = base64.urlsafe_b64encode(some_bytes).decode('ascii')
        s = s.replace("=", "").replace("+", "-").replace("/", "_")
        return f"https://www.meshtastic.org/e/#{s}"

    def setURL(self, url):
        """Set mesh network URL"""
        if self.localConfig is None:
            our_exit("Warning: No Config has been read")

        # URLs are of the form https://www.meshtastic.org/d/#{base64_channel_set}
        # Split on '/#' to find the base64 encoded channel settings
        splitURL = url.split("/#")
        b64 = splitURL[-1]

        # We normally strip padding to make for a shorter URL, but the python parser doesn't like
        # that.  So add back any missing padding
        # per https://stackoverflow.com/a/9807138
        missing_padding = len(b64) % 4
        if missing_padding:
            b64 += '=' * (4 - missing_padding)

        decodedURL = base64.urlsafe_b64decode(b64)
        channelSet = apponly_pb2.ChannelSet()
        channelSet.ParseFromString(decodedURL)


        if len(channelSet.settings) == 0:
            our_exit("Warning: There were no settings.")

        i = 0
        for chs in channelSet.settings:
            ch = channel_pb2.Channel()
            ch.role = channel_pb2.Channel.Role.PRIMARY if i == 0 else channel_pb2.Channel.Role.SECONDARY
            ch.index = i
            ch.settings.CopyFrom(chs)
            self.channels[ch.index] = ch
            logging.debug(f'Channel i:{i} ch:{ch}')
            self.writeChannel(ch.index)
            i = i + 1

        p = admin_pb2.AdminMessage()
        p.set_config.lora.CopyFrom(channelSet.lora_config)
        self._sendAdmin(p)

    def onResponseRequestCannedMessagePluginMessageMessages(self, p):
        """Handle the response packet for requesting canned message plugin message part 1"""
        logging.debug(f'onResponseRequestCannedMessagePluginMessageMessages() p:{p}')
        errorFound = False
        if "routing" in p["decoded"]:
            if p["decoded"]["routing"]["errorReason"] != "NONE":
                errorFound = True
                print(f'Error on response: {p["decoded"]["routing"]["errorReason"]}')
        if errorFound is False:
            if "decoded" in p:
                if "admin" in p["decoded"]:
                    if "raw" in p["decoded"]["admin"]:
                        self.cannedPluginMessageMessages = p["decoded"]["admin"]["raw"].get_canned_message_module_messages_response
                        logging.debug(f'self.cannedPluginMessageMessages:{self.cannedPluginMessageMessages}')
                        self.gotResponse = True


    def get_canned_message(self):
        """Get the canned message string. Concatenate all pieces together and return a single string."""
        logging.debug(f'in get_canned_message()')
        if not self.cannedPluginMessage:

            p1 = admin_pb2.AdminMessage()
            p1.get_canned_message_module_messages_request = True
            self.gotResponse = False
            self._sendAdmin(p1, wantResponse=True, onResponse=self.onResponseRequestCannedMessagePluginMessageMessages)
            while self.gotResponse is False:
                time.sleep(0.1)

            logging.debug(f'self.cannedPluginMessageMessages:{self.cannedPluginMessageMessages}')

            self.cannedPluginMessage = ""
            if self.cannedPluginMessageMessages:
                self.cannedPluginMessage += self.cannedPluginMessageMessages

        print(f'canned_plugin_message:{self.cannedPluginMessage}')
        logging.debug(f'canned_plugin_message:{self.cannedPluginMessage}')
        return self.cannedPluginMessage

    def set_canned_message(self, message):
        """Set the canned message. The canned messages length must be less than 200 character."""

        if len(message) > 200:
            our_exit("Warning: The canned message must be less than 200 characters.")

        # split into chunks
        chunks = []
        chunks_size = 200
        for i in range(0, len(message), chunks_size):
            chunks.append(message[i: i + chunks_size])

        # for each chunk, send a message to set the values
        #for i in range(0, len(chunks)):
        for i, chunk in enumerate(chunks):
            p = admin_pb2.AdminMessage()

            # TODO: should be a way to improve this
            if i == 0:
                p.set_canned_message_module_messages = chunk

            logging.debug(f"Setting canned message '{chunk}' part {i+1}")
            self._sendAdmin(p)

    def exitSimulator(self):
        """Tell a simulator node to exit (this message
           is ignored for other nodes)"""
        p = admin_pb2.AdminMessage()
        p.exit_simulator = True
        logging.debug('in exitSimulator()')

        return self._sendAdmin(p)

    def reboot(self, secs: int = 10):
        """Tell the node to reboot."""
        p = admin_pb2.AdminMessage()
        p.reboot_seconds = secs
        logging.info(f"Telling node to reboot in {secs} seconds")

        return self._sendAdmin(p)

    def shutdown(self, secs: int = 10):
        """Tell the node to shutdown."""
        p = admin_pb2.AdminMessage()
        p.shutdown_seconds = secs
        logging.info(f"Telling node to shutdown in {secs} seconds")

        return self._sendAdmin(p)

    def getMetadata(self, secs: int = 10):
        """Tell the node to shutdown."""
        p = admin_pb2.AdminMessage()
        p.get_device_metadata_request = True
        logging.info(f"Requesting device metadata")

        return self._sendAdmin(p, wantResponse=True, onResponse=self.onRequestGetMetadata)

    def factoryReset(self):
        """Tell the node to factory reset."""
        p = admin_pb2.AdminMessage()
        p.factory_reset = True
        logging.info(f"Telling node to factory reset")

        return self._sendAdmin(p)   

    def resetNodeDb(self):
        """Tell the node to reset its list of nodes."""
        p = admin_pb2.AdminMessage()
        p.nodedb_reset = True
        logging.info(f"Telling node to reset the NodeDB")

        return self._sendAdmin(p)

    def _fixupChannels(self):
        """Fixup indexes and add disabled channels as needed"""

        # Add extra disabled channels as needed
        # TODO: These 2 lines seem to not do anything.
        for index, ch in enumerate(self.channels):
            ch.index = index  # fixup indexes

        self._fillChannels()

    def _fillChannels(self):
        """Mark unused channels as disabled"""

        # Add extra disabled channels as needed
        index = len(self.channels)
        while index < self.iface.myInfo.max_channels:
            ch = channel_pb2.Channel()
            ch.role = channel_pb2.Channel.Role.DISABLED
            ch.index = index
            self.channels.append(ch)
            index += 1


    def onRequestGetMetadata(self, p):
        """Handle the response packet for requesting device metadata getMetadata()"""
        logging.debug(f'onRequestGetMetadata() p:{p}')

        if p["decoded"]["portnum"] == portnums_pb2.PortNum.Name(portnums_pb2.PortNum.ROUTING_APP):
            if p["decoded"]["routing"]["errorReason"] != "NONE":
                logging.warning(f'Metadata request failed, error reason: {p["decoded"]["routing"]["errorReason"]}')
                self._timeout.expireTime = time.time() # Do not wait any longer
                return # Don't try to parse this routing message
            logging.debug(f"Retrying metadata request.")
            self.getMetadata()
            return 
            
        c = p["decoded"]["admin"]["raw"].get_device_metadata_response
        self._timeout.reset()  # We made foreward progress
        logging.debug(f"Received metadata {stripnl(c)}")
        print(f"\nfirmware_version: {c.firmware_version}")
        print(f"device_state_version: {c.device_state_version}")

    def onResponseRequestChannel(self, p):
        """Handle the response packet for requesting a channel _requestChannel()"""
        logging.debug(f'onResponseRequestChannel() p:{p}')

        if p["decoded"]["portnum"] == portnums_pb2.PortNum.Name(portnums_pb2.PortNum.ROUTING_APP):
            if p["decoded"]["routing"]["errorReason"] != "NONE":
                logging.warning(f'Channel request failed, error reason: {p["decoded"]["routing"]["errorReason"]}')
                self._timeout.expireTime = time.time() # Do not wait any longer
                return # Don't try to parse this routing message
            lastTried = 0
            if len(self.partialChannels) > 0:
                lastTried = self.partialChannels[-1]
            logging.debug(f"Retrying previous channel request.")
            self._requestChannel(lastTried)
            return

        c = p["decoded"]["admin"]["raw"].get_channel_response
        self.partialChannels.append(c)
        self._timeout.reset()  # We made foreward progress
        logging.debug(f"Received channel {stripnl(c)}")
        index = c.index

        # for stress testing, we can always download all channels
        fastChannelDownload = True

        # Once we see a response that has NO settings, assume
        # we are at the end of channels and stop fetching
        quitEarly = (c.role == channel_pb2.Channel.Role.DISABLED) and fastChannelDownload

        if quitEarly or index >= self.iface.myInfo.max_channels - 1:
            logging.debug("Finished downloading channels")

            self.channels = self.partialChannels
            self._fixupChannels()

            # FIXME, the following should only be called after we have settings and channels
            self.iface._connected()  # Tell everyone else we are ready to go
        else:
            self._requestChannel(index + 1)

    def _requestChannel(self, channelNum: int):
        """Done with initial config messages, now send regular
           MeshPackets to ask for settings"""
        p = admin_pb2.AdminMessage()
        p.get_channel_request = channelNum + 1

        # Show progress message for super slow operations
        if self != self.iface.localNode:
            print(f"Requesting channel {channelNum} info from remote node (this could take a while)")
            logging.debug(f"Requesting channel {channelNum} info from remote node (this could take a while)")
        else:
            logging.debug(f"Requesting channel {channelNum}")

        return self._sendAdmin(p, wantResponse=True, onResponse=self.onResponseRequestChannel)


    # pylint: disable=R1710
    def _sendAdmin(self, p: admin_pb2.AdminMessage, wantResponse=False,
                   onResponse=None, adminIndex=0):
        """Send an admin message to the specified node (or the local node if destNodeNum is zero)"""

        if self.noProto:
            logging.warning(f"Not sending packet because protocol use is disabled by noProto")
        else:
            if adminIndex == 0:  # unless a special channel index was used, we want to use the admin index
                adminIndex = self.iface.localNode._getAdminChannelIndex()
            logging.debug(f'adminIndex:{adminIndex}')

            return self.iface.sendData(p, self.nodeNum,
                                       portNum=portnums_pb2.PortNum.ADMIN_APP,
                                       wantAck=True,
                                       wantResponse=wantResponse,
                                       onResponse=onResponse,
                                       channelIndex=adminIndex)
