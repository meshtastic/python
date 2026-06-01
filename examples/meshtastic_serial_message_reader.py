#!/usr/bin/env python3
"""Passively monitor incoming text messages over serial.

Purpose: receive-only monitor for text messages.
Transport scope: Serial only.
Behavior: subscribes to text receive events and prints timestamp/channel/sender/text.
Expected output: one line per received text message.
Cleanup/error handling: graceful Ctrl+C exit and explicit connection errors.
"""

import argparse
import time
from datetime import datetime
from typing import Any, Optional

from pubsub import pub
import meshtastic.serial_interface

_TZ_NAME = time.tzname[time.localtime().tm_isdst > 0]


def on_receive(packet: dict[str, Any], interface: Any) -> None:  # pylint: disable=unused-argument
    """Print a compact line for each received text packet."""
    decoded = packet.get("decoded", {})
    if decoded.get("portnum") != "TEXT_MESSAGE_APP":
        return

    message = decoded.get("text")
    if not message:
        return

    channel_num = packet.get("channel", 0)
    sender_id = packet.get("fromId", "unknown")
    message_time = datetime.now().strftime(f"%a %b %d %Y %H:%M:%S {_TZ_NAME}")
    print(f"{message_time} : {channel_num} : {sender_id} : {message}")


def main() -> int:
    """Connect over serial and print inbound text messages."""
    parser = argparse.ArgumentParser(description="Read incoming Meshtastic text over serial")
    parser.add_argument("--port", default=None, help="Serial port path (default: auto-detect)")
    args = parser.parse_args()

    pub.subscribe(on_receive, "meshtastic.receive")

    iface: Optional[meshtastic.serial_interface.SerialInterface] = None
    try:
        iface = meshtastic.serial_interface.SerialInterface(devPath=args.port)
        print("Connected. Listening for text messages. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Error: Could not monitor serial messages: {exc}")
        return 1
    finally:
        if iface:
            iface.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
