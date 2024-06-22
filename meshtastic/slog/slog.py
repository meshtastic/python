"""code logging power consumption of meshtastic devices."""

import logging
import re
import atexit
from datetime import datetime
from dataclasses import dataclass

import parse
import pandas as pd

from meshtastic.mesh_interface import MeshInterface
from meshtastic.observable import Event
from meshtastic.powermon import PowerMeter


@dataclass(init=False)
class LogDef:
    """Log definition."""
    code: str           # i.e. PM or B or whatever... see meshtastic slog documentation
    format: str         # A format string that can be used to parse the arguments

    def __init__(self, code: str, format: str) -> None:
        """Initialize the LogDef object.

            code (str): The code.
            format (str): The format.
        """
        self.code = code
        self.format = parse.compile(format)

"""A dictionary mapping from logdef code to logdef"""
log_defs = {d.code: d for d in [
    LogDef("B", "{boardid:d},{version}"),
    LogDef("PM", "{bitmask:d},{reason}")
    ]}
log_regex = re.compile(".*S:([0-9A-Za-z]+):(.*)")


class StructuredLogger:
    """Sniffs device logs for structured log messages, extracts those into pandas/CSV format."""

    def __init__(self, client: MeshInterface, pMeter: PowerMeter = None) -> None:
        """Initialize the PowerMonClient object.

            power (PowerSupply): The power supply object.
            client (MeshInterface): The MeshInterface object to monitor.
        """
        self.client = client
        self.pMeter = pMeter
        self.columns = ["time", "power"]
        self.rawData = pd.DataFrame(columns=self.columns)  # use time as the index
        # self.rawData.set_index("time", inplace=True)

        # for efficiency reasons we keep new data in a list - only adding to rawData when needed
        self.newData: list[dict] = []

        atexit.register(self._exitHandler)
        client.onLogMessage.subscribe(self._onLogMessage)

    def getRawData(self) -> pd.DataFrame:
        """Get the raw data.

        Returns
        -------
            pd.DataFrame: The raw data.
        """

        df = pd.DataFrame(self.newData)

        # We prefer some columns to be integers
        intcols = [ "bitmask" ]
        for c in intcols:
            if c in df:
                df[c] = df[c].astype('Int64')

        # df.set_index("time")
        # Add new data, creating new columns as needed (an outer join)
        self.rawData = pd.concat([self.rawData, df], axis=0, ignore_index=True)
        self.newData = []

        return self.rawData

    def _exitHandler(self) -> None:
        """Exit handler."""
        fn = "/tmp/powermon.slog"  # Find a better place
        logging.info(f"Storing slog in {fn}")
        self.getRawData().to_csv(fn)

    def _onLogMessage(self, ev: Event) -> None:
        """Handle log messages.

            ev (Event): The log event.
        """
        m = log_regex.match(ev.message)
        if m:
            src = m.group(1)
            args = m.group(2)

            args += " "  # append a space so that if the last arg is an empty str it will still be accepted as a match
            logging.debug(f"SLog {src}, reason: {args}")
            d = log_defs.get(src)
            if d:
                r = d.format.parse(args) # get the values with the correct types
                if r:
                    di = r.named
                    di["time"] = datetime.now()
                    if self.pMeter: # if we have a power meter include a fresh power reading
                        di["power"] = self.pMeter.getWatts()
                    self.newData.append(di)
                    self.getRawData()
                else:
                    logging.warning(f"Failed to parse slog {ev.message} with {d.format}")
            else:
                logging.warning(f"Unknown Structured Log: {ev.message}")
