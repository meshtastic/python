"""List serial ports currently visible to Meshtastic helpers.

Purpose: fastest host-side serial port enumeration.
Transport scope: none (host serial listing only).
Behavior: prints result of `findPorts()`.
Expected output: list-like representation of available candidate ports.
Cleanup/error handling: exits with code 1 on unexpected scan error.
"""

from meshtastic.util import findPorts


def main() -> int:
    """Print discovered serial ports."""
    try:
        print(findPorts())
    except Exception as exc:
        print(f"Error: Could not list ports: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
