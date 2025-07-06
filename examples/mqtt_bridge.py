# Meshtastic MQTT Packet Bridge Example
#
# This script connects to a Meshtastic MQTT broker, subscribes to mesh topics,
# and prints (optionally decrypts) incoming packets.
#
# Dependencies:
#   pip install paho-mqtt cryptography meshtastic --user
#
# Usage:
#   python mqtt-read.py
#
# Edit BROKER, USER, PASS, TOPICS, and KEY as needed for your setup.
# See https://github.com/meshtastic/Meshtastic-python for more info.
# ---------------------------------------------------------------

import paho.mqtt.client as mqtt
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from meshtastic.protobuf import mqtt_pb2, mesh_pb2
from meshtastic import protocols
from google.protobuf.json_format import MessageToDict
import pprint
import datetime
import os
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()

BROKER = os.getenv("MQTT_BROKER", "mqtt.smartcitizen.me")
USER = os.getenv("MQTT_USER", "")
PASS = os.getenv("MQTT_PASS", "")
PORT = int(os.getenv("MQTT_PORT", 1883))

TOPICS = os.getenv("MQTT_TOPICS", "device/sck/mesh12/2/#").split(",")
KEY = os.getenv("MQTT_KEY", "")
KEY = "" if KEY == "AQ==" else KEY


# Map of device IDs to friendly names
# This is a dictionary that maps device IDs to their friendly names only for debuggin purposes during the hackathon.
DEVICE_NAME_MAP = {
    # Example: device_id: "Friendly Name"
    2534365592: "mesh25-jm (jm25)",
    3665041700: "Meshtastic 1924 (1924)",
    2925623876: "mesh25-ze (zerg)"
    # Add more mappings as needed
}

# Add these color codes near the top, after imports
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"

# Callback when the client connects to the broker
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker!")
        for topic in TOPICS:
            client.subscribe(topic)
            print(f"Subscribed to topic: {topic}")
    else:
        print(f"Failed to connect, return code {rc}")

# Callback when a message is received
def on_message(client, userdata, msg):
    se = mqtt_pb2.ServiceEnvelope()
    print (msg.payload)
    se.ParseFromString(msg.payload)
    print ('---')
    decoded_mp = se.packet

    # Try to decrypt the payload if it is encrypted
    if decoded_mp.HasField("encrypted") and not decoded_mp.HasField("decoded"):
        decoded_data = decrypt_packet(decoded_mp, KEY)
        if decoded_data is None:
            print("Decryption failed; retaining original encrypted payload")
        else:
            decoded_mp.decoded.CopyFrom(decoded_data)

    # Attempt to process the decrypted or encrypted payload
    portNumInt = decoded_mp.decoded.portnum if decoded_mp.HasField("decoded") else None
    handler = protocols.get(portNumInt) if portNumInt else None

    pb = None
    if handler is not None and handler.protobufFactory is not None:
        pb = handler.protobufFactory()
        pb.ParseFromString(decoded_mp.decoded.payload)

    if pb:
        # Pretty print the protobuf as a dictionary with extra identifying info
        pb_dict = MessageToDict(pb, preserving_proto_field_name=True)
        decoded_mp.decoded.payload = str(pb_dict).encode("utf-8")

        # Gather extra info if available
        device_id = getattr(decoded_mp, "from", None)
        packet_id = getattr(decoded_mp, "id", None)
        timestamp = pb_dict.get("time") or pb_dict.get("timestamp")
        iso_time = None
        if timestamp:
            try:
                iso_time = datetime.datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass

        print(f"{BOLD}{CYAN}=== Meshtastic Packet Info ==={RESET}")
        print(f"{BOLD}🔑 Device ID:{RESET} {device_id}")
        # Pretty print device name using the map
        device_name = DEVICE_NAME_MAP.get(device_id, f"{RED}Unknown device{RESET}")
        print(f"{BOLD}📟 Device Name:{RESET} {device_name}")
        print(f"{BOLD}🗂️ Packet ID:{RESET} {packet_id}")
        print(f"{BOLD}⏰ Timestamp:{RESET} {iso_time if iso_time else 'N/A'}")
        print(f"{BOLD}📡 Port Number:{RESET} {portNumInt if portNumInt is not None else 'N/A'}")

        # portnum_name = None
        # if portNumInt is not None:
        #     try:
        #         portnum_name = mesh_pb2.PortNum.Name(portNumInt)
        #     except Exception:
        #         portnum_name = "UNKNOWN"
        # print(f"{BOLD}📡 Port Number:{RESET} {portNumInt if portNumInt is not None else 'N/A'} ({portnum_name})")

        print(f"{BOLD}📦 Full protobuf payload:{RESET}")
        pprint.pprint(pb_dict, sort_dicts=False, indent=2)

        

        # Only print transformed SC payload if portNumInt == 67 (TELEMETRY_APP)
        # Todo: Change for Protobuf definition.
        if portNumInt == 67:
            print(f"{BOLD}🔄 Transformed SC payload:{RESET}")
            print(transform_meshtastic_json(pb_dict))
       

def decrypt_packet(mp, key):
    try:
        key_bytes = base64.b64decode(key.encode('ascii'))

        # Build the nonce from message ID and sender
        nonce_packet_id = getattr(mp, "id").to_bytes(8, "little")
        nonce_from_node = getattr(mp, "from").to_bytes(8, "little")
        nonce = nonce_packet_id + nonce_from_node

        # Decrypt the encrypted payload
        cipher = Cipher(algorithms.AES(key_bytes), modes.CTR(nonce), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_bytes = decryptor.update(getattr(mp, "encrypted")) + decryptor.finalize()

        # Parse the decrypted bytes into a Data object
        data = mesh_pb2.Data()
        data.ParseFromString(decrypted_bytes)
        return data

    except Exception as e:
        return None

def transform_meshtastic_json(pb_dict):
    """
    Transforms Meshtastic-style dictionary into the desired output format.
    Maps sensor names (with their parent key) to IDs and converts unix time to ISO8601.
    Only includes sensors present in SENSOR_ID_MAP.
    """
    SENSOR_ID_MAP = {
        "air_quality_metrics.co2": 99,
        "device_metrics.voltage": 98,
        # Extend this mapping as needed, e.g. "env.pm25": 100
    }

    sensors = []
    for top_key, sub_dict in pb_dict.items():
        if isinstance(sub_dict, dict):
            for sensor_name, value in sub_dict.items():
                map_key = f"{top_key}.{sensor_name}"
                if map_key in SENSOR_ID_MAP:
                    sensors.append({
                        "id": SENSOR_ID_MAP[map_key],
                        "value": value
                    })

    # Convert unix time to ISO8601 UTC string
    recorded_at = None
    if "time" in pb_dict:
        recorded_at = datetime.datetime.utcfromtimestamp(pb_dict["time"]).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "data": [
            {
                "recorded_at": recorded_at,
                "sensors": sensors
            }
        ]
    }

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(USER, PASS)
try:
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_forever()
except Exception as e:
    print(f"An error occurred: {e}")