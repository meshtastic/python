"""code logging power consumption of meshtastic devices."""

import logging
import re
import atexit
from datetime import datetime

import pandas as pd
from riden import Riden

from meshtastic.mesh_interface import MeshInterface
from meshtastic.observable import Event


class PowerSupply:
    """Interface for talking to programmable bench-top power supplies.
    Currently only the Riden supplies are supported (RD6006 tested)
    """

    def __init__(self, portName: str = "/dev/ttyUSB0"):
        """Initialize the PowerSupply object."""
        self.r = r = Riden(port=portName, baudrate=115200, address=1)
        logging.info(
            f"Connected to Riden power supply: model {r.type}, sn {r.sn}, firmware {r.fw}. Date/time updated."
        )
        r.set_date_time(datetime.now())

    def powerOn(self):
        """Power on the supply, with reasonable defaults for meshtastic devices."""
        self.r.set_i_set(
            0.300
        )  # Set current limit to 300mA - hopefully enough to power any board but not break things if there is a short circuit

        # self.r.set_v_set(3.7)  # default to a nominal LiPo voltage
        self.r.set_v_set(3.3)  # my WM1110 devboard header is directly connected to the 3.3V rail
        self.r.set_output(1)

        """Get current watts out.
        But for most applications you probably want getWattHour() instead (to prevent integration errors from accumulating).
        """
        return self.r.get_p_out()

    def getWattHour(self):
        """Get current Wh out, since power was turned on."""
        # FIXME: Individual reads seem busted in the riden lib.  So for now I just read everything.
        self.r.update()
        return self.r.wh
        # return self.r.get_wh()

    def clearWattHour(self):
        """Clear the watt-hour counter FIXME."""


"""Used to match power mon log lines:
INFO  | ??:??:?? 7 [Blink] S:PM:0x00000080,reason
"""
logRegex = re.compile(".*S:PM:0x([0-9A-Fa-f]+),(.*)")


class PowerMonClient:
    """Client for monitoring power consumption of meshtastic devices."""

    def __init__(self, portName: str, client: MeshInterface) -> None:
        """Initialize the PowerMonClient object.

        Args:
            client (MeshInterface): The MeshInterface object to monitor.

        """
        self.client = client
        self.state = 0  # The current power mon state bitfields
        self.columns = ["time", "power", "reason", "bitmask"]
        self.rawData = pd.DataFrame(columns=self.columns) # use time as the index

        # for efficiency reasons we keep new data in a list - only adding to rawData when needfed
        self.newData: list[dict] = []

        self.power = power = PowerSupply(portName)
        power.powerOn()

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
            message (str): The log message.

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
            {"time": now, "power": watts, "reason": reason, "bitmask": mask})
        # self.getRawData()
