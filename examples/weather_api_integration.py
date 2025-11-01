import requests
import meshtastic
import meshtastic.serial_interface

# ---- Get weather data ----
lat, lon = 9.9312, 76.2673  
url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=relative_humidity_2m"

response = requests.get(url)
data = response.json()

temp = data["current_weather"]["temperature"]
humidity = data["hourly"]["relative_humidity_2m"][0]

message = f" Weather: {temp}°C, {humidity}% humidity"

# ---- Send over Meshtastic ----
iface = meshtastic.serial_interface.SerialInterface()
iface.sendText(message)

print("Sent:", message)
iface.close()
