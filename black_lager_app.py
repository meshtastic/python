#!/usr/bin/env python3

from persona_wallet import PersonaWallet
from textwindow import TextWindow
from textpad import TextPad
from utils import *
import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
import time
from datetime import datetime
import traceback
from pubsub import pub
import argparse
import collections
import sys
import os
import pickle

# to review logfiles
import subprocess

# for calculating distance
import geopy.distance

# For capturing key presses and drawing text boxes
import curses
from curses.textpad import Textbox

# for capturing ctl-c
from signal import signal, SIGINT
from sys import exit

# PyNaCl libsodium library
from nacl_suite import NaclSuite

from nacl.encoding import HexEncoder
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

NAME = "BlackLager"
DESCRIPTION = "Send and receive signed and unsigned messages from a Meshtastic device."
DEBUG = False

parser = argparse.ArgumentParser(description=DESCRIPTION)
parser.add_argument('-s', '--send', type=str, help="send a text message")
parser.add_argument('-t', '--time', type=int,
                    help="seconds to listen before exiting", default=36000)
ifparser = parser.add_mutually_exclusive_group(required=False)
ifparser.add_argument('-p', '--port', type=str,
                      help="port the Meshtastic device is connected to (e.g., /dev/ttyUSB0)")
ifparser.add_argument('-i', '--host', type=str,
                      help="hostname/ipaddr of the device to connect to over TCP")
args = parser.parse_args()

# process arguments and assign values to local variables
if args.send:
    SendMessage = True
    TheMessage = args.send
else:
    SendMessage = False

TimeToSleep = args.time


global PrintSleep  # controls how fast the screens scroll
global OldPrintSleep  # controls how fast the screens scroll
global TitleWindow
global StatusWindow
global Window1
global Window2
global Window3
global Window4
global Window5
global Window6
global Pad1
global InputMessageBox
global INputMessageWindow
global IPAddress
global Interface
global DeviceStatus
global DeviceName
global DevicePort
global PacketsReceived
global PacketsSent
global LastPacketType
global BaseLat
global BaseLon

global MacAddress
global DeviceID

global PauseOutput
global PriorityOutput


PrintSleep = 0.1
OldPrintSleep = PrintSleep

# Create Persona wallet
wallet = PersonaWallet()


# --------------------------------------
# Initialize Text window / pads      --
# --------------------------------------

def create_text_windows():

    global StatusWindow
    global TitleWindow
    global Window1
    global Window2
    global Window3
    global Window4
    global Window5
    global HelpWindow
    global Pad1
    global SendMessageWindow
    global InputMessageWindow
    global InputMessageBox

    # Colors are numbered, and start_color() initializes 8
    # basic colors when it activates color mode.
    # They are: 0:black, 1:red, 2:green, 3:yellow, 4:blue, 5:magenta, 6:cyan, and 7:white.
    # The curses module defines named constants for each of these colors: curses.COLOR_BLACK, curses.COLOR_RED, and so forth.
    # Future Note for pads:  call noutrefresh() on a number of windows to update the data structure, and then call doupdate() to update the screen.

    # Text windows

    stdscr.nodelay(1)  # doesn't keep waiting for a key press
    curses.start_color()
    curses.noecho()

    # We do a quick check to prevent the screen boxes from being erased.  Weird, I know.  Could not find
    # a solution.  Am happy with this work around.
    c = str(stdscr.getch())

    # Note: When making changes, be very careful.  Each Window's position is relative to the other ones on the same
    # horizontal level.  Change one setting at a time and see how it looks on your screen

    # Window1 Coordinates (info window)
    Window1Height = 12
    Window1Length = 40
    Window1x1 = 0
    Window1y1 = 1
    Window1x2 = Window1x1 + Window1Length
    Window1y2 = Window1y1 + Window1Height

    # Window2 Coordinates (small debug window)
    Window2Height = 12
    Window2Length = 46
    Window2x1 = Window1x2 + 1
    Window2y1 = 1
    Window2x2 = Window2x1 + Window2Length
    Window2y2 = Window2y1 + Window2Height

    # Window3 Coordinates (Messages)
    Window3Height = 12
    Window3Length = 104
    Window3x1 = Window2x2 + 1
    Window3y1 = 1
    Window3x2 = Window3x1 + Window3Length
    Window3y2 = Window3y1 + Window3Height

    # Window4 Coordinates (packet data)
    Window4Height = 45
    #Window4Length = Window1Length + Window2Length + Window3Length + 2
    Window4Length = 60
    Window4x1 = 0
    Window4y1 = Window1y2
    Window4x2 = Window4x1 + Window4Length
    Window4y2 = Window4y1 + Window4Height

    # We are going to put a window here as a border, but have the pad
    # displayed inside
    # Window5 Coordinates (to the right of window4)
    Window5Height = 45
    Window5Length = 95
    Window5x1 = Window4x2 + 1
    Window5y1 = Window4y1
    Window5x2 = Window5x1 + Window5Length
    Window5y2 = Window5y1 + Window5Height

    # Coordinates (scrolling pad/window for showing keys being decoded)
    Pad1Columns = Window5Length - 2
    Pad1Lines = Window5Height - 2
    Pad1x1 = Window5x1+1
    Pad1y1 = Window5y1+1
    Pad1x2 = Window5x2 - 1
    Pad1y2 = Window5y2 - 1

    # Help Window
    HelpWindowHeight = 13
    HelpWindowLength = 35
    HelpWindowx1 = Window5x2 + 1
    HelpWindowy1 = Window5y1
    HelpWindowx2 = HelpWindowx1 + HelpWindowLength
    HelpWindowy2 = HelpWindowy1 + HelpWindowHeight

    # SendMessage Window
    # This window will be used to display the border
    # and title and will surround the input window
    SendMessageWindowHeight = 6
    SendMessageWindowLength = 35
    SendMessageWindowx1 = Window5x2 + 1
    SendMessageWindowy1 = HelpWindowy1 + HelpWindowHeight
    SendMessageWindowx2 = SendMessageWindowx1 + SendMessageWindowLength
    SendMessageWindowy2 = SendMessageWindowy1 + SendMessageWindowHeight

    # InputMessage Window
    # This window will be used get the text to be sent
    InputMessageWindowHeight = SendMessageWindowHeight - 2
    InputMessageWindowLength = SendMessageWindowLength - 2
    InputMessageWindowx1 = Window5x2 + 2
    InputMessageWindowy1 = HelpWindowy1 + HelpWindowHeight + 1
    InputMessageWindowx2 = InputMessageWindowx1 + InputMessageWindowLength - 2
    InputMessageWindowy2 = InputMessageWindowy1 + InputMessageWindowHeight - 2

    try:

        # stdscr.clear()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)

        # --------------------------------------
        # Draw Screen                        --
        # --------------------------------------

        # Create windows
        # name,  rows,      columns,   y1,    x1,    y2,    x2,ShowBorder,BorderColor,TitleColor):
        TitleWindow = TextWindow('TitleWindow', 1, 50, 0, 0, 0, 50, 'N', 0, 0, stdscr)
        StatusWindow = TextWindow(
            'StatusWindow', 1, 50, 0, 51, 0, 100, 'N', 0, 0, stdscr)
        StatusWindow2 = TextWindow(
            'StatusWindow2', 1, 30, 0, 101, 0, 130, 'N', 0, 0, stdscr)
        Window1 = TextWindow('Window1', Window1Height, Window1Length,
                             Window1y1, Window1x1, Window1y2, Window1x2, 'Y', 2, 2, stdscr)
        Window2 = TextWindow('Window2', Window2Height, Window2Length,
                             Window2y1, Window2x1, Window2y2, Window2x2, 'Y', 2, 2, stdscr)
        Window3 = TextWindow('Window3', Window3Height, Window3Length,
                             Window3y1, Window3x1, Window3y2, Window3x2, 'Y', 3, 3, stdscr)
        Window4 = TextWindow('Window4', Window4Height, Window4Length,
                             Window4y1, Window4x1, Window4y2, Window4x2, 'Y', 5, 5, stdscr)
        Window5 = TextWindow('Window5', Window5Height, Window5Length,
                             Window5y1, Window5x1, Window5y2, Window5x2, 'Y', 6, 6, stdscr)
        HelpWindow = TextWindow('HelpWindow', HelpWindowHeight, HelpWindowLength,
                                HelpWindowy1, HelpWindowx1, HelpWindowy2, HelpWindowx2, 'Y', 7, 7, stdscr)
        SendMessageWindow = TextWindow('SendMessageWindow', SendMessageWindowHeight, SendMessageWindowLength,
                                       SendMessageWindowy1, SendMessageWindowx1, SendMessageWindowy2, SendMessageWindowx2, 'Y', 7, 7, stdscr)
        InputMessageWindow = TextWindow('InputMessageWindow', InputMessageWindowHeight, InputMessageWindowLength,
                                        InputMessageWindowy1, InputMessageWindowx1, InputMessageWindowy2, InputMessageWindowx2, 'N', 7, 7, stdscr)
        Pad1 = TextPad('Pad1', Pad1Lines, Pad1Columns,
                       Pad1y1, Pad1x1, Pad1y2, Pad1x2, 'N', 5, stdscr)

        # each title needs to be initialized or you get errors in scrollprint
        TitleWindow.Title,   TitleWindow.TitleColor = "--Black Lager--", 2
        StatusWindow.Title,  StatusWindow.TitleColor = "", 2
        StatusWindow2.Title, StatusWindow2.TitleColor = "", 2
        Window1.Title, Window1.TitleColor = "Device Info", 2
        Window2.Title, Window2.TitleColor = "Debug", 2
        Window3.Title, Window3.TitleColor = "Messages", 3
        Window4.Title, Window4.TitleColor = "Data Packets", 5
        Window5.Title, Window5.TitleColor = "Extended Information", 6
        HelpWindow.Title, HelpWindow.TitleColor = "Help", 7
        SendMessageWindow.Title, SendMessageWindow.TitleColor = "Press S to send a message", 7

        TitleWindow.window_print(0, 0, TitleWindow.Title)
        Window1.display_title()
        Window2.display_title()
        Window3.display_title()
        Window4.display_title()
        Window5.display_title()
        HelpWindow.display_title()
        SendMessageWindow.display_title()

        display_help_info()

        # Prepare edit window for send message
        InputMessageBox = Textbox(InputMessageWindow.TextWindow)

    except Exception as ErrorMessage:
        TraceMessage = traceback.format_exc()
        AdditionalInfo = "Creating text windows"
        error_handler(ErrorMessage, TraceMessage, AdditionalInfo, stdscr)


