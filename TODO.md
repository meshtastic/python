# TODO

Basic functionality is complete now.

## Eventual tasks

- Improve documentation on properties/fields
- include more examples: textchat.py, replymessage.py all as one little demo

- possibly use tk to make a multiwindow test console: https://stackoverflow.com/questions/12351786/how-to-redirect-print-statements-to-tkinter-text-widget

## MeshtasticShell todos

- Possibly use multiple windows: https://stackoverflow.com/questions/12351786/how-to-redirect-print-statements-to-tkinter-text-widget
- make pingpong test

## Bluetooth support

- ./bin/run.sh --ble-scan # To look for Meshtastic devices
- ./bin/run.sh --ble 24:62:AB:DD:DF:3A --info

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
- localConfig - getter/setter syntax: https://www.python-course.eu/python3_properties.php
- let user change radio params via commandline options
- keep nodedb up-to-date based on received MeshPackets
- handle radio reboots and redownload db when that happens. Look for a special FromRadio.rebooted packet
