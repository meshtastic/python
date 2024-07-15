"""code logging power consumption of meshtastic devices."""

import atexit
import io
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import parse  # type: ignore[import-untyped]
import platformdirs
from pubsub import pub  # type: ignore[import-untyped]

from meshtastic.mesh_interface import MeshInterface
from meshtastic.powermon import PowerMeter

from .arrow import FeatherWriter


@dataclass(init=False)
class LogDef:
    """Log definition."""

    code: str  # i.e. PM or B or whatever... see meshtastic slog documentation
    format: parse.Parser  # A format string that can be used to parse the arguments

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
        self.writer = FeatherWriter(file_path)
        self.interval = interval
        self.is_logging = True
        self.thread = threading.Thread(
            target=self._logging_thread, name="PowerLogger", daemon=True
        )
        self.thread.start()

    def _logging_thread(self) -> None:
        """Background thread for logging the current watts reading."""
        while self.is_logging:
            d = {
                "time": datetime.now(),
                "average_mW": self.pMeter.get_average_current_mA(),
                "max_mW": self.pMeter.get_max_current_mA(),
                "min_mW": self.pMeter.get_min_current_mA(),
            }
            self.pMeter.reset_measurements()
            self.writer.add_row(d)
            time.sleep(self.interval)

    def close(self) -> None:
        """Close the PowerLogger and stop logging."""
        if self.is_logging:
            self.pMeter.close()
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
        self.writer = FeatherWriter(f"{dir_path}/slog")
        self.raw_file: Optional[
            io.TextIOWrapper
        ] = open(  # pylint: disable=consider-using-with
            f"{dir_path}/raw.txt", "w", encoding="utf8"
        )

        # We need a closure here because the subscription API is very strict about exact arg matching
        def listen_glue(line, interface):  # pylint: disable=unused-argument
            self._onLogMessage(line)

        self.listener = pub.subscribe(listen_glue, TOPIC_MESHTASTIC_LOG_LINE)

    def close(self) -> None:
        """Stop logging."""
        pub.unsubscribe(self.listener, TOPIC_MESHTASTIC_LOG_LINE)
        self.writer.close()
        f = self.raw_file
        self.raw_file = None  # mark that we are shutting down
        if f:
            f.close()  # Close the raw.txt file

    def _onLogMessage(self, line: str) -> None:
        """Handle log messages.

        line (str): the line of log output
        """
        m = log_regex.match(line)
        if m:
            src = m.group(1)
            args = m.group(2)
            args += " "  # append a space so that if the last arg is an empty str it will still be accepted as a match
            logging.debug(f"SLog {src}, reason: {args}")
            if src != "PM":
                logging.warning(f"Not yet handling structured log {src} (FIXME)")
            else:
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
        if self.raw_file:
            self.raw_file.write(line + "\n")  # Write the raw log


class LogSet:
    """A complete set of meshtastic log/metadata for a particular run."""

    def __init__(
        self,
        client: MeshInterface,
        dir_name: Optional[str] = None,
        power_meter: Optional[PowerMeter] = None,
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

            # Also make a 'latest' directory that always points to the most recent logs
            # symlink might fail on some platforms, if it does fail silently
            if os.path.exists(f"{app_dir}/slogs/latest"):
                os.unlink(f"{app_dir}/slogs/latest")
            os.symlink(dir_name, f"{app_dir}/slogs/latest", target_is_directory=True)

        self.dir_name = dir_name

        logging.info(f"Writing slogs to {dir_name}")

        self.slog_logger: Optional[StructuredLogger] = StructuredLogger(
            client, self.dir_name
        )
        self.power_logger: Optional[PowerLogger] = (
            None
            if not power_meter
            else PowerLogger(power_meter, f"{self.dir_name}/power")
        )

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
