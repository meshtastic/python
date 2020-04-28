#!python3

import argparse
from .interface import StreamInterface
import logging
from time import sleep


def main():
    """Perform command line meshtastic operations"""
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--device",
        help="The port the Meshtastic device is connected to, i.e. /dev/ttyUSB0. If unspecified, we'll try to find it.",
        default=None)

    parser.add_argument("--debug", help="Show debug log message",
                        action="store_true")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    client = StreamInterface(args.device)


if __name__ == "__main__":
    main()