# --------------------------------------
# Meshtastic functions               --
# --------------------------------------


def decode_packet(PacketParent, Packet, Filler, FillerChar, PrintSleep=0):
    global DeviceStatus
    global DeviceName
    global DevicePort
    global PacketsReceived
    global PacketsSent
    global LastPacketType
    global HardwareModel
    global DeviceID

    # This is a recursive function that will decode a packet (get key/value pairs from a dictionary)
    # if the value is itself a dictionary, recurse
    Window2.scroll_print("DecodePacket", 2, TimeStamp=True)

    # used to indent packets
    if (PacketParent.upper() != 'MAINPACKET'):
        Filler = Filler + FillerChar

    #Window4.scroll_print("{}".format(PacketParent).upper(), 2)
    update_status_window(NewLastPacketType=PacketParent)

    # adjust the input to slow down the output for that cool retro feel
    if (PrintSleep > 0):
        time.sleep(PrintSleep)

    if PriorityOutput == True:
        time.sleep(5)

    # if the packet is a dictionary, decode it
    if isinstance(Packet, collections.abc.Mapping):

        for Key in Packet.keys():
            Value = Packet.get(Key)

            if (PrintSleep > 0):
                time.sleep(PrintSleep)

            # if the value paired with this key is another dictionary, keep digging
            if isinstance(Value, collections.abc.Mapping):

                # Print the name/type of the packet
                #Window4.scroll_print(" ", 2)
                LastPacketType = Key.upper()

                decode_packet("{}/{}".format(PacketParent, Key).upper(), Value, Filler, FillerChar, PrintSleep=PrintSleep)

            # else:
            #     # Print KEY if not RAW (gotta decode those further, or ignore)
            #     if (Key == 'raw'):
            #         #Window4.scroll_print("{}  RAW value not yet suported by DecodePacket function".format(Filler), 2)
            #     else:
            #         #Window4.scroll_print("  {}{}: {}".format(Filler, Key, Value), 2)

    else:
        Window2.scroll_print("Warning: Not a packet!", 5, TimeStamp=True)


def on_receive(packet, interface):
    """Called when a new packet arrives"""
    global PacketsReceived
    global PacketsSent

    PacketsReceived = PacketsReceived + 1

    Window2.scroll_print("onReceive", 2, TimeStamp=True)
    #Window4.scroll_print(" ", 2)
    #Window4.scroll_print("==Packet RECEIVED======================================", 2)

    decoded = packet.get('decoded')
    unsigned_message = decoded.get('text')
    portnum = decoded.get('portnum')

    sender = packet.get('from')

    # Recursively decode all the packets of packets
    decode_packet('MainPacket', packet, Filler='', FillerChar='', PrintSleep=PrintSleep)

    if unsigned_message:
        Window3.scroll_print("UNSIGNED message from: {} - {}".format(sender, unsigned_message), 2, TimeStamp=True)
    elif portnum == "BLACK_LAGER":
        signed_message = decoded.get('payload')
        # Split the concatenated byte string into the message and key
        signed_b64 = signed_message[:-64]
        verify_key_b64 = signed_message[-64:]

        # Create a VerifyKey object from a base64 serialized public key
        verify_key = VerifyKey(verify_key_b64, encoder=HexEncoder)

        # Check the validity of a message's signature
        try:
            text_message_bytes = verify_key.verify(signed_b64, encoder=HexEncoder)
            text_message = text_message_bytes.decode('utf-8')
            Window3.scroll_print("VERIFIED SIGNED message from: {} - {}".format(sender, text_message), 2, TimeStamp=True)
        except BadSignatureError:
            Window3.scroll_print("Signature from {} was forged or corrupt".format(sender), 2, TimeStamp=True)

    #Window4.scroll_print("=======================================================", 2)
    #Window4.scroll_print(" ", 2)


# called when we (re)connect to the radio
def on_connection_established(interface, topic=pub.AUTO_TOPIC):
    global PriorityOutput

    if not PriorityOutput:
        update_status_window(NewDeviceStatus="CONNECTED", Color=2)

        From = "BaseStation"
        To = "All"
        current_time = datetime.now().strftime("%H:%M:%S")
        Message = "MeshWatch active,  please respond. [{}]".format(
            current_time)
        Window3.scroll_print("From: {} - {}".format(From,
                                                    Message, To), 2, TimeStamp=True)

        try:
            interface.sendText(Message, wantAck=True)
            #Window4.scroll_print("", 2)
            #Window4.scroll_print("==Packet SENT==========================================", 3)
            #Window4.scroll_print("To:     {}:".format(To), 3)
            #Window4.scroll_print("From    {}:".format(From), 3)
            #Window4.scroll_print("Message {}:".format(Message), 3)
            #Window4.scroll_print("=======================================================", 3)
            #Window4.scroll_print("", 2)

        except Exception as ErrorMessage:
            TraceMessage = traceback.format_exc()
            AdditionalInfo = "Sending text message ({})".format(Message)
            error_handler(ErrorMessage, TraceMessage, AdditionalInfo, stdscr)


