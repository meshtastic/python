#!python3

import argparse
from .interface import StreamInterface
import logging


def main():
    """Perform command line meshtastic operations"""
    parser = argparse.ArgumentParser()

    # Operations for manufacturing
    parser.add_argument("--install", choices=['JR', 'JL', 'JM', 'JO', 'JG', 'JK', 'JY', 'JC', 'JT', 'MB', 'MS'],
                        help="Install the ezdevice code onto a new device (you must select the board type letter - see README.md)")
    parser.add_argument("--readee", action="store_true",
                        help="Extract the eeprom contents from the device, so it can be programmed onto other boards")

    # Operations for app developers
    parser.add_argument(
        "--target", help="The device we are controlling given as <ID>:<secretkey> (get the secret key at https://www.ezdevice.net/my/devices)")
    parser.add_argument(
        "--displayfile", help="display a text,html,png,svg or jpeg file on the display")
    # parser.add_argument("--displayURL", help="display a text,html,png,svg or jpeg from the web on the device")
    parser.add_argument(
        "--claim", help="Mark that this device is no longer being used for custom development", action="store_true")
    parser.add_argument(
        "--release", help="Mark that this device is no longer being used for custom development (i.e. return to joyframe demo app)", action="store_true")

    # Operations for server backend developers
    parser.add_argument("--localserve", help="Talk to a development server",
                        action="store_true")
    parser.add_argument("--debug", help="Show debug log message",
                        action="store_true")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    client = StreamInterface("/dev/ttyUSB0")


if __name__ == "__main__":
    main()
