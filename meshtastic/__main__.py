#!python3

import argparse
from .interface import StreamInterface
import logging
from time import sleep


def main():
    """Perform command line meshtastic operations"""
    parser = argparse.ArgumentParser()

    parser.add_argument("--debug", help="Show debug log message",
                        action="store_true")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    client = StreamInterface("/dev/ttyUSB0")


#             self.sendText("hello world")

if __name__ == "__main__":
    main()
