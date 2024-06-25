"""code logging power consumption of meshtastic devices."""

import math
import time
from typing import *

from .power_supply import PowerError, PowerSupply


class SimPowerSupply(PowerSupply):
    """A simulated power supply for testing."""

    def getAverageWatts(self) -> float:
        """Get the total amount of power that is currently being consumed."""

        # Sim a 20mW load that varies sinusoidally
        return (20 + 5 * math.sin(time.time())) / 1000