# called when we (re)connect to the radio
def on_connection_lost(interface, topic=pub.AUTO_TOPIC):
    global PriorityOutput
    if (PriorityOutput == False):
        Window2.scroll_print('onConnectionLost', 2, TimeStamp=True)
        update_status_window(NewDeviceStatus="DISCONNECTED", Color=1)


# called when we (re)connect to the radio
def on_node_update(interface, topic=pub.AUTO_TOPIC):
    global PriorityOutput
    if (PriorityOutput == False):
        Window2.scroll_print('onNodeUpdated', 2, TimeStamp=True)
        Window1.window_print(1, 4, 'UPDATE RECEIVED', 1, TimeStamp=True)
        #Window4.scroll_print("", 2)


def sigint_handler(signal_received, frame):
    # Handle any cleanup here
    print('WARNING: Somethign bad happened.  SIGINT detected.')
    final_cleanup(stdscr)
    print('** END OF LINE')
    sys.exit('Meshwatch exiting...')


def poll_keyboard():
    global stdscr
    global Window2
    global interface

    return_char = ""

    # curses.filter()
    curses.noecho()

    try:
        c = chr(stdscr.getch())
    except Exception as ErrorMessage:
        c = ""

    # Look for digits (ascii 48-57 == digits 0-9)
    if (c >= '0' and c <= '9'):
        #print ("Digit detected")
        #StatusWindow.ScrollPrint("Digit Detected",2)
        return_char = c

    if (c != ""):
        #print ("----------------")
        #print ("Key Pressed: ",Key)
        #print ("----------------")
        OutputLine = "Key Pressed: " + c
        # Window2.ScrollPrint(OutputLine,4)
        process_keypress(c)
    return return_char


def process_keypress(key):
    # c = clear screen
    # i = get node info
    # l = show system LOGS (dmesg)
    # n = show all nodes in mesh
    # p = pause
    # q = quit
    # r = reboot
    # u = Send unsigned message
    # s = Send signed message
    # t = test messages
    # k = send keys

    global stdscr
    global StatusWindow
    global Window2
    global Window4
    global interface
    global PauseOutput
    global PriorityOutput
    global PrintSleep
    global OldPrintSleep

    output_line = "KEYPRESS: [" + str(key) + "]"
    Window2.scroll_print(output_line, 5)

    if key == "p" or key == " ":
        PauseOutput = not PauseOutput
        if PauseOutput:
            Window2.scroll_print("Pausing output", 2)
            StatusWindow.window_print(0, 0, "** Output SLOW - press SPACE again to cancel **", 1)
            PrintSleep = PrintSleep * 3
        else:
            Window2.scroll_print("Resuming output", 2)
            StatusWindow.window_print(0, 0, " ", 3)
            PrintSleep = OldPrintSleep

    elif key == "i":
        Window4.clear()
        get_node_info(interface)

    elif key == "l":
        Pad1.clear()
        display_logs(0.01)

    elif key == "n":
        Pad1.clear()
        display_nodes(interface)

    elif key == "q":
        wallet.write_wallet_to_file()
        final_cleanup(stdscr)
        exit()

    elif key == "c":
        clear_all_windows()

    elif key == "r":
        Window2.scroll_print('** REBOOTING **', 1)

        final_cleanup(stdscr)
        os.execl(sys.executable, sys.executable, *sys.argv)

    elif key == "u":
        send_unsigned_message(interface)

    elif key == "s":
        send_signed_message(interface)

    elif key == "t":
        test_mesh(interface, 5, 10)

    elif key == "k":
        send_keys(interface)


def send_keys(interface):
    node_list = []
    suite = NaclSuite()

    Window2.scroll_print("SendSignedMessagePacket", 2)
    TheMessage=''


    InputMessageWindow.TextWindow.move(0,0)
    #Change color temporarily
    SendMessageWindow.TextWindow.attron(curses.color_pair(2))
    SendMessageWindow.TextWindow.border()
    SendMessageWindow.TitleColor = 2
    SendMessageWindow.Title = 'Press CTL-G to send'
    SendMessageWindow.display_title()

    SendMessageWindow.TextWindow.attroff(curses.color_pair(2))

    SendMessageWindow.TextWindow.refresh()

    #Show cursor

    curses.curs_set(True)

    InputMessageWindow.TextWindow.erase()
    InputMessageBox.edit()
    curses.curs_set(False)

    for node in interface.nodes.values():
        new_tuple = (node['user']['longName'], node['user']['macaddr'], node['num'])
        node_list.append(new_tuple)


    for node in node_list:
        local_name = node[0]
        mac_addr = node[1]
        node_num = node[2]
        public_key, private_key = suite.generate_key_pairs(local_name)
        suite.add_person_to_book(local_name,mac_addr,node_num, bytes(public_key), bytes(private_key))
        interface.sendData(public_key, wantAck=True)
        interface.sendData(private_key, wantAck=True)

    suite.write_all_secrets_to_file()

    Window4.scroll_print(" ", 2)
    Window4.scroll_print("==Keys Sent SENT===================================", 3)
    Window4.scroll_print("=======================================================", 3)
    Window4.scroll_print(" ", 2)

    SendMessageWindow.clear()
    SendMessageWindow.TitleColor = 2
    SendMessageWindow.Title = 'Press S to send a message'
    SendMessageWindow.display_title()

    Window3.scroll_print("To: All - {}".format(TheMessage), 2, TimeStamp=True)


