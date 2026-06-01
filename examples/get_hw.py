"""Print the local node hardware model.

Purpose: show the narrowest read-only local hardware lookup.
Transport scope: Serial only.
Behavior: reads local node metadata and prints hwModel.
Expected output: one hardware model line, if available.
Cleanup/error handling: exits with code 3 for bad args and closes interface on exit.
"""

import argparse
import sys

import meshtastic.serial_interface


def main() -> int:
    """Print the hardware model for the local node."""
    if len(sys.argv) != 1:
        print(f"usage: {sys.argv[0]}")
        print("Print the hardware model for the local node.")
        return 3

    parser = argparse.ArgumentParser(description="Print local Meshtastic hardware model")
    parser.parse_args()

    try:
        with meshtastic.serial_interface.SerialInterface() as iface:
            if iface.nodes:
                for node in iface.nodes.values():
                    if node["num"] == iface.myInfo.my_node_num:
                        print(node["user"]["hwModel"])
                        break
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Error: Could not read hardware model: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
