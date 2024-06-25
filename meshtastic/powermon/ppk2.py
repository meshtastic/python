"""Classes for logging power consumption of meshtastic devices."""

import logging
from typing import Optional

from ppk2_api import ppk2_api  # type: ignore[import-untyped]

from .power_supply import PowerError, PowerSupply


class PPK2PowerSupply(PowerSupply):
    """Interface for talking with the NRF PPK2 high-resolution micro-power supply.
    Power Profiler Kit II is what you should google to find it for purchase.
    """

    def __init__(self, portName: Optional[str] = None):
        """Initialize the PowerSupply object.

        portName (str, optional): The port name of the power supply. Defaults to "/dev/ttyACM0".
        """
        if not portName:
            devs = ppk2_api.PPK2_API.list_devices()
            if not devs or len(devs) == 0:
                raise PowerError("No PPK2 devices found")
            elif len(devs) > 1:
                raise PowerError(
                    "Multiple PPK2 devices found, please specify the portName"
                )
            else:
                portName = devs[0]

        self.r = r = ppk2_api.PPK2_MP(portName)  # serial port will be different for you
        r.get_modifiers()
        self.r.start_measuring()  # start measuring

        logging.info("Connected to PPK2 power supply")

        super().__init__()  # we call this late so that the port is already open and _getRawWattHour callback works

    def close(self) -> None:
        """Close the power meter."""
        self.r.stop_measuring()
        super().close()

    def setIsSupply(self, s: bool):
        """If in supply mode we will provide power ourself, otherwise we are just an amp meter."""
        if (
            not s
        ):  # min power outpuf of PPK2.  If less than this assume we want just meter mode.
            self.r.use_ampere_meter()
        else:
            self.r.set_source_voltage(
                int(self.v * 1000)
            )  # set source voltage in mV BEFORE setting source mode
            self.r.use_source_meter()  # set source meter mode

    def powerOn(self):
        """Power on the supply."""
        self.r.toggle_DUT_power("ON")

    def powerOff(self):
        """Power off the supply."""
        self.r.toggle_DUT_power("OFF")
