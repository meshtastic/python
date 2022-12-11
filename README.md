# Black Lager Python App

## Overview
A Python messaging client for use with radio devices flashed with the [Black Lager firmware](https://github.com/black-lager/firmware).
Provides an application that allows you to send and receive text messages with digital signatures. 
The messages are verified and displayed in a text based interface created with Curses.

## Supported hardware
* LILYGO Lora v2.1-1.6
* LILYGO T-Beam

Note: Other models listed at https://meshtastic.org/docs/supported-hardware may also work, but they have not been tested with the Black Lager firmware or application

## Connect to device
Connect your computer to a radio device flashed with the Black Lager firmware via USB cable.
For more information on hardware and firmware, see: https://github.com/black-lager/firmware

## Installation
### Clone the repo
`git clone git@github.com:meshtastic/python.git`

### Install dependencies
`pip3 install -r requirements.txt`

## Running the app
`python3 black_lager_app.py`

## Commands
![Help is here!](https://github.com/datagod/meshtalk/blob/main/pics/Meshtalk%20help%20window%20send%20message.jpg?raw=true "Help")

## Screen Layout
The screen has 5 areas of scrolling text.

## Top Row
![Top Row](https://github.com/datagod/meshtalk/blob/main/pics/Meshtalk%20messages.jpg?raw=true "Top Row")

The top row has basic information messages from the system, a debug area that shows the currently executing function, and a spot to show incoming messages.


## Decoded Packets
![Decoded Packets](https://github.com/datagod/meshtalk/blob/main/pics/Meshtalk%20packet.jpg?raw=true "Packet values")

Each packet that is intercepted will be displayed here in, decoded.  Some fields such as RAW are not supported yet.  This type of window is using a wrap around function to display the new lines.


## Extended Info
![Just the Keys](https://github.com/datagod/meshtalk/blob/main/pics/Meshtalk%20extended%20info.jpg?raw=true "Extended Info")

This is a curses text pad that scrolls upwards as new lines are entered.  In this example I am displaying the connected nodes in the mesh.

This is a curses text pad that scrolls upwards as new lines are entered.  In this example I am displaying the connected nodes in the mesh.

## Send Messages
Press S to send a signed message or U to send an unsigned message.  Press control+g when you are finished typing the message.

## Viewing Messages
![Messages](https://github.com/datagod/meshtalk/blob/main/pics/Meshtalk%20help%20window%20send%20message%202.jpg?raw=true "Messages")

As both signed and unsigned messages are sent or received, they are displayed in the Messages text box.
