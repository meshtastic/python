"""Look up local node position over TCP.

Purpose: demonstrate read-only position lookup via LAN/TCP.
Transport scope: TCP only.
Behavior: connects, reads local node position, prints it, then exits.
Expected output: position dict for local node.
Cleanup/error handling: explicit connect/read failures and clean close.
"""
# pylint: disable=duplicate-code

import argparse

import meshtastic.tcp_interface


def main() -> int:
    """Connect over TCP and print local node position."""
    parser = argparse.ArgumentParser(description="Print local node position over TCP")
    parser.add_argument(
        "--host",
        default="meshtastic.local",
        help="TCP hostname or IP (default: meshtastic.local)",
    )
    args = parser.parse_args()

    iface = None
    try:
        iface = meshtastic.tcp_interface.TCPInterface(args.host)
        my_node_num = iface.myInfo.my_node_num
        pos = iface.nodesByNum[my_node_num].get("position")
        if pos is None:
            print(f"No position available for local node {my_node_num}")
            return 1
        print(pos)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Error: Could not read position from {args.host}: {exc}")
        return 1
    finally:
        if iface:
            iface.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
