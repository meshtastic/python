"""
This example shows how to implement a robust client-side reconnection loop for a
long-running application that uses the BLE interface.

The key is to instantiate the BLEInterface with `auto_reconnect=True` (the default).
This prevents the library from calling `close()` on the entire interface when a
disconnect occurs. Instead, it cleans up the underlying BLE client and notifies
listeners via the `onConnection` event with a `connected=False` payload.

The application can then listen for this event and attempt to create a new
BLEInterface instance to re-establish the connection, as shown in this example.
"""
import argparse
import logging
import threading
import time

from pubsub import pub

import meshtastic
import meshtastic.ble_interface

# Retry delay in seconds when connection fails
RETRY_DELAY_SECONDS = 5

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# A thread-safe flag to signal disconnection
disconnected_event = threading.Event()

def on_connection_change(interface, connected):
    """Callback for connection changes."""
    iface_label = getattr(interface, "address", repr(interface))
    print(f"Connection changed for {iface_label}: {'Connected' if connected else 'Disconnected'}")
    if not connected:
        # Signal the main loop that we've been disconnected
        disconnected_event.set()

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Meshtastic BLE automatic reconnection example.")
    parser.add_argument("address", help="The BLE address of your Meshtastic device.")
    args = parser.parse_args()
    address = args.address

    # Subscribe to the connection change event
    pub.subscribe(on_connection_change, "meshtastic.connection.status")

    iface = None
    while True:
        try:
            disconnected_event.clear()
            print(f"Attempting to connect to {address}...")
            # Set auto_reconnect=True to prevent the interface from closing on disconnect.
            # This allows us to handle the reconnection here.
            iface = meshtastic.ble_interface.BLEInterface(
                address,
                noProto=True, # Set to False in a real application
                auto_reconnect=True
            )

            print("Connection successful. Waiting for disconnection event...")
            # Wait until the on_connection_change callback signals a disconnect
            disconnected_event.wait()
            print("Disconnected normally.")

        except KeyboardInterrupt:
            print("Exiting...")
            break
        except meshtastic.ble_interface.BLEInterface.BLEError:
            logger.exception("Connection failed")
        except Exception:
            logger.exception("An unexpected error occurred")
        finally:
            if iface:
                iface.close()
                print("Interface closed.")

        print(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
        time.sleep(RETRY_DELAY_SECONDS)

if __name__ == "__main__":
    main()
