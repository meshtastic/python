"""Simple mDNS advertiser for Meshtastic discovery tests-- Used this for ISSUE # 837 "mDNS resolve deeped CLI detail """
import argparse
import socket
import sys
import time
from typing import Dict

from zeroconf import ServiceInfo, Zeroconf


def build_properties(shortname: str, node_id: str, extra: Dict[str, str]) -> Dict[bytes, bytes]:
    data: Dict[bytes, bytes] = {
        b"shortname": shortname.encode("utf-8"),
        b"id": node_id.encode("utf-8"),
    }

    for key, value in extra.items():
        data[key.encode("utf-8")] = value.encode("utf-8")

    return data

### Basic node info for testing
def main() -> int:
    parser = argparse.ArgumentParser(description="Advertise a mock Meshtastic mDNS service.")
    parser.add_argument("--name", default="MockNode", help="Service instance name without type suffix")
    parser.add_argument("--shortname", default="MOCK", help="TXT record shortname value")
    parser.add_argument("--id", default="!deadbeef", help="TXT record id value")
    parser.add_argument("--port", type=int, default=4403, help="Service port")
    parser.add_argument(
        "--address",
        default="127.0.0.1",
        help="IPv4 address to advertise",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Seconds to keep the service advertised (0 keeps it running until Ctrl+C).",
    )
    parser.add_argument(
        "--firmware",
        default="2.3.0",
        help="Firmware version to test",
    )
    parser.add_argument(
        "--hardware",
        default="TBEAM",
        help="Hardware model to test",
    )
    parser.add_argument(
        "--platform",
        default="esp32",
        help="Platform/OS string to advertise",
    )
    parser.add_argument(
        "--last-heard",
        dest="last_heard",
        default="just now",
        help="Last heard string to advertise",
    )
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional TXT record entries (can be specified multiple times).",
    )

    args = parser.parse_args()
    extras: Dict[str, str] = {}
    for item in args.extra:
        if "=" not in item:
            parser.error(f"Invalid --extra entry '{item}', expected KEY=VALUE")
        key, value = item.split("=", 1)
        extras[key] = value

    extras.setdefault("firmware", args.firmware)
    extras.setdefault("hw_model", args.hardware)
    extras.setdefault("platform", args.platform)
    extras.setdefault("last_heard", args.last_heard)

    service_type = "_meshtastic._tcp.local."
    service_name = f"{args.name}.{service_type}"
    properties = build_properties(args.shortname, args.id, extras)

    zeroconf = Zeroconf()

    try:
        info = ServiceInfo(
            service_type,
            service_name,
            addresses=[socket.inet_aton(args.address)],
            port=args.port,
            properties=properties,
            server=f"{args.name.lower()}.local.",
        )
        zeroconf.register_service(info)
        print(f"Advertising {service_name} on {args.address}:{args.port} (Ctrl+C to stop)")
        if args.duration > 0:
            time.sleep(args.duration)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping advertiser (Ctrl+C received)...")
    finally:
        zeroconf.unregister_service(info)
        zeroconf.close()
        print("Advertiser stopped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
