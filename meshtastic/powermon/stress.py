"""Power stress testing support.
"""
import logging
import time

from ..protobuf import portnums_pb2, powermon_pb2


def onPowerStressResponse(packet, interface):
    """Delete me? FIXME"""
    logging.debug(f"packet:{packet} interface:{interface}")
    # interface.gotResponse = True


class PowerStressClient:
    """
    The client stub for talking to the firmware PowerStress module.
    """

    def __init__(self, iface, node_id=None):
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
        self,
        cmd: powermon_pb2.PowerStressMessage.Opcode.ValueType,
        num_seconds: float = 0.0,
        onResponse=None,
    ):
        """Client goo for talking with the device side agent."""
        r = powermon_pb2.PowerStressMessage()
        r.cmd = cmd
        r.num_seconds = num_seconds

        return self.iface.sendData(
            r,
            self.node_id,
            portnums_pb2.POWERSTRESS_APP,
            wantAck=True,
            wantResponse=True,
            onResponse=onResponse,
            onResponseAckPermitted=True,
        )

    def syncPowerStress(
        self,
        cmd: powermon_pb2.PowerStressMessage.Opcode.ValueType,
        num_seconds: float = 0.0,
    ):
        """Send a power stress command and wait for the ack."""
        gotAck = False

        def onResponse(packet: dict):  # pylint: disable=unused-argument
            nonlocal gotAck
            gotAck = True

        logging.info(
            f"Sending power stress command {powermon_pb2.PowerStressMessage.Opcode.Name(cmd)}"
        )
        self.sendPowerStress(cmd, onResponse=onResponse, num_seconds=num_seconds)

        if num_seconds == 0.0:
            # Wait for the response and then continue
            while not gotAck:
                time.sleep(0.1)
        else:
            # we wait a little bit longer than the time the UUT would be waiting (to make sure all of its messages are handled first)
            time.sleep(
                num_seconds + 0.2
            )  # completely block our thread for the duration of the test
            if not gotAck:
                logging.error("Did not receive ack for power stress command!")


class PowerStress:
    """Walk the UUT through a set of power states so we can capture repeatable power consumption measurements."""

    def __init__(self, iface):
        self.client = PowerStressClient(iface)

    def run(self):
        """Run the power stress test."""
        try:
            self.client.syncPowerStress(powermon_pb2.PowerStressMessage.PRINT_INFO)

            num_seconds = 5.0
            states = [
                powermon_pb2.PowerStressMessage.LED_ON,
                powermon_pb2.PowerStressMessage.LED_OFF,
                powermon_pb2.PowerStressMessage.BT_OFF,
                powermon_pb2.PowerStressMessage.BT_ON,
                powermon_pb2.PowerStressMessage.CPU_FULLON,
                powermon_pb2.PowerStressMessage.CPU_IDLE,
                # FIXME - can't test deepsleep yet because the ttyACM device disappears.  Fix the python code to retry connections
                # powermon_pb2.PowerStressMessage.CPU_DEEPSLEEP,
            ]
            for s in states:
                s_name = powermon_pb2.PowerStressMessage.Opcode.Name(s)
                logging.info(
                    f"Running power stress test {s_name} for {num_seconds} seconds"
                )
                self.client.syncPowerStress(s, num_seconds)

            logging.info("Power stress test complete.")
        except KeyboardInterrupt as e:
            logging.warning(f"Power stress interrupted: {e}")
