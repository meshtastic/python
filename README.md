# Meshtastic-python

A python client for using Meshtastic devices. This small library (and example application) provides an easy API for sending and receiving messages over mesh radios. It also provides access to any of the operations/data available in the device user interface or the Android application. Events are delivered using a publish-subscribe model, and you can subscribe to only the message types you are interested in.

Full documentation including examples and installation instructions [here](https://meshtastic.github.io/Meshtastic-python/meshtastic/index.html).

But suffice it to say, it is really easy:

```
pip3 install meshtastic
```

then run the following python3 code:

```
import meshtastic
interface = meshtastic.StreamInterface() # By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
interface.sendData("hello world")
```

For the rough notes/implementation plan see [TODO](./TODO.md).

## Command line tool

This pip package will also install a "meshtastic" commandline executable, which displays packets sent over the network as JSON and lets you see serial debugging information from the meshtastic devices. The source code for this tool is also a good [example](./meshtastic/__main__.py) of a 'complete' application that uses the meshtastic python API.
