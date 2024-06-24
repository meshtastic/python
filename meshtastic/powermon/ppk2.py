"""code logging power consumption of meshtastic devices."""

import logging
from typing import *

from ppk2_api import ppk2_api
from .power_supply import PowerSupply, PowerError



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
                raise PowerError("Multiple PPK2 devices found, please specify the portName")
            else:
                portName = devs[0]

        self.r = r = ppk2_api.PPK2_MP(portName)  # serial port will be different for you
        r.get_modifiers()

        logging.info("Connected to PPK2 power supply")

        super().__init__() # we call this late so that the port is already open and _getRawWattHour callback works

    def powerOn(self):
        """Power on the supply, with reasonable defaults for meshtastic devices."""
        self.r.use_source_meter()  # set source meter mode
        self.r.set_source_voltage(self.v * 1000)  # set source voltage in mV
        self.r.toggle_DUT_power("ON")
        self.r.start_measuring()  # start measuring


    def _getRawWattHour(self) -> float:
        """Get the current watt-hour reading."""
        return 4 # FIXME
