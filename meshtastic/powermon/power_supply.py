"""code logging power consumption of meshtastic devices."""

import math
from datetime import datetime


class PowerError(Exception):
    """An exception class for powermon errors"""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class PowerMeter:
    """Abstract class for power meters."""

    def __init__(self):
        """Initialize the PowerMeter object."""
        self.prevPowerTime = datetime.now()

    def close(self) -> None:
        """Close the power meter."""

    def get_average_current_mA(self) -> float:
        """Returns average current of last measurement in mA (since last call to this method)"""
        return math.nan

    def get_min_current_mA(self):
        """Returns max current in mA (since last call to this method)."""
        # Subclasses must override for a better implementation
        return self.get_average_current_mA()

    def get_max_current_mA(self):
        """Returns max current in mA (since last call to this method)."""
        # Subclasses must override for a better implementation
        return self.get_average_current_mA()

    def reset_measurements(self):
        """Reset current measurements."""


class PowerSupply(PowerMeter):
    """Abstract class for power supplies."""

    def __init__(self):
        """Initialize the PowerSupply object."""
        super().__init__()
        self.v = 0.0

    def powerOn(self):
        """Turn on the power supply (using the voltage set in self.v)."""
