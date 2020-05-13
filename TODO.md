# TODO

## Bluetooth support

(Alpha level feature)

- This library supports connecting to Meshtastic devices over either USB (serial) or Bluetooth. Before connecting to the device you must [pair](https://docs.ubuntu.com/core/en/stacks/bluetooth/bluez/docs/reference/pairing/outbound.html) your PC with it.
- We use the pip3 install "pygatt[GATTTOOL]"
- ./bin/run.sh --debug --ble --device 24:62:AB:DD:DF:3A

## Before beta

- document properties/fields
- include more examples: textchat.py, replymessage.py all as one little demo
- have device side StreamAPI client prevent radio sleep
- device side PhoneAPI should only allow message delivery to one connected device - currently breaks when you have BLE and serial connections
- announce at the usual places

## Soon after initial release

- keep nodedb up-to-date based on received MeshPackets
- handle radio reboots and redownload db when that happens. Look for a special FromRadio.rebooted packet

## Eventual

- possibly use tk to make a multiwindow test console: https://stackoverflow.com/questions/12351786/how-to-redirect-print-statements-to-tkinter-text-widget

## MeshtasticShell todos

- Possibly use multiple windows: https://stackoverflow.com/questions/12351786/how-to-redirect-print-statements-to-tkinter-text-widget
- make pingpong test

## Done

- DONE use port enumeration to find ports https://pyserial.readthedocs.io/en/latest/shortintro.html
- DONE make serial debug output optional (by providing a null stream)
- DONE make pubsub work
- DONE make docs decent
- DONE keep everything in dicts
- DONE have device send a special packet at boot so the serial client can detect if it rebooted
- DONE add fromId and toId to received messages dictionaries
- make command line options for displaying/changing config
- update nodedb as nodes change
- radioConfig - getter/setter syntax: https://www.python-course.eu/python3_properties.php
- let user change radio params via commandline options