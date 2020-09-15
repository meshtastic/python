# Meshtastic-python

A python client for using [Meshtastic](https://www.meshtastic.org) devices. This small library (and example application) provides an easy API for sending and receiving messages over mesh radios. It also provides access to any of the operations/data available in the device user interface or the Android application. Events are delivered using a publish-subscribe model, and you can subscribe to only the message types you are interested in.

Full documentation including examples and installation instructions [here](https://meshtastic.github.io/Meshtastic-python/meshtastic/index.html).

But suffice it to say, it is really easy (note, you must use pip version 20 or later):

```
pip3 install --upgrade meshtastic
```

then run the following python3 code:

```
import meshtastic
interface = meshtastic.StreamInterface() # By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface.sendText("hello mesh") # or sendData to send binary data, see documentations for other options.
```

For the rough notes/implementation plan see [TODO](https://github.com/meshtastic/Meshtastic-python/blob/master/TODO.md).

## Command line tool

This pip package will also install a "meshtastic" commandline executable, which displays packets sent over the network as JSON and lets you see serial debugging information from the meshtastic devices. The source code for this tool is also a good [example](https://github.com/meshtastic/Meshtastic-python/blob/master/meshtastic/__main__.py) of a 'complete' application that uses the meshtastic python API.

You can also use this tool to set any of the device parameters which are stored in persistent storage. For instance, here's how to set the device
to keep the bluetooth link alive for eight hours (any usage of the bluetooth protcol from your phone will reset this timer)

```
meshtastic --set wait_bluetooth_secs 28800
Connected to radio...
Setting preference wait_bluetooth_secs to 28800
Writing modified preferences to device...
```

Or to configure an ESP32 based board to join a wifi network as a station (wifi support in the device code is coming soon):

```
meshtastic --set wifi_ap_mode false --setstr wifi_ssid mywifissid --setstr wifi_password mywifipsw
```

Or to configure an ESP32 to run as a Wifi access point:

```
meshtastic --set wifi_ap_mode true --setstr wifi_ssid mywifissid --setstr wifi_password mywifipsw
```

## Required device software version

This API and tool both require that the device is running Meshtastic 0.6.0 or later.