def send_unsigned_message(interface, Message=''):
    Window2.scroll_print("SendUnsignedMessagePacket", 2)
    TheMessage = ''

    InputMessageWindow.TextWindow.move(0, 0)
    # Change color temporarily
    SendMessageWindow.TextWindow.attron(curses.color_pair(2))
    SendMessageWindow.TextWindow.border()
    SendMessageWindow.TitleColor = 2
    SendMessageWindow.Title = 'Press CTL-G to send'
    SendMessageWindow.display_title()

    SendMessageWindow.TextWindow.attroff(curses.color_pair(2))

    SendMessageWindow.TextWindow.refresh()

    # Show cursor
    curses.curs_set(True)

    # Let the user edit until Ctrl-G is struck.
    InputMessageWindow.TextWindow.erase()
    InputMessageBox.edit()
    curses.curs_set(False)

    # Get resulting contents

    TheMessage = InputMessageBox.gather().replace("\n", " ")

    # remove last character which seems to be interfering with line printing
    TheMessage = TheMessage[0:-1]

    # Send the message to the device
    interface.sendText(TheMessage, wantAck=True)

    #Window4.scroll_print(" ", 2)
    #Window4.scroll_print("==Unsigned Packet SENT=================================", 3)
    #Window4.scroll_print("To:      All:", 3)
    #Window4.scroll_print("From:    BaseStation", 3)
    #Window4.scroll_print("Message: {}".format(TheMessage), 3)
    #Window4.scroll_print("=======================================================", 3)
    #Window4.scroll_print(" ", 2)

    SendMessageWindow.clear()
    SendMessageWindow.TitleColor = 2
    SendMessageWindow.Title = 'Press S to send a message'
    SendMessageWindow.display_title()

    Window3.scroll_print(
        "UNSIGNED message to: All - {}".format(TheMessage), 2, TimeStamp=True)


def send_signed_message(interface, Message=''):
    #Window2.scroll_print("SendSignedMessagePacket", 2)
    TheMessage = ''

    InputMessageWindow.TextWindow.move(0, 0)
    # Change color temporarily
    SendMessageWindow.TextWindow.attron(curses.color_pair(2))
    SendMessageWindow.TextWindow.border()
    SendMessageWindow.TitleColor = 2
    SendMessageWindow.Title = 'Press CTL-G to send'
    SendMessageWindow.display_title()

    SendMessageWindow.TextWindow.attroff(curses.color_pair(2))

    SendMessageWindow.TextWindow.refresh()

    # Show cursor
    curses.curs_set(True)

    # Let the user edit until Ctrl-G is struck.
    InputMessageWindow.TextWindow.erase()
    InputMessageBox.edit()
    curses.curs_set(False)

    # Get resulting contents
    TheMessage = InputMessageBox.gather().replace("\n", " ")

    # remove last character which seems to be interfering with line printing
    TheMessage = TheMessage[0:-1]

    # Sign the message and send the signed message to the device
    signing_key = pickle.loads(wallet.current_persona.private_key)

    # Convert the text message to bytes and sign it with the private key
    text_message_bytes = TheMessage.encode('utf-8')

    # Sign a message with the signing key
    signed_b64 = signing_key.sign(text_message_bytes, encoder=HexEncoder)

    # Obtain the verify key for a given signing key
    verify_key = signing_key.verify_key

    # Serialize the verify key to send it to a third party
    verify_key_b64 = verify_key.encode(encoder=HexEncoder)

    signed_message_bytes = signed_b64 + verify_key_b64

    interface.sendSignedText(signed_message_bytes, wantAck=True)

    #Window4.scroll_print(" ", 2)
    #Window4.scroll_print("==Signed Packet SENT===================================", 3)
    #Window4.scroll_print("To:      All:", 3)
    #Window4.scroll_print("From:    BaseStation", 3)
    #Window4.scroll_print("Message: {}".format(TheMessage), 3)
    #Window4.scroll_print("=======================================================", 3)
    #Window4.scroll_print(" ", 2)

    SendMessageWindow.clear()
    SendMessageWindow.TitleColor = 2
    SendMessageWindow.Title = 'Press S to send a message'
    SendMessageWindow.display_title()

    Window3.scroll_print("SIGNED message to: All - {}".format(TheMessage), 2, TimeStamp=True)


