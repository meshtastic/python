import logging
from . import util
from . import SerialInterface, TCPInterface, BROADCAST_NUM
from pubsub import pub
import time
import sys
import threading, traceback
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
        pass
        # print("Ignoring sending interface")
    else:
        # print(f"From {interface.stream.port}: {packet}")
        p = DotMap(packet)

        if p.decoded.portnum == "TEXT_MESSAGE_APP":
            # We only care a about clear text packets
            if receivedPackets != None:
                receivedPackets.append(p)


def onNode(node):
    """Callback invoked when the node DB changes"""
    print(f"Node changed: {node}")


def subscribe():
    """Subscribe to the topics the user probably wants to see, prints output to stdout"""

    pub.subscribe(onNode, "meshtastic.node")


def testSend(fromInterface, toInterface, isBroadcast=False, asBinary=False, wantAck=False):
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

    logging.debug(
        f"Sending test wantAck={wantAck} packet from {fromNode} to {toNode}")
    global sendingInterface
    sendingInterface = fromInterface
    if not asBinary:
        fromInterface.sendText(f"Test {testNumber}", toNode, wantAck=wantAck)
    else:
        fromInterface.sendData((f"Binary {testNumber}").encode(
            "utf-8"), toNode, wantAck=wantAck)
    for sec in range(60):  # max of 60 secs before we timeout
        time.sleep(1)
        if (len(receivedPackets) >= 1):
            return True
    return False  # Failed to send


def runTests(numTests=50, wantAck=False, maxFailures=0):
    logging.info(f"Running {numTests} tests with wantAck={wantAck}")
    numFail = 0
    numSuccess = 0
    for i in range(numTests):
        global testNumber
        testNumber = testNumber + 1
        isBroadcast = True
        # asBinary=(i % 2 == 0)
        success = testSend(
            interfaces[0], interfaces[1], isBroadcast, asBinary=False, wantAck=wantAck)
        if not success:
            numFail = numFail + 1
            logging.error(
                f"Test {testNumber} failed, expected packet not received ({numFail} failures so far)")
        else:
            numSuccess = numSuccess + 1
            logging.info(
                f"Test {testNumber} succeeded {numSuccess} successes {numFail} failures so far")

        # if numFail >= 3:
        #    for i in interfaces:
        #        i.close()
        #    return

        time.sleep(1)

    if numFail > maxFailures:
        logging.error("Too many failures! Test failed!")

    return numFail


def testThread(numTests=50):
    logging.info("Found devices, starting tests...")
    runTests(numTests, wantAck=True)
    # Allow a few dropped packets
    runTests(numTests, wantAck=False, maxFailures=5)


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


def testSimulator():
    """
    Assume that someone has launched meshtastic-native as a simulated node.
    Talk to that node over TCP, do some operations and if they are successful
    exit the process with a success code, else exit with a non zero exit code.

    Run with
    python3 -c 'from meshtastic.test import testSimulator; testSimulator()'
    """
    logging.basicConfig(level=logging.DEBUG if False else logging.INFO)
    logging.info("Connecting to simulator on localhost!")
    try:
        iface = TCPInterface("localhost")
        iface.showInfo()
        iface.localNode.showInfo()
        iface.localNode.exitSimulator()
        iface.close()
        logging.info("Integration test successful!")
    except:
        print("Error while testing simulator:", sys.exc_info()[0])
        traceback.print_exc()
        sys.exit(1)
    sys.exit(0)
