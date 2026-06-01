"""Send one text message over serial.

Purpose: minimal send-only example.
Transport scope: Serial only.
Behavior: sends one message and exits.
Expected output: no output on success.
Cleanup/error handling: exits with code 3 for bad args, closes interface on exit.
"""

import argparse
import sys

import meshtastic.serial_interface


def main() -> int:
    """Parse arguments and send one text message."""
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} message")
        return 3

    parser = argparse.ArgumentParser(description="Send one Meshtastic text message over serial")
    parser.add_argument("message", help="Message text to broadcast")
    args = parser.parse_args()

    try:
        with meshtastic.serial_interface.SerialInterface() as iface:
            iface.sendText(args.message)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Error: Could not send message: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
