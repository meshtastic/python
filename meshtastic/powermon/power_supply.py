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
        self.prevWattHour = self._getRawWattHour()

    def getWatts(self) -> float:
        """Get the total amount of power that is currently being consumed."""
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

    def __init__(self):
        """Initialize the PowerSupply object."""
        super().__init__()
        self.v = 0.0

    def powerOn(self):
        """Turn on the power supply (using the voltage set in self.v)."""
