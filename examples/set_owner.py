"""Set local owner long/short name over serial.

Purpose: demonstrate a local config mutation workflow.
Transport scope: Serial only.
Behavior: updates owner long name and optional short name.
Expected output: prints the owner values being applied.
Cleanup/error handling: exits with code 3 for bad args and closes interface on exit.
"""

import argparse
import sys

import meshtastic.serial_interface


def main() -> int:
    """Parse args and set owner fields."""
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} long_name [short_name]")
        return 3

    parser = argparse.ArgumentParser(description="Set Meshtastic local owner information")
    parser.add_argument("long_name", help="Owner long name")
    parser.add_argument("short_name", nargs="?", default=None, help="Owner short name")
    args = parser.parse_args()

    print(f"Setting owner long_name={args.long_name}, short_name={args.short_name}")
    try:
        with meshtastic.serial_interface.SerialInterface() as iface:
            iface.localNode.setOwner(args.long_name, args.short_name)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Error: Could not set owner: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
