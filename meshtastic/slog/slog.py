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
from functools import reduce
from typing import Optional, List, Tuple

import parse  # type: ignore[import-untyped]
import platformdirs
import pyarrow as pa
from pubsub import pub  # type: ignore[import-untyped]

from meshtastic.mesh_interface import MeshInterface
from meshtastic.powermon import PowerMeter

from .arrow import FeatherWriter


def root_dir() -> str:
    """Return the root directory for slog files."""

    app_name = "meshtastic"
    app_author = "meshtastic"
    app_dir = platformdirs.user_data_dir(app_name, app_author)
    dir_name = f"{app_dir}/slogs"
    os.makedirs(dir_name, exist_ok=True)
    return dir_name


@dataclass(init=False)
class LogDef:
    """Log definition."""

    code: str  # i.e. PM or B or whatever... see meshtastic slog documentation
    fields: List[Tuple[str, pa.DataType]]  # A list of field names and their arrow types
    format: parse.Parser  # A format string that can be used to parse the arguments

    def __init__(self, code: str, fields: List[Tuple[str, pa.DataType]]) -> None:
        """Initialize the LogDef object.

        code (str): The code.
        format (str): The format.

        """
        self.code = code
        self.fields = fields

        fmt = ""
        for idx, f in enumerate(fields):
            if idx != 0:
                fmt += ","

            # make the format string
            suffix = (
                "" if f[1] == pa.string() else ":d"
            )  # treat as a string or an int (the only types we have so far)
            fmt += "{" + f[0] + suffix + "}"
        self.format = parse.compile(
            fmt
        )  # We include a catchall matcher at the end - to ignore stuff we don't understand


"""A dictionary mapping from logdef code to logdef"""
log_defs = {
    d.code: d
    for d in [
        LogDef("B", [("board_id", pa.uint32()), ("sw_version", pa.string())]),
        LogDef("PM", [("pm_mask", pa.uint64()), ("pm_reason", pa.string())]),
        LogDef("PS", [("ps_state", pa.uint32())]),
    ]
}
log_regex = re.compile(".*S:([0-9A-Za-z]+):(.*)")


class PowerLogger:
    """Logs current watts reading periodically using PowerMeter and ArrowWriter."""

    def __init__(self, pMeter: PowerMeter, file_path: str, interval=0.002) -> None:
        """Initialize the PowerLogger object."""
        self.pMeter = pMeter
        self.writer = FeatherWriter(file_path)
        self.interval = interval
        self.is_logging = True
        self.thread = threading.Thread(
            target=self._logging_thread, name="PowerLogger", daemon=True
        )
        self.thread.start()

    def store_current_reading(self, now: Optional[datetime] = None) -> None:
        """Store current power measurement."""
        if now is None:
            now = datetime.now()
        d = {
            "time": now,
            "average_mW": self.pMeter.get_average_current_mA(),
            "max_mW": self.pMeter.get_max_current_mA(),
            "min_mW": self.pMeter.get_min_current_mA(),
        }
        self.pMeter.reset_measurements()
        self.writer.add_row(d)

    def _logging_thread(self) -> None:
        """Background thread for logging the current watts reading."""
        while self.is_logging:
            self.store_current_reading()
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

    def __init__(
        self,
        client: MeshInterface,
        dir_path: str,
        power_logger: Optional[PowerLogger] = None,
        include_raw=True,
    ) -> None:
        """Initialize the StructuredLogger object.

        client (MeshInterface): The MeshInterface object to monitor.
        """
        self.client = client
        self.power_logger = power_logger

        # Setup the arrow writer (and its schema)
        self.writer = FeatherWriter(f"{dir_path}/slog")
        all_fields = reduce(
            (lambda x, y: x + y), map(lambda x: x.fields, log_defs.values())
        )

        self.include_raw = include_raw
        if self.include_raw:
            all_fields.append(("raw", pa.string()))

        # Use timestamp as the first column
        all_fields.insert(0, ("time", pa.timestamp("us")))

        # pass in our name->type tuples a pa.fields
        self.writer.set_schema(
            pa.schema(map(lambda x: pa.field(x[0], x[1]), all_fields))
        )

        self.raw_file: Optional[
            io.TextIOWrapper
        ] = open(  # pylint: disable=consider-using-with
            f"{dir_path}/raw.txt", "w", encoding="utf8"
        )

        # We need a closure here because the subscription API is very strict about exact arg matching
        def listen_glue(line, interface):  # pylint: disable=unused-argument
            self._onLogMessage(line)

        self._listen_glue = (
            listen_glue  # we must save this so it doesn't get garbage collected
        )
        self._listener = pub.subscribe(listen_glue, TOPIC_MESHTASTIC_LOG_LINE)

    def close(self) -> None:
        """Stop logging."""
        pub.unsubscribe(self._listener, TOPIC_MESHTASTIC_LOG_LINE)
        self.writer.close()
        f = self.raw_file
        self.raw_file = None  # mark that we are shutting down
        if f:
            f.close()  # Close the raw.txt file

    def _onLogMessage(self, line: str) -> None:
        """Handle log messages.

        line (str): the line of log output
        """

        di = {}  # the dictionary of the fields we found to log

        m = log_regex.match(line)
        if m:
            src = m.group(1)
            args = m.group(2)
            logging.debug(f"SLog {src}, args: {args}")

            d = log_defs.get(src)
            if d:
                last_field = d.fields[-1]
                last_is_str = last_field[1] == pa.string()
                if last_is_str:
                    args += " "
                    # append a space so that if the last arg is an empty str
                    # it will still be accepted as a match for a str

                r = d.format.parse(args)  # get the values with the correct types
                if r:
                    di = r.named
                    if last_is_str:
                        di[last_field[0]] = di[
                            last_field[0]
                        ].strip()  # remove the trailing space we added
                        if di[last_field[0]] == "":
                            # If the last field is an empty string, remove it
                            del di[last_field[0]]
                else:
                    logging.warning(f"Failed to parse slog {line} with {d.format}")
            else:
                logging.warning(f"Unknown Structured Log: {line}")

        # Store our structured log record
        if di or self.include_raw:
            now = datetime.now()
            di["time"] = now
            if self.include_raw:
                di["raw"] = line
            self.writer.add_row(di)

            # If we have a sibling power logger, make sure we have a power measurement with the EXACT same timestamp
            if self.power_logger:
                self.power_logger.store_current_reading(now)

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
            app_dir = root_dir()
            dir_name = f"{app_dir}/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            os.makedirs(dir_name, exist_ok=True)

            # Also make a 'latest' directory that always points to the most recent logs
            # symlink might fail on some platforms, if it does fail silently
            if os.path.exists(f"{app_dir}/latest"):
                os.unlink(f"{app_dir}/latest")
            os.symlink(dir_name, f"{app_dir}/latest", target_is_directory=True)

        self.dir_name = dir_name

        logging.info(f"Writing slogs to {dir_name}")

        self.power_logger: Optional[PowerLogger] = (
            None
            if not power_meter
            else PowerLogger(power_meter, f"{self.dir_name}/power")
        )

        self.slog_logger: Optional[StructuredLogger] = StructuredLogger(
            client, self.dir_name, power_logger=self.power_logger
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
