"""Connect over TCP, print connection info once, then exit.

Purpose: demonstrate pubsub connection lifecycle callback.
Transport scope: TCP only.
Behavior: subscribe to `meshtastic.connection.established`, print `myInfo`, then close.
Expected output: one object/line showing local radio info after connect.
Cleanup/error handling: explicit connect failure message and clean close on callback.
"""

import argparse

from pubsub import pub
import meshtastic.tcp_interface


def on_connection(interface, topic=pub.AUTO_TOPIC):  # pylint: disable=unused-argument
    """Print local radio info when connected, then close."""
    print(interface.myInfo)
    interface.close()


def main() -> int:
    """Parse args, connect, and wait for established callback."""
    parser = argparse.ArgumentParser(description="Print radio info on TCP connect and exit")
    parser.add_argument("host", help="TCP hostname or IP of the Meshtastic node")
    args = parser.parse_args()

    pub.subscribe(on_connection, "meshtastic.connection.established")

    try:
        meshtastic.tcp_interface.TCPInterface(args.host)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Error: Could not connect to {args.host}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