def go_to_sleep(TimeToSleep):
    Window2.scroll_print("GoToSleep({})".format(TimeToSleep), 2, TimeStamp=True)
    for i in range(0, (TimeToSleep * 10)):
        # Check for keyboard input
        poll_keyboard()
        time.sleep(0.1)


def clear_all_windows():
    Window1.clear()
    Window2.clear()
    Window3.clear()
    Window4.clear()
    Window5.clear()
    Window2.scroll_print("**Clearing screens**", 2)
    update_status_window()


def update_status_window(NewDeviceStatus='',
                         NewDeviceName='',
                         NewDevicePort='',
                         NewHardwareModel='',
                         NewMacAddress='',
                         NewDeviceID='',
                         NewBatteryLevel=-1,
                         NewLastPacketType='',
                         NewLat=0,
                         NewLon=0,
                         Color=2
                         ):
    # Window2.ScrollPrint("UpdateStatusWindow",2,TimeStamp=True)

    global DeviceStatus
    global DeviceName
    global DevicePort
    global PacketsReceived
    global PacketsSent
    global LastPacketType
    global HardwareModel
    global MacAddress
    global DeviceID
    global BaseLat
    global BaseLon

    BatteryLevel = -1

    x1, y1 = 1, 1  # DeviceName
    x2, y2 = 1, 2  # HardwareModel
    x3, y3 = 1, 3  # DeviceStatus
    x4, y4 = 1, 4  # MacAddress
    x5, y5 = 1, 5  # DeviceID
    x6, y6 = 1, 6  # PacketsDecoded
    x7, y7 = 1, 7  # LastPacketType
    x8, y8 = 1, 8  # BatteryLevel
    x9, y9 = 1, 9  # BaseLat
    x10, y10 = 1, 10  # BaseLon

    if (NewDeviceName != ''):
        DeviceName = NewDeviceName

    if (NewDeviceStatus != ''):
        DeviceStatus = NewDeviceStatus

    if (NewDevicePort != ''):
        DevicePort = NewDevicePort

    if (NewLastPacketType != ''):
        LastPacketType = NewLastPacketType

    if (NewHardwareModel != ''):
        HardwareModel = NewHardwareModel

    if (NewMacAddress != ''):
        MacAddress = NewMacAddress

    if (NewDeviceID != ''):
        DeviceID = NewDeviceID

    if (NewBatteryLevel > -1):
        BatteryLevel = NewBatteryLevel

    if (NewLat != 0):
        BaseLat = NewLat

    if (NewLon != 0):
        BaseLon = NewLon

    # DeviceName
    Window1.window_print(y1, x1, "UserName:   ", 2)
    Window1.window_print(y1, x1 + 12, DeviceName, Color)

    # DeviceStatus
    Window1.window_print(y2, x2, "Model:      " + HardwareModel, 2)
    Window1.window_print(y2, x2 + 12, HardwareModel, Color)

    # DeviceStatus
    Window1.window_print(y3, x3, "Status:     " + DeviceStatus, 2)
    Window1.window_print(y3, x3 + 12, DeviceStatus, Color)

    # MacAddress
    Window1.window_print(y4, x4, "MacAddress: ", 2)
    Window1.window_print(y4, x4 + 12, MacAddress, Color)

    # DeviceID
    Window1.window_print(y5, x5, "DeviceID:   ", 2)
    Window1.window_print(y5, x5 + 12, DeviceID, Color)

    # PacketsReceived
    Window1.window_print(y6, x6, "Packets Decoded: ", 2)
    Window1.window_print(y6, x6 + 17, "{}".format(PacketsReceived), Color)

    # LastPacketType
    Window1.window_print(y7, x7, "LastPacketType:  ", 2)
    Window1.window_print(y7, x7 + 17, LastPacketType, Color)

    # BatteryLevel
    Window1.window_print(y8, x8, "BatteryLevel:    ", 2)
    Window1.window_print(y8, x8 + 17, "{}".format(BatteryLevel), Color)

    # Base LAT
    Window1.window_print(y9, x9, "Base LAT:    ", 2)
    Window1.window_print(y9, x9 + 17, "{}".format(BaseLat), Color)

    # Base LON
    Window1.window_print(y10, x10, "Base LON:    ", 2)
    Window1.window_print(y10, x10 + 17, "{}".format(BaseLon), Color)


def display_help_info():
    HelpWindow.scroll_print("C - CLEAR Screen", 7)
    HelpWindow.scroll_print("I - Request node INFO", 7)
    HelpWindow.scroll_print("L - Show LOGS", 7)
    HelpWindow.scroll_print("N - Show all NODES", 7)
    HelpWindow.scroll_print("Q - QUIT program", 7)
    HelpWindow.scroll_print("R - RESTART Black Lager", 7)
    HelpWindow.scroll_print("U - SEND unsigned message", 7)
    HelpWindow.scroll_print("S - SEND signed message", 7)
    HelpWindow.scroll_print("T - TEST mesh network", 7)
    HelpWindow.scroll_print("K - Assign KEYS", 7)
    HelpWindow.scroll_print("SPACEBAR - Slow/Fast output", 7)


