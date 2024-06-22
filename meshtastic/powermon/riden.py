"""code logging power consumption of meshtastic devices."""

import logging
import math
from datetime import datetime

from riden import Riden

class PowerMeter:
    """Abstract class for power meters."""

    def __init__(self):
        """Initialize the PowerMeter object."""
        self.prevPowerTime = datetime.now()
        self.prevWattHour = self._getRawWattHour()

    def getWatts(self) -> float:
        """Get the total amount of power that has been consumed since the previous call of this method"""
        now = datetime.now()
        nowWattHour = self._getRawWattHour()
        watts = (
            (nowWattHour - self.prevWattHour)
            / (now - self.prevPowerTime).total_seconds()
            * 3600
        )
        self.prevPowerTime = now
        self.prevWattHour = nowWattHour
        return watts

    def _getRawWattHour(self) -> float:
        """Get the current watt-hour reading (without any offset correction)."""
        return math.nan



class PowerSupply(PowerMeter):
    """Abstract class for power supplies."""

    def setMaxCurrent(self, i: float):
        """Set the maximum current the supply will provide."""

    def powerOn(self, v: float):
        """Turn on the power supply."""



class RidenPowerSupply(PowerSupply):
    """Interface for talking to programmable bench-top power supplies.
    Currently only the Riden supplies are supported (RD6006 tested)
    """

    def __init__(self, portName: str = "/dev/ttyUSB0"):
        """Initialize the RidenPowerSupply object.

            portName (str, optional): The port name of the power supply. Defaults to "/dev/ttyUSB0".
        """
        self.r = r = Riden(port=portName, baudrate=115200, address=1)
        logging.info(
            f"Connected to Riden power supply: model {r.type}, sn {r.sn}, firmware {r.fw}. Date/time updated."
        )
        r.set_date_time(datetime.now())
        super().__init__() # we call this late so that the port is already open and _getRawWattHour callback works

    def setMaxCurrent(self, i: float):
        """Set the maximum current the supply will provide."""
        self.r.set_i_set(i)

    def powerOn(self, v: float):
        """Power on the supply, with reasonable defaults for meshtastic devices."""
        self.r.set_v_set(v)  # my WM1110 devboard header is directly connected to the 3.3V rail
        self.r.set_output(1)

    def _getRawWattHour(self) -> float:
        """Get the current watt-hour reading."""
        self.r.update()
        return self.r.wh
