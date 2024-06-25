"""code logging power consumption of meshtastic devices."""

import math
import time

from .power_supply import PowerSupply


class SimPowerSupply(PowerSupply):
    """A simulated power supply for testing."""

    def get_average_current_mA(self) -> float:
        """Returns average current of last measurement in mA (since last call to this method)"""

        # Sim a 20mW load that varies sinusoidally
        return (20.0 + 5 * math.sin(time.time()))