def get_node_info(interface):
    # Get information about my own node

    Window4.scroll_print(" ", 2)
    Window4.scroll_print("==MyNodeInfo===================================", 3)
    TheNode = interface.getMyNodeInfo()
    decode_packet('MYNODE', TheNode, '', '', PrintSleep=PrintSleep)
    Window4.scroll_print("===============================================", 3)
    Window4.scroll_print(" ", 2)

    if 'latitude' in TheNode['position'] and 'longitude' in TheNode['position']:
        BaseLat = TheNode['position']['latitude']
        BaseLon = TheNode['position']['longitude']
        update_status_window(NewLon=BaseLon, NewLat=BaseLat, Color=2)

    if 'longName' in TheNode['user']:
        update_status_window(NewDeviceName=TheNode['user']['longName'], Color=2)

    if 'hwModel' in TheNode['user']:
        update_status_window(
            NewHardwareModel=TheNode['user']['hwModel'], Color=2)

    if 'macaddr' in TheNode['user']:
        update_status_window(NewMacAddress=TheNode['user']['macaddr'], Color=2)

    if 'id' in TheNode['user']:
        update_status_window(NewDeviceID=TheNode['user']['id'], Color=2)

    if 'batteryLevel' in TheNode['position']:
        update_status_window(
            NewBatteryLevel=TheNode['position']['batteryLevel'], Color=2)


def display_nodes(interface):
    Pad1.clear()
    Pad1.pad_print("--NODES IN MESH------------", 3)

    if (PriorityOutput == True):
        time.sleep(5)

    try:
        # interface.nodes.values() will return a dictionary
        for node in (interface.nodes.values()):
            Pad1.pad_print("NAME: {}".format(node['user']['longName']), 3)
            Pad1.pad_print("NODE: {}".format(node['num']), 3)
            Pad1.pad_print("ID:   {}".format(node['user']['id']), 3)
            Pad1.pad_print("MAC:  {}".format(node['user']['macaddr']), 3)

            if 'position' in node.keys():

                # used to calculate XY for tile servers
                if 'latitude' in node['position'] and 'longitude' in node['position']:
                    Lat = node['position']['latitude']
                    Lon = node['position']['longitude']

                    xtile, ytile = deg2num(Lat, Lon, 10)
                    Pad1.pad_print("Tile: {}/{}".format(xtile, ytile), 3)
                    Pad1.pad_print("LAT:  {}".format(
                        node['position']['latitude']), 3)
                    Pad1.pad_print("LONG: {}".format(
                        node['position']['longitude']), 3)
                    Distance = geopy.distance.geodesic(
                        (Lat, Lon), (BaseLat, BaseLon)).m
                    Pad1.pad_print("Distance: {:.3f} m".format(Distance), 3)

                if 'batteryLevel' in node['position']:
                    Battery = node['position']['batteryLevel']
                    Pad1.pad_print("Battery:   {}".format(Battery), 3)

            if 'lastHeard' in node.keys():
                LastHeardDatetime = time.strftime(
                    '%Y-%m-%d %H:%M:%S', time.localtime(node['lastHeard']))
                Pad1.pad_print("LastHeard: {}".format(LastHeardDatetime), 3)

            time.sleep(PrintSleep)
            Pad1.pad_print("", 3)

    except Exception as ErrorMessage:
        TraceMessage = traceback.format_exc()
        AdditionalInfo = "Processing node info"
        error_handler(ErrorMessage, TraceMessage, AdditionalInfo, stdscr)

    Pad1.pad_print("---------------------------", 3)


