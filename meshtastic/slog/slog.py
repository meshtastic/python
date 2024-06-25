"""code logging power consumption of meshtastic devices."""

import atexit
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import parse
import platformdirs
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
        self.thread = threading.Thread(
            target=self._logging_thread, name="PowerLogger", daemon=True
        )
        self.thread.start()

    def _logging_thread(self) -> None:
        """Background thread for logging the current watts reading."""
        while self.is_logging:
            watts = self.pMeter.getAverageWatts()
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
    """Sniffs device logs for structured log messages, extracts those into apache arrow format.
    Also writes the raw log messages to raw.txt"""

    def __init__(self, client: MeshInterface, dir_path: str) -> None:
        """Initialize the StructuredLogger object.

        client (MeshInterface): The MeshInterface object to monitor.
        """
        self.client = client
        self.writer = ArrowWriter(f"{dir_path}/slog.arrow")
        self.raw_file = open(  # pylint: disable=consider-using-with
            f"{dir_path}/raw.txt", "w", encoding="utf8"
        )
        self.listener = pub.subscribe(self._onLogMessage, TOPIC_MESHTASTIC_LOG_LINE)

    def close(self) -> None:
        """Stop logging."""
        pub.unsubscribe(self.listener, TOPIC_MESHTASTIC_LOG_LINE)
        self.writer.close()
        self.raw_file.close()  # Close the raw.txt file

    def _onLogMessage(
        self, line: str, interface: MeshInterface  # pylint: disable=unused-argument
    ) -> None:
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
        self.raw_file.write(line + "\n")  # Write the raw log


class LogSet:
    """A complete set of meshtastic log/metadata for a particular run."""

    def __init__(
        self,
        client: MeshInterface,
        dir_name: Optional[str] = None,
        power_meter: PowerMeter = None,
    ) -> None:
        """Initialize the PowerMonClient object.

        power (PowerSupply): The power supply object.
        client (MeshInterface): The MeshInterface object to monitor.
        """

        if not dir_name:
            app_name = "meshtastic"
            app_author = "meshtastic"
            app_dir = platformdirs.user_data_dir(app_name, app_author)
            dir_name = f"{app_dir}/slogs/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            os.makedirs(dir_name, exist_ok=True)
        self.dir_name = dir_name

        logging.info(f"Writing slogs to {dir_name}")

        self.slog_logger = StructuredLogger(client, self.dir_name)
        if power_meter:
            self.power_logger = PowerLogger(power_meter, f"{self.dir_name}/power.arrow")
        else:
            self.power_logger = None

        # Store a lambda so we can find it again to unregister
        self.atexit_handler = lambda: self.close()  # pylint: disable=unnecessary-lambda

    def close(self) -> None:
        """Close the log set."""

        if self.slog_logger:
            logging.info(f"Closing slogs in {self.dir_name}")
            atexit.unregister(
                self.atexit_handler
            )  # docs say it will silently ignore if not found
            self.slog_logger.close()
            if self.power_logger:
                self.power_logger.close()
            self.slog_logger = None
