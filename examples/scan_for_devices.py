"""Scan host serial hardware for supported Meshtastic devices.

Purpose: host-side discovery without opening a radio session.
Transport scope: none (OS/device scanning only).
Behavior: scans vendor IDs, lists matched devices, and candidate active ports.
Expected output: vendor ID list, zero-or-more detected devices, and port list.
Cleanup/error handling: exits with code 3 for bad args and code 1 on scan errors.
"""

import argparse
import sys

from meshtastic.util import (
    active_ports_on_supported_devices,
    detect_supported_devices,
    get_unique_vendor_ids,
)


def main() -> int:
    """Run device detection and print candidate ports."""
    if len(sys.argv) != 1:
        print(f"usage: {sys.argv[0]}")
        print("Detect which device we might have.")
        return 3

    parser = argparse.ArgumentParser(description="Scan host for supported Meshtastic devices")
    parser.parse_args()

    try:
        vids = get_unique_vendor_ids()
        print(f"Searching for all devices with these vendor ids {vids}")

        supported_devices = detect_supported_devices()
        if supported_devices:
            print("Detected possible devices:")
            for device in supported_devices:
                print(
                    f" name:{device.name}{device.version} firmware:{device.for_firmware}"
                )
        else:
            print("Detected possible devices: none")

        ports = active_ports_on_supported_devices(supported_devices)
        print(f"ports:{ports}")
    except Exception as exc:
        print(f"Error: device scan failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
