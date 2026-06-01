"""Show a concise local node summary over serial.

Purpose: read local node identity and metadata in one place.
Transport scope: Serial only.
Behavior: reads node database, prints local node ID/name/hardware model.
Expected output: 1-3 summary lines describing the local node.
Cleanup/error handling: closes interface on exit and prints clear errors on failure.
"""

import meshtastic.serial_interface


def main() -> int:
    """Print local node summary fields."""
    try:
        with meshtastic.serial_interface.SerialInterface() as iface:
            local_num = iface.myInfo.my_node_num
            local_node = None
            if iface.nodes:
                for node in iface.nodes.values():
                    if node["num"] == local_num:
                        local_node = node
                        break

            if not local_node:
                print(f"Local node not found in node database (node num: {local_num}).")
                return 1

            user = local_node.get("user", {})
            print(f"Node number: {local_num}")
            print(f"Node ID: {local_node.get('id', 'unknown')}")
            print(
                "Name: "
                f"{user.get('longName', 'unknown')} ({user.get('shortName', 'unknown')})"
            )
            print(f"Hardware model: {user.get('hwModel', 'unknown')}")
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Error: Could not read local node summary: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
