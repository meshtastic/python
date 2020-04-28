#!python3

import argparse
from .interface import StreamInterface
import logging
import sys
from pubsub import pub
import google.protobuf.json_format


def onReceive(packet):
    """Callback invoked when a packet arrives"""
    print(f"Received: {packet}")


def onConnection(topic=pub.AUTO_TOPIC):
    """Callback invoked when we connect/disconnect from a radio"""
    print(f"Connection changed: {topic.getName()}")


def onNode(node):
    """Callback invoked when the node DB changes"""
    print(f"Node changed: {node}")


def subscribe():
    """Subscribe to the topics the user probably wants to see, prints output to stdout"""
    pub.subscribe(onReceive, "meshtastic.receive")
    pub.subscribe(onConnection, "meshtastic.connection")
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

    parser.add_argument("--debug", help="Show API library debug log messages",
                        action="store_true")

    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    if args.seriallog == "stdout":
        logfile = sys.stdout
    elif args.seriallog == "none":
        logging.debug("Not logging serial output")
        logfile = None
    else:
        logging.info(f"Logging serial output to {args.seriallog}")
        logfile = open(args.seriallog, 'w+', buffering=1)  # line buffering

    subscribe()
    client = StreamInterface(args.device, debugOut=logfile)


if __name__ == "__main__":
    main()
