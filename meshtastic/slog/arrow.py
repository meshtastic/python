"""Utilities for Apache Arrow serialization."""

import logging
import threading
import os
from typing import Optional, List

import pyarrow as pa
from pyarrow import feather

chunk_size = 1000  # disk writes are batched based on this number of rows


class ArrowWriter:
    """Writes an arrow file in a streaming fashion"""

    def __init__(self, file_name: str):
        """Create a new ArrowWriter object.

        file_name (str): The name of the file to write to.
        """
        self.sink = pa.OSFile(file_name, "wb")  # type: ignore
        self.new_rows: List[dict] = []
        self.schema: Optional[pa.Schema] = None  # haven't yet learned the schema
        self.writer: Optional[pa.RecordBatchStreamWriter] = None
        self._lock = threading.Condition()  # Ensure only one thread writes at a time

    def close(self):
        """Close the stream and writes the file as needed."""
        with self._lock:
            self._write()
            if self.writer:
                self.writer.close()
            self.sink.close()

    def set_schema(self, schema: pa.Schema):
        """Set the schema for the file.
        Only needed for datasets where we can't learn it from the first record written.

        schema (pa.Schema): The schema to use.
        """
        with self._lock:
            assert self.schema is None
            self.schema = schema
            self.writer = pa.ipc.new_stream(self.sink, schema)

    def _write(self):
        """Write the new rows to the file."""
        if len(self.new_rows) > 0:
            if self.schema is None:
                # only need to look at the first row to learn the schema
                self.set_schema(pa.Table.from_pylist([self.new_rows[0]]).schema)

            self.writer.write_batch(
                pa.RecordBatch.from_pylist(self.new_rows, schema=self.schema)
            )
            self.new_rows = []

    def add_row(self, row_dict: dict):
        """Add a row to the arrow file.
        We will automatically learn the schema from the first row. But all rows must use that schema.
        """
        with self._lock:
            self.new_rows.append(row_dict)
            if len(self.new_rows) >= chunk_size:
                self._write()


class FeatherWriter(ArrowWriter):
    """A smaller more interoperable version of arrow files.
    Uses a temporary .arrow file (which could be huge) but converts to a much smaller (but still fast)
    feather file.
    """

    def __init__(self, file_name: str):
        super().__init__(file_name + ".arrow")
        self.base_file_name = file_name

    def close(self):
        super().close()
        src_name = self.base_file_name + ".arrow"
        dest_name = self.base_file_name + ".feather"
        if os.path.getsize(src_name) == 0:
            logging.warning(f"Discarding empty file: {src_name}")
            os.remove(src_name)
        else:
            logging.info(f"Compressing log data into {dest_name}")

            # note: must use open_stream, not open_file/read_table because the streaming layout is different
            # data = feather.read_table(src_name)
            with pa.memory_map(src_name) as source:
                array = pa.ipc.open_stream(source).read_all()

            # See https://stackoverflow.com/a/72406099 for more info and performance testing measurements
            feather.write_feather(array, dest_name, compression="zstd")
            os.remove(src_name)
