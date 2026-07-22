"""Send once on connect and print received packets over TCP.

Purpose: demonstrate pubsub send-on-connect plus receive callback flow.
Transport scope: TCP only.
Behavior: sends "hello mesh" at connect, prints packets while running.
Expected output: "Connected..." plus "Received: ..." lines for inbound packets.
Cleanup/error handling: graceful Ctrl+C exit and clean interface close.
"""

import argparse
import time

from pubsub import pub
from meshtastic.tcp_interface import TCPInterface


def on_receive(packet, interface):  # pylint: disable=unused-argument
    """Print each inbound packet."""
    print(f"Received: {packet}")


def on_connection(interface, topic=pub.AUTO_TOPIC):  # pylint: disable=unused-argument
    """Send a broadcast text when connected."""
    print("Connected. Sending one broadcast message.")
    interface.sendText("hello mesh")


def main() -> int:
    """Parse args, connect via TCP, and run callbacks."""
    parser = argparse.ArgumentParser(description="TCP pubsub send-and-receive example")
    parser.add_argument("host", help="TCP hostname or IP of the Meshtastic node")
    args = parser.parse_args()

    pub.subscribe(on_receive, "meshtastic.receive")
    pub.subscribe(on_connection, "meshtastic.connection.established")

    iface = None
    try:
        iface = TCPInterface(hostname=args.host)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Error: Could not connect to {args.host}: {exc}")
        return 1
    finally:
        if iface:
            iface.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
