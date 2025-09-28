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
import threading
import time

from pubsub import pub

import meshtastic
import meshtastic.ble_interface

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
    # Subscribe to the connection change event
    pub.subscribe(on_connection_change, "meshtastic.connection.status")

    # The address of the device to connect to.
    # Replace with your device's address.
    address = "DD:DD:13:27:74:29" # TODO: Replace with your device's address

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

            # We must explicitly close the old interface before creating a new one
            iface.close()
            print("Interface closed. Reconnecting in 5 seconds...")
            time.sleep(5)

        except meshtastic.ble_interface.BLEInterface.BLEError as e:
            print(f"Connection failed: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("Exiting...")
            # Make sure to close the interface on exit
            if iface:
                iface.close()
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            if iface:
                iface.close()
            raise

if __name__ == "__main__":
    main()
