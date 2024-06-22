"""code logging power consumption of meshtastic devices."""

import logging

from datetime import datetime

from riden import Riden

class PowerMeter:
    """Abstract class for power meters."""

    def getWattHour(self) -> float:
        """Get the current watt-hour reading."""



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

        Args:
            portName (str, optional): The port name of the power supply. Defaults to "/dev/ttyUSB0".
        """
        self.r = r = Riden(port=portName, baudrate=115200, address=1)
        logging.info(
            f"Connected to Riden power supply: model {r.type}, sn {r.sn}, firmware {r.fw}. Date/time updated."
        )
        r.set_date_time(datetime.now())

    def setMaxCurrent(self, i: float):
        """Set the maximum current the supply will provide."""
        self.r.set_i_set(i)

    def powerOn(self, v: float):
        """Power on the supply, with reasonable defaults for meshtastic devices."""
        self.r.set_v_set(v)  # my WM1110 devboard header is directly connected to the 3.3V rail
        self.r.set_output(1)

    def getWattHour(self) -> float:
        """Get the current watt-hour reading."""
        self.r.update()
        return self.r.wh

