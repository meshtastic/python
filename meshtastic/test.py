"""With two radios connected serially, send and receive test
   messages and report back if successful.
"""
import logging
import sys
import time
import traceback

from dotmap import DotMap # type: ignore[import-untyped]
from pubsub import pub # type: ignore[import-untyped]

import meshtastic.util
from meshtastic import BROADCAST_NUM
from meshtastic.serial_interface import SerialInterface
from meshtastic.tcp_interface import TCPInterface

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
            if receivedPackets is not None:
                receivedPackets.append(p)


def onNode(node):
    """Callback invoked when the node DB changes"""
    print(f"Node changed: {node}")


def subscribe():
    """Subscribe to the topics the user probably wants to see, prints output to stdout"""

    pub.subscribe(onNode, "meshtastic.node")


def testSend(
    fromInterface, toInterface, isBroadcast=False, asBinary=False, wantAck=False
):
    """
    Sends one test packet between two nodes and then returns success or failure

    Arguments:
        fromInterface {[type]} -- [description]
        toInterface {[type]} -- [description]

    Returns:
        boolean -- True for success
    """
    # pylint: disable=W0603
    global receivedPackets
    receivedPackets = []
    fromNode = fromInterface.myInfo.my_node_num

    if isBroadcast:
        toNode = BROADCAST_NUM
    else:
        toNode = toInterface.myInfo.my_node_num

    logging.debug(f"Sending test wantAck={wantAck} packet from {fromNode} to {toNode}")
    # pylint: disable=W0603
    global sendingInterface
    sendingInterface = fromInterface
    if not asBinary:
        fromInterface.sendText(f"Test {testNumber}", toNode, wantAck=wantAck)
    else:
        fromInterface.sendData(
            (f"Binary {testNumber}").encode("utf-8"), toNode, wantAck=wantAck
        )
    for _ in range(60):  # max of 60 secs before we timeout
        time.sleep(1)
        if len(receivedPackets) >= 1:
            return True
    return False  # Failed to send


def runTests(numTests=50, wantAck=False, maxFailures=0):
    """Run the tests."""
    logging.info(f"Running {numTests} tests with wantAck={wantAck}")
    numFail = 0
    numSuccess = 0
    for _ in range(numTests):
        # pylint: disable=W0603
        global testNumber
        testNumber = testNumber + 1
        isBroadcast = True
        # asBinary=(i % 2 == 0)
        success = testSend(
            interfaces[0], interfaces[1], isBroadcast, asBinary=False, wantAck=wantAck
        )
        if not success:
            numFail = numFail + 1
            logging.error(
                f"Test {testNumber} failed, expected packet not received ({numFail} failures so far)"
            )
        else:
            numSuccess = numSuccess + 1
            logging.info(
                f"Test {testNumber} succeeded {numSuccess} successes {numFail} failures so far"
            )

        time.sleep(1)

    if numFail > maxFailures:
        logging.error("Too many failures! Test failed!")
        return False
    return True


def testThread(numTests=50):
    """Test thread"""
    logging.info("Found devices, starting tests...")
    result = runTests(numTests, wantAck=True)
    if result:
        # Run another test
        # Allow a few dropped packets
        result = runTests(numTests, wantAck=False, maxFailures=1)
    return result


def onConnection(topic=pub.AUTO_TOPIC):
    """Callback invoked when we connect/disconnect from a radio"""
    print(f"Connection changed: {topic.getName()}")


def openDebugLog(portName):
    """Open the debug log file"""
    debugname = "log" + portName.replace("/", "_")
    logging.info(f"Writing serial debugging to {debugname}")
    return open(debugname, "w+", buffering=1, encoding="utf8")


def testAll(numTests=5):
    """
    Run a series of tests using devices we can find.
    This is called from the cli with the "--test" option.

    """
    ports = meshtastic.util.findPorts(True)
    if len(ports) < 2:
        meshtastic.util.our_exit(
            "Warning: Must have at least two devices connected to USB."
        )

    pub.subscribe(onConnection, "meshtastic.connection")
    pub.subscribe(onReceive, "meshtastic.receive")
    # pylint: disable=W0603
    global interfaces
    interfaces = list(
        map(
            lambda port: SerialInterface(
                port, debugOut=openDebugLog(port), connectNow=True
            ),
            ports,
        )
    )

    logging.info("Ports opened, starting test")
    result = testThread(numTests)

    for i in interfaces:
        i.close()

    return result


def testSimulator():
    """
    Assume that someone has launched meshtastic-native as a simulated node.
    Talk to that node over TCP, do some operations and if they are successful
    exit the process with a success code, else exit with a non zero exit code.

    Run with
    python3 -c 'from meshtastic.test import testSimulator; testSimulator()'
    """
    logging.basicConfig(level=logging.DEBUG)
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
