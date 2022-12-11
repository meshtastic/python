"""Simple program to demo how to send a signed message.
   To run: python examples/signed_message_example.py
"""

import sys
import meshtastic
import meshtastic.serial_interface
from nacl.signing import SigningKey
from nacl.encoding import HexEncoder

# simple arg check
if len(sys.argv) < 2:
    print(f"usage: {sys.argv[0]} message")
    sys.exit(3)

# By default will try to find a meshtastic device,
# otherwise provide a device path like /dev/ttyUSB0
iface = meshtastic.serial_interface.SerialInterface()

signing_key = SigningKey.generate()

# Convert the text message to bytes and sign it with the private key
text_message_bytes = sys.argv[1].encode('utf-8')

# Sign a message with the signing key
signed = signing_key.sign(text_message_bytes, encoder=HexEncoder)

# Obtain the verify key for a given signing key
verify_key = signing_key.verify_key

# Serialize the verify key to send it to a third party
verify_key_b64 = verify_key.encode(encoder=HexEncoder)

signed_message_bytes = signed + verify_key_b64

iface.sendSignedText(signed_message_bytes, wantAck=True)

iface.close()
