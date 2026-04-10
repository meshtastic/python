"""Simple text chat demo for meshtastic.
   To run: python examples/textchat.py
   To run with TCP: python examples/textchat.py --host 192.168.1.5
   To run with BLE: python examples/textchat.py --ble 24:62:AB:DD:DF:3A
"""

import argparse
from typing import Any, Optional, Union
from pubsub import pub
import meshtastic.serial_interface
import meshtastic.tcp_interface
import meshtastic.ble_interface
from meshtastic.mesh_interface import MeshInterface

def onReceive(packet: dict, interface: MeshInterface) -> None:  # pylint: disable=unused-argument
    """called when a packet arrives"""
    text: Optional[str] = packet.get("decoded", {}).get("text")
    if text:
        sender: str = packet.get("fromId", "unknown")
        print(f"{sender}: {text}")

def onConnection(interface: MeshInterface, topic: Any = pub.AUTO_TOPIC) -> None:  # pylint: disable=unused-argument
    """called when we (re)connect to the radio"""
    print("Connected. Type a message and press Enter to send. Ctrl+C to exit.")

parser = argparse.ArgumentParser(description="Meshtastic text chat demo")
group = parser.add_mutually_exclusive_group()
group.add_argument("--host", help="Connect via TCP to this hostname or IP")
group.add_argument("--ble", help="Connect via BLE to this MAC address or device name")

args = parser.parse_args()

pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")

iface: Optional[Union[
    meshtastic.tcp_interface.TCPInterface,
    meshtastic.ble_interface.BLEInterface,
    meshtastic.serial_interface.SerialInterface
]] = None

# defaults to serial, use --host for TCP or --ble for Bluetooth
try:
    if args.host:
        # note: timeout only applies after connection, not during the initial connect attempt
        # TCPInterface.myConnect() calls socket.create_connection() without a timeout
        iface = meshtastic.tcp_interface.TCPInterface(hostname=args.host, timeout=10)
    elif args.ble:
        iface = meshtastic.ble_interface.BLEInterface(address=args.ble, timeout=10)
    else:
        iface = meshtastic.serial_interface.SerialInterface(timeout=10)
except KeyboardInterrupt as exc:
    raise SystemExit(0) from exc
except Exception as e:
    print(f"Error: Could not connect. {e}")
    raise SystemExit(1) from e

assert iface is not None
try:
    while True:
        line = input()
        if line:
            iface.sendText(line)
except KeyboardInterrupt:
    pass
except EOFError:
    pass
finally:
    try:
        if iface:
            iface.close()
    except AttributeError:
        pass
