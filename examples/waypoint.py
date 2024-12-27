"""Program to create and delete waypoint
   To run:
   python3 examples/waypoint.py --port /dev/ttyUSB0 create 45 test the_desc_2 '2024-12-18T23:05:23' 48.74 7.35
   python3 examples/waypoint.py delete 45
"""

import argparse
import datetime
import sys

import meshtastic
import meshtastic.serial_interface

parser = argparse.ArgumentParser(
                    prog='waypoint',
                    description='Create and delete Meshtastic waypoint')
parser.add_argument('--port', default=None)
parser.add_argument('--debug', default=False, action='store_true')

subparsers = parser.add_subparsers(dest='cmd')
parser_delete = subparsers.add_parser('delete', help='Delete a waypoint')
parser_delete.add_argument('id', help="id of the waypoint")

parser_create = subparsers.add_parser('create', help='Create a new waypoint')
parser_create.add_argument('id', help="id of the waypoint")
parser_create.add_argument('name', help="name of the waypoint")
parser_create.add_argument('description', help="description of the waypoint")
parser_create.add_argument('expire', help="expiration date of the waypoint as interpreted by datetime.fromisoformat")
parser_create.add_argument('latitude', help="latitude of the waypoint")
parser_create.add_argument('longitude', help="longitude of the waypoint")

args = parser.parse_args()
print(args)

# By default will try to find a meshtastic device,
# otherwise provide a device path like /dev/ttyUSB0
if args.debug:
    d = sys.stderr
else:
    d = None
with meshtastic.serial_interface.SerialInterface(args.port, debugOut=d) as iface:
    if args.cmd == 'create':
        p = iface.sendWaypoint(
            waypoint_id=int(args.id),
            name=args.name,
            description=args.description,
            expire=int(datetime.datetime.fromisoformat(args.expire).timestamp()),
            latitude=float(args.latitude),
            longitude=float(args.longitude),
        )
    else:
        p = iface.deleteWaypoint(int(args.id))
    print(p)

# iface.close()
