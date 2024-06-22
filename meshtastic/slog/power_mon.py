"""code logging power consumption of meshtastic devices."""

import logging
import re
import atexit
from datetime import datetime

import pandas as pd

from meshtastic.mesh_interface import MeshInterface
from meshtastic.observable import Event
from meshtastic.powermon import PowerSupply

logRegex = re.compile(".*S:PM:0x([0-9A-Fa-f]+),(.*)")


class PowerMonClient:
    """Client for monitoring power consumption of meshtastic devices."""

    def __init__(self, power: PowerSupply, client: MeshInterface) -> None:
        """Initialize the PowerMonClient object.

        Args:
            power (PowerSupply): The power supply object.
            client (MeshInterface): The MeshInterface object to monitor.
        """
        self.client = client
        self.state = 0  # The current power mon state bitfields
        self.columns = ["time", "power", "reason", "bitmask"]
        self.rawData = pd.DataFrame(columns=self.columns)  # use time as the index

        # for efficiency reasons we keep new data in a list - only adding to rawData when needed
        self.newData: list[dict] = []

        self.power = power
        power.setMaxCurrent(0.300) # Set current limit to 300mA - hopefully enough to power any board but not break things if there is a short circuit
        power.powerOn(3.3)

        # Used to calculate watts over an interval
        self.prevPowerTime = datetime.now()
        self.prevWattHour = power.getWattHour()
        atexit.register(self._exitHandler)
        client.onLogMessage.subscribe(self._onLogMessage)

    def getRawData(self) -> pd.DataFrame:
        """Get the raw data.

        Returns:
            pd.DataFrame: The raw data.
        """
        df = pd.DataFrame(self.newData, columns=self.columns)
        self.rawData = pd.concat([self.rawData, df], ignore_index=True)
        self.newData = []

        return self.rawData

    def _exitHandler(self) -> None:
        """Exit handler."""
        fn = "/tmp/powermon.csv"  # Find a better place
        logging.info(f"Storing PowerMon raw data in {fn}")
        self.getRawData().to_csv(fn)

    def _onLogMessage(self, ev: Event) -> None:
        """Callback function for handling log messages.

        Args:
            ev (Event): The log event.
        """
        m = logRegex.match(ev.message)
        if m:
            mask = int(m.group(1), 16)
            reason = m.group(2)
            logging.debug(f"PowerMon state: 0x{mask:x}, reason: {reason}")
            if mask != self.state:
                self._storeRecord(mask, reason)

    def _storeRecord(self, mask: int, reason: str) -> None:
        """Store a power mon record.

        Args:
            mask (int): The power mon state bitfields.
            reason (str): The reason for the power mon state change.
        """
        now = datetime.now()
        nowWattHour = self.power.getWattHour()
        watts = (
            (nowWattHour - self.prevWattHour)
            / (now - self.prevPowerTime).total_seconds()
            * 3600
        )
        self.prevPowerTime = now
        self.prevWattHour = nowWattHour
        self.state = mask

        self.newData.append(
            {"time": now, "power": watts, "reason": reason, "bitmask": mask}
        )
