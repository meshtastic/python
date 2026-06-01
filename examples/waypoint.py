"""Create or delete a waypoint.

Purpose: demonstrate waypoint mutation API (create/delete).
Transport scope: Serial only.
Behavior: sends waypoint create/delete request and prints API response.
Expected output: request response object printed to stdout.
Cleanup/error handling: explicit argument parsing and clean interface close.
"""

import argparse
import datetime
import sys

import meshtastic
import meshtastic.serial_interface

parser = argparse.ArgumentParser(
    prog="waypoint", description="Create and delete Meshtastic waypoint"
)
parser.add_argument("--port", default=None)
parser.add_argument("--debug", default=False, action="store_true")

subparsers = parser.add_subparsers(dest="cmd", required=True)
parser_delete = subparsers.add_parser("delete", help="Delete a waypoint")
parser_delete.add_argument("id", type=int, help="ID of the waypoint")

parser_create = subparsers.add_parser("create", help="Create a new waypoint")
parser_create.add_argument("id", type=int, help="ID of the waypoint")
parser_create.add_argument("name", help="Name of the waypoint")
parser_create.add_argument("description", help="Description of the waypoint")
parser_create.add_argument("icon", help="Icon of the waypoint")
parser_create.add_argument(
    "expire",
    help="Expiration time as ISO timestamp accepted by datetime.fromisoformat",
)
parser_create.add_argument("latitude", type=float, help="Latitude of the waypoint")
parser_create.add_argument("longitude", type=float, help="Longitude of the waypoint")

args = parser.parse_args()

# By default will try to find a meshtastic device,
# otherwise provide a device path like /dev/ttyUSB0
if args.debug:
    d = sys.stderr
else:
    d = None
with meshtastic.serial_interface.SerialInterface(args.port, debugOut=d) as iface:
    if args.cmd == "create":
        p = iface.sendWaypoint(
            waypoint_id=args.id,
            name=args.name,
            description=args.description,
            icon=args.icon,
            expire=int(datetime.datetime.fromisoformat(args.expire).timestamp()),
            latitude=args.latitude,
            longitude=args.longitude,
        )
    else:
        p = iface.deleteWaypoint(args.id)
    print(p)
