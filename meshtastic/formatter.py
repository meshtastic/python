import json

from meshtastic.util import pskToString, check_if_newer_version
from meshtastic.protobuf import channel_pb2

"""Defines the formatting of outputs using factories"""

class FormatterFactory():
    """Factory of formatters"""
    def __init__(self):
        self.formatters = {
            "json": FormatAsJson,
            "default": FormatAsText
        }

    def getFormatter(self, formatSpec: str):
        """returns the formatter for info data. If no valid formatter is found, default to text"""
        return self.formatters.get(formatSpec.lower(), self.formatters["default"])


class InfoFormatter():
    """responsible to format info data"""
    def format(self, data: dict, formatSpec: str | None = None) -> str:
        """returns formatted string according to formatSpec for info data"""
        if not formatSpec:
            formatSpec = 'default'
        formatter = FormatterFactory().getFormatter(formatSpec)
        return formatter().formatInfo(data)


class FormatAsJson():
    """responsible to return the data as JSON string"""
    def formatInfo(self, data: dict) -> str:
        """Info as JSON"""

        # Remove the bytes entry of PSK before serialization of JSON
        for c in data['Channels']:
            del c['psk']
        jsonData = json.dumps(data, indent=2)
        print(jsonData)
        return jsonData


class FormatAsText():
    """responsible to print the data. No string return"""
    def formatInfo(self, data: dict) -> str:
        """Info printed as plain text"""
        print("")
        self.showMeshInfo(data)
        self.showNodeInfo(data)
        print("")
        pypi_version = check_if_newer_version()
        if pypi_version:
            print(
                f"*** A newer version v{pypi_version} is available!"
                ' Consider running "pip install --upgrade meshtastic" ***\n'
            )
        return ""

    def showMeshInfo(self, data: dict):
        """Show human-readable summary about mesh interface data"""
        owner = f"Owner: {data['Owner'][0]}({data['Owner'][1]})"

        myinfo = ""
        if dx := data.get('My Info', None) is not None:
            myinfo = f"My info: {json.dumps(dx)}"

        metadata = ""
        if dx := data.get('Metadata', None) is not None:
            metadata = f"Metadata: {json.dumps(dx)}"

        mesh = f"\nNodes in mesh:{json.dumps(data.get('Nodes', {}), indent=2)}"

        infos = f"{owner}\n{myinfo}\n{metadata}\n{mesh}"
        print(infos)

    def showNodeInfo(self, data: dict):
        """Show human-readable description of our node"""
        if dx := data.get('Preferences', None) is not None:
            print(f"Preferences: {json.dumps(dx, indent=2)}")

        if dx := data.get('Module preferences', None) is not None:
            print(f"Module preferences: {json.dumps(dx, indent=2)}")

        if dx := data.get('Channels', None) is not None:
            print("Channels:")
            for idx, c in enumerate(dx):
                if channel_pb2.Channel.Role.Name(c['role']) != "DISABLED":
                    print(f"  Index {idx}: {channel_pb2.Channel.Role.Name(c['role'])} psk={pskToString(c['psk'])} {json.dumps(c['settings'])}")
            print("")
            publicURL = data['publicURL']
            print(f"\nPrimary channel URL: {publicURL}")
            adminURL = data['adminURL']
            if adminURL != publicURL:
                print(f"Complete URL (includes all channels): {adminURL}")
