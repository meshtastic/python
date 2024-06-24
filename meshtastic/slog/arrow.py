import pyarrow as pa

chunk_size = 10  # disk writes are batched based on this number of rows


class ArrowWriter:
    """Writes an arrow file in a streaming fashion"""

    def __init__(self, file_name: str):
        """Create a new ArrowWriter object.

        file_name (str): The name of the file to write to.
        """
        self.sink = pa.OSFile(file_name, "wb")
        self.new_rows: list[dict] = []
        self.schema: pa.Schema | None = None  # haven't yet learned the schema
        self.writer: pa.RecordBatchFileWriter | None = None

    def close(self):
        """Close the stream and writes the file as needed."""
        self._write()
        if self.writer:
            self.writer.close()
        self.sink.close()

    def _write(self):
        """Write the new rows to the file."""
        if len(self.new_rows) > 0:
            if self.schema is None:
                self.schema = pa.Table.from_pylist(self.new_rows).schema
                self.writer = pa.ipc.new_stream(self.sink, self.schema)

            self.writer.write_batch(pa.RecordBatch.from_pylist(self.new_rows))
            self.new_rows = []

    def add_row(self, row_dict: dict):
        """Add a row to the arrow file.
        We will automatically learn the schema from the first row. But all rows must use that schema.
        """
        self.new_rows.append(row_dict)
        if len(self.new_rows) >= chunk_size:
            self._write()
