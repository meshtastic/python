"""code logging power consumption of meshtastic devices."""

import atexit
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime

import parse
from pubsub import pub  # type: ignore[import-untyped]

from meshtastic.mesh_interface import MeshInterface
from meshtastic.powermon import PowerMeter

from .arrow import ArrowWriter


@dataclass(init=False)
class LogDef:
    """Log definition."""

    code: str  # i.e. PM or B or whatever... see meshtastic slog documentation
    format: str  # A format string that can be used to parse the arguments

    def __init__(self, code: str, fmt: str) -> None:
        """Initialize the LogDef object.

        code (str): The code.
        format (str): The format.
        """
        self.code = code
        self.format = parse.compile(fmt)


"""A dictionary mapping from logdef code to logdef"""
log_defs = {
    d.code: d
    for d in [
        LogDef("B", "{boardid:d},{version}"),
        LogDef("PM", "{bitmask:d},{reason}"),
    ]
}
log_regex = re.compile(".*S:([0-9A-Za-z]+):(.*)")


class PowerLogger:
    """Logs current watts reading periodically using PowerMeter and ArrowWriter."""

    def __init__(self, pMeter: PowerMeter, file_path: str, interval=0.2) -> None:
        """Initialize the PowerLogger object."""
        self.pMeter = pMeter
        self.writer = ArrowWriter(file_path)
        self.interval = interval
        self.is_logging = True
        self.thread = threading.Thread(target=self._logging_thread, name="PowerLogger")
        self.thread.start()

    def _logging_thread(self) -> None:
        """Background thread for logging the current watts reading."""
        while self.is_logging:
            watts = self.pMeter.getWatts()
            d = {"time": datetime.now(), "watts": watts}
            self.writer.add_row(d)
            time.sleep(self.interval)

    def close(self) -> None:
        """Close the PowerLogger and stop logging."""
        if self.is_logging:
            self.is_logging = False
            self.thread.join()
            self.writer.close()

# FIXME move these defs somewhere else
TOPIC_MESHTASTIC_LOG_LINE = "meshtastic.log.line"

class StructuredLogger:
    """Sniffs device logs for structured log messages, extracts those into pandas/CSV format."""

    def __init__(self, client: MeshInterface, file_path: str) -> None:
        """Initialize the PowerMonClient object.

        power (PowerSupply): The power supply object.
        client (MeshInterface): The MeshInterface object to monitor.
        """
        self.client = client
        self.writer = ArrowWriter(file_path)
        self.listener = pub.subscribe(self._onLogMessage, TOPIC_MESHTASTIC_LOG_LINE)

    def close(self) -> None:
        """Stop logging."""
        pub.unsubscribe(self.listener, TOPIC_MESHTASTIC_LOG_LINE)
        self.writer.close()

    def _onLogMessage(
        self, line: str, interface: MeshInterface
    ) -> None:  # pylint: disable=unused-argument
        """Handle log messages.

        line (str): the line of log output
        """
        m = log_regex.match(line)
        if m:
            src = m.group(1)
            args = m.group(2)

            args += " "  # append a space so that if the last arg is an empty str it will still be accepted as a match
            logging.debug(f"SLog {src}, reason: {args}")
            d = log_defs.get(src)
            if d:
                r = d.format.parse(args)  # get the values with the correct types
                if r:
                    di = r.named
                    di["time"] = datetime.now()
                    self.writer.add_row(di)
                else:
                    logging.warning(f"Failed to parse slog {line} with {d.format}")
            else:
                logging.warning(f"Unknown Structured Log: {line}")


class LogSet:
    """A complete set of meshtastic log/metadata for a particular run."""

    def __init__(self, client: MeshInterface, power_meter: PowerMeter = None) -> None:
        """Initialize the PowerMonClient object.

        power (PowerSupply): The power supply object.
        client (MeshInterface): The MeshInterface object to monitor.
        """
        self.dir_name = "/tmp"  # FIXME

        self.slog_logger = StructuredLogger(client, f"{self.dir_name}/slog.arrow")
        if power_meter:
            self.power_logger = PowerLogger(power_meter, f"{self.dir_name}/power.arrow")
        else:
            self.power_logger = None

        atexit.register(self._exitHandler)

    def close(self) -> None:
        """Close the log set."""

        logging.info(f"Storing slog in {self.dir_name}")
        self.slog_logger.close()
        if self.power_logger:
            self.power_logger.close()

    def _exitHandler(self) -> None:
        """Exit handler."""
        self.close()