def exec_process(cmdline, silent, input=None, **kwargs):
    """Execute a subprocess and returns the returncode, stdout buffer and stderr buffer.
       Optionally prints stdout and stderr while running."""
    try:
        sub = subprocess.Popen(cmdline, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        stdout, stderr = sub.communicate(input=input)
        returncode = sub.returncode
        if not silent:
            sys.stdout.write(stdout)
            sys.stderr.write(stderr)
    except OSError as e:
        if e.errno == 2:
            raise RuntimeError(
                '"%s" is not present on this system' % cmdline[0])
        else:
            raise
    if returncode != 0:
        raise RuntimeError('Got return value %d while executing "%s", stderr output was:\n%s' % (
            returncode, " ".join(cmdline), stderr.rstrip("\n")))
    return stdout


def tail(f, n):
    assert n >= 0
    pos, lines = n+1, []
    while len(lines) <= n:
        try:
            f.seek(-pos, 2)
        except IOError:
            f.seek(0)
            break
        finally:
            lines = list(f)
        pos *= 2
    return lines[-n:]


def display_logs(ScrollSleep):
    global PriorityOutput

    # we want to stop all other output to prevent text being written to other windows
    PriorityOutput = True
    Window2.scroll_print("PriorityOutput: activated")

    try:
        with open("/var/log/kern.log") as f:

            f = tail(f, 50)

            for line in f:
                Pad1.pad_print(line, 3)
                time.sleep(ScrollSleep)
                poll_keyboard()
    except IOError:
        Pad1.pad_print("Could not open /var/log/kern.log.", 3)

    PriorityOutput = False
    Window2.scroll_print("PriorityOutput: deactivated")


def test_mesh(interface, MessageCount=10, Sleep=10):
    Window2.scroll_print("TestMesh", 2)

    for i in range(1, MessageCount+1):

        TheMessage = ''
        current_time = datetime.now().strftime("%H:%M:%S")
        TheMessage = "This is Base station.  Message: {} Date: {}".format(
            i, current_time)

        # Send the message to the device
        interface.sendText(TheMessage, wantAck=True)

        Window4.scroll_print(" ", 2)
        Window4.scroll_print("==Packet SENT==========================================", 3)
        Window4.scroll_print("To:      All:", 3)
        Window4.scroll_print("From:    BaseStation", 3)
        Window4.scroll_print("Message: {}".format(TheMessage), 3)
        Window4.scroll_print("=======================================================", 3)
        Window4.scroll_print(" ", 2)

        SendMessageWindow.clear()
        SendMessageWindow.TitleColor = 2
        SendMessageWindow.Title = 'Press S to send a message'
        SendMessageWindow.display_title()

        Window3.scroll_print("To: All - {}".format(TheMessage), 2, TimeStamp=True)

        go_to_sleep(Sleep)


def main(stdscr):
    global interface
    global DeviceStatus
    global DeviceName
    global DevicePort
    global PacketsSent
    global PacketsReceived
    global LastPacketType
    global HardwareModel
    global MacAddress
    global DeviceID
    global PauseOutput
    global HardwareModel
    global PriorityOutput
    global BaseLat
    global BaseLon

    try:
        DeviceName = '??'
        DeviceStatus = '??'
        DevicePort = '??'
        PacketsReceived = 0
        PacketsSent = 0
        LastPacketType = ''
        HardwareModel = ''
        MacAddress = ''
        DeviceName = ''
        DeviceID = ''
        PauseOutput = False
        HardwareModel = '??'
        PriorityOutput = False,
        BaseLat = 0
        BaseLon = 0

        if curses.LINES < 57 or curses.COLS < 190:
            ErrorMessage = "Display area too small. Increase window size or reduce font size."
            TraceMessage = traceback.format_stack()[0]
            AdditionalInfo = "57 lines and 190 columns required. Found {} lines and {} columns.".format(
                curses.LINES, curses.COLS)
            error_handler(ErrorMessage, TraceMessage, AdditionalInfo, stdscr)

        create_text_windows()
        Window4.scroll_print("System initiated", 2)
        Window2.scroll_print("Priorityoutput: {}".format(PriorityOutput), 1)

        # Instantiate a meshtastic object
        # By default will try to find a meshtastic device, otherwise provide a device path like /dev/ttyUSB0
        if args.host:
            Window4.scroll_print("Connecting to device on host {}".format(args.host), 2)
            interface = meshtastic.tcp_interface.TCPInterface(args.host)
        elif args.port:
            Window4.scroll_print("Connecting to device at port {}".format(args.port), 2)
            interface = meshtastic.serial_interface.SerialInterface(args.port)
        else:
            Window4.scroll_print("Finding Meshtastic device", 2)
            interface = meshtastic.serial_interface.SerialInterface()

        # subscribe to connection and receive channels
        Window4.scroll_print("Subscribe to publications", 2)
        pub.subscribe(on_connection_established, "meshtastic.connection.established")
        pub.subscribe(on_connection_lost, "meshtastic.connection.lost")

        time.sleep(2)
        # Get node info for connected device
        Window4.scroll_print("Requesting device info", 2)
        get_node_info(interface)

        # Check for message to be sent (command line option)
        if SendMessage:
            interface.sendText(TheMessage, wantAck=True)

        # Go into listening mode
        Window4.scroll_print("Listening for: {} seconds".format(TimeToSleep), 2)
        Window4.scroll_print("Subscribing to interface channels...", 2)
        pub.subscribe(on_receive, "meshtastic.receive")

        while True:
            go_to_sleep(5)

    except Exception as ErrorMessage:
        time.sleep(2)
        TraceMessage = traceback.format_exc()
        AdditionalInfo = "Main function "
        error_handler(ErrorMessage, TraceMessage, AdditionalInfo, stdscr)

    # if SIGINT or CTL-C detected, run SIGINT_handler to exit gracefully
    signal(SIGINT, sigint_handler)


if __name__ == '__main__':
    try:
        # Initialize curses
        stdscr = curses.initscr()
        # Turn off echoing of keys, and enter cbreak mode, where no buffering is performed on keyboard input
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)

        # In keypad mode, escape sequences for special keys (like the cursor keys) will be interpreted
        # and a special value like curses.KEY_LEFT will be returned
        stdscr.keypad(1)
        # Enter the main loop
        main(stdscr)

        # Set everything back to normal
        final_cleanup(stdscr)

    except Exception as ErrorMessage:
        # In event of error, restore terminal to sane state.
        TraceMessage = traceback.format_exc()
        AdditionalInfo = "Main pre-amble"
        error_handler(ErrorMessage, TraceMessage, AdditionalInfo, stdscr)
