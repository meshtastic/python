"""Power stress testing support.
"""
import logging
import time

from pubsub import pub  # type: ignore[import-untyped]

from meshtastic.protobuf import portnums_pb2
from meshtastic.protobuf.powermon_pb2 import PowerStressMessage


def onPowerStressResponse(packet, interface):
    """Delete me? FIXME"""
    logging.debug(f"packet:{packet} interface:{interface}")
    # interface.gotResponse = True


class PowerStressClient:
    """
    The client stub for talking to the firmware PowerStress module.
    """

    def __init__(self, iface, node_id = None):
        """
        Create a new PowerStressClient instance.

        iface is the already open MeshInterface instance
        """
        self.iface = iface

        if not node_id:
            node_id = iface.myInfo.my_node_num

        self.node_id = node_id            
        # No need to subscribe - because we
        # pub.subscribe(onGPIOreceive, "meshtastic.receive.powerstress")

    def sendPowerStress(
        self, cmd: PowerStressMessage.Opcode.ValueType, num_seconds: float = 0.0, onResponse=None
    ):
        r = PowerStressMessage()
        r.cmd = cmd
        r.num_seconds = num_seconds

        return self.iface.sendData(
            r,
            self.node_id,
            portnums_pb2.POWERSTRESS_APP,
            wantAck=True,
            wantResponse=True,
            onResponse=onResponse,
            onResponseAckPermitted=True
        )

class PowerStress:
    """Walk the UUT through a set of power states so we can capture repeatable power consumption measurements."""

    def __init__(self, iface):
        self.client = PowerStressClient(iface)


    def run(self):
        """Run the power stress test."""
        # Send the power stress command
        gotAck = False

        def onResponse(packet: dict):  # pylint: disable=unused-argument
            nonlocal gotAck
            gotAck = True

        logging.info("Starting power stress test, attempting to contact UUT...")   
        self.client.sendPowerStress(PowerStressMessage.PRINT_INFO, onResponse=onResponse)

        # Wait for the response
        while not gotAck:
            time.sleep(0.1)

        logging.info("Power stress test complete.")