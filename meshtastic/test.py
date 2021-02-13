import logging
from . import util
from . import SerialInterface, BROADCAST_NUM
from pubsub import pub
import time
import sys
import threading
from dotmap import DotMap

"""The interfaces we are using for our tests"""
interfaces = None

"""A list of all packets we received while the current test was running"""
receivedPackets = None

testsRunning = False

testNumber = 0

sendingInterface = None

def onReceive(packet, interface):
    """Callback invoked when a packet arrives"""
    if sendingInterface == interface:
        print("Ignoring sending interface")
    else:
        print(f"From {interface.stream.port}: {packet}")
        p = DotMap(packet)

        if p.decoded.data.portnum == "TEXT_MESSAGE_APP":
            # We only care a about clear text packets
            receivedPackets.append(p)

def onNode(node):
    """Callback invoked when the node DB changes"""
    print(f"Node changed: {node}")


def subscribe():
    """Subscribe to the topics the user probably wants to see, prints output to stdout"""

    pub.subscribe(onNode, "meshtastic.node")


def testSend(fromInterface, toInterface, isBroadcast=False, asBinary=False):
    """
    Sends one test packet between two nodes and then returns success or failure

    Arguments:
        fromInterface {[type]} -- [description]
        toInterface {[type]} -- [description]

    Returns:
        boolean -- True for success
    """
    global receivedPackets
    receivedPackets = []
    fromNode = fromInterface.myInfo.my_node_num

    if isBroadcast:
        toNode = BROADCAST_NUM
    else:
        toNode = toInterface.myInfo.my_node_num

    logging.info(f"Sending test packet from {fromNode} to {toNode}")
    wantAck = False # Don't want any sort of reliaible sending
    global sendingInterface
    sendingInterface = fromInterface
    if not asBinary:
        fromInterface.sendText(f"Test {testNumber}", toNode, wantAck=wantAck)
    else:
        fromInterface.sendData((f"Binary {testNumber}").encode(
            "utf-8"), toNode, wantAck=wantAck)
    for sec in range(45): # max of 45 secs before we timeout
        time.sleep(1)
        if (len(receivedPackets) >= 1):
            return True
    return False # Failed to send


def testThread(numTests=50):
    logging.info("Found devices, starting tests...")
    numFail = 0
    numSuccess = 0
    for i in range(numTests):
        global testNumber
        testNumber = testNumber + 1
        isBroadcast = True
        # asBinary=(i % 2 == 0)
        success = testSend(
            interfaces[0], interfaces[1], isBroadcast, asBinary = False)
        if not success:
            numFail = numFail + 1
            logging.error(
                f"Test failed, expected packet not received ({numFail} failures so far)")
        else:
            numSuccess = numSuccess + 1
            logging.info(f"Test succeeded ({numSuccess} successes ({numFail} failures) so far)")

        if numFail >= 3:
            for i in interfaces:
                i.close()
            return

        time.sleep(1)


def onConnection(topic=pub.AUTO_TOPIC):
    """Callback invoked when we connect/disconnect from a radio"""
    print(f"Connection changed: {topic.getName()}")

def openDebugLog(portName):
    debugname = "log" + portName.replace("/", "_")
    logging.info(f"Writing serial debugging to {debugname}")
    return open(debugname, 'w+', buffering=1)

def testAll():
    """
    Run a series of tests using devices we can find.

    Raises:
        Exception: If not enough devices are found
    """
    ports = util.findPorts()
    if (len(ports) < 2):
        raise Exception("Must have at least two devices connected to USB")

    pub.subscribe(onConnection, "meshtastic.connection")
    pub.subscribe(onReceive, "meshtastic.receive")
    global interfaces
    interfaces = list(map(lambda port: SerialInterface(
        port, debugOut=openDebugLog(port), connectNow=True), ports))

    logging.info("Ports opened, starting test")
    testThread()

    for i in interfaces:
        i.close()
    
