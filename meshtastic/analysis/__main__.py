"""Post-run analysis tools for meshtastic."""

import argparse
import logging
from typing import cast, List

import dash_bootstrap_components as dbc  # type: ignore[import-untyped]
import numpy as np
import pandas as pd
import plotly.express as px  # type: ignore[import-untyped]
import plotly.graph_objects as go  # type: ignore[import-untyped]
import pyarrow as pa
from dash import Dash, dcc, html  # type: ignore[import-untyped]
from pyarrow import feather

from .. import mesh_pb2, powermon_pb2
from ..slog import root_dir

# Configure panda options
pd.options.mode.copy_on_write = True


def to_pmon_names(arr) -> List[str]:
    """Convert the power monitor state numbers to their corresponding names.

    arr (list): List of power monitor state numbers.

    Returns the List of corresponding power monitor state names.
    """

    def to_pmon_name(n):
        try:
            s = powermon_pb2.PowerMon.State.Name(int(n))
            return s if s != "None" else None
        except ValueError:
            return None

    return [to_pmon_name(x) for x in arr]


def read_pandas(filepath: str) -> pd.DataFrame:
    """Read a feather file and convert it to a pandas DataFrame.

    filepath (str): Path to the feather file.

    Returns the pandas DataFrame.
    """
    # per https://arrow.apache.org/docs/python/pandas.html#reducing-memory-use-in-table-to-pandas
    # use this to get nullable int fields treated as ints rather than floats in pandas
    dtype_mapping = {
        pa.int8(): pd.Int8Dtype(),
        pa.int16(): pd.Int16Dtype(),
        pa.int32(): pd.Int32Dtype(),
        pa.int64(): pd.Int64Dtype(),
        pa.uint8(): pd.UInt8Dtype(),
        pa.uint16(): pd.UInt16Dtype(),
        pa.uint32(): pd.UInt32Dtype(),
        pa.uint64(): pd.UInt64Dtype(),
        pa.bool_(): pd.BooleanDtype(),
        pa.float32(): pd.Float32Dtype(),
        pa.float64(): pd.Float64Dtype(),
        pa.string(): pd.StringDtype(),
    }

    return cast(pd.DataFrame, feather.read_table(filepath).to_pandas(types_mapper=dtype_mapping.get))  # type: ignore[arg-type]


def get_pmon_raises(dslog: pd.DataFrame) -> pd.DataFrame:
    """Get the power monitor raises from the slog DataFrame.

        dslog (pd.DataFrame): The slog DataFrame.

    Returns the DataFrame containing the power monitor raises.
    """
    pmon_events = dslog[dslog["pm_mask"].notnull()]

    pm_masks = pd.Series(pmon_events["pm_mask"]).to_numpy()

    # possible to do this with pandas rolling windows if I was smarter?
    pm_changes = [
        (pm_masks[i - 1] ^ x if i != 0 else x) for i, x in enumerate(pm_masks)
    ]
    pm_raises = [(pm_masks[i] & x) for i, x in enumerate(pm_changes)]
    pm_falls = [(~pm_masks[i] & x if i != 0 else 0) for i, x in enumerate(pm_changes)]

    pmon_events["pm_raises"] = to_pmon_names(pm_raises)
    pmon_events["pm_falls"] = to_pmon_names(pm_falls)

    pmon_raises = pmon_events[pmon_events["pm_raises"].notnull()][["time", "pm_raises"]]
    pmon_falls = pmon_events[pmon_events["pm_falls"].notnull()]

    # pylint: disable=unused-variable
    def get_endtime(row):
        """Find the corresponding fall event."""
        following = pmon_falls[
            (pmon_falls["pm_falls"] == row["pm_raises"])
            & (pmon_falls["time"] > row["time"])
        ]
        return following.iloc[0] if not following.empty else None

    # HMM - setting end_time doesn't work yet - leave off for now
    # pmon_raises['end_time'] = pmon_raises.apply(get_endtime, axis=1)

    return pmon_raises


def get_board_info(dslog: pd.DataFrame) -> tuple:
    """Get the board information from the slog DataFrame.

    dslog (pd.DataFrame): The slog DataFrame.

    Returns a tuple containing the board ID and software version.
    """
    board_info = dslog[dslog["sw_version"].notnull()]
    sw_version = board_info.iloc[0]["sw_version"]
    board_id = mesh_pb2.HardwareModel.Name(board_info.iloc[0]["board_id"])
    return (board_id, sw_version)


def create_argparser() -> argparse.ArgumentParser:
    """Create the argument parser for the script."""
    parser = argparse.ArgumentParser(description="Meshtastic power analysis tools")
    group = parser
    group.add_argument(
        "--slog",
        help="Specify the structured-logs directory (defaults to latest log directory)",
    )
    group.add_argument(
        "--no-server",
        action="store_true",
        help="Exit immediately, without running the visualization web server",
    )

    return parser


def create_dash(slog_path: str) -> Dash:
    """Create a Dash application for visualizing power consumption data.

    slog_path (str): Path to the slog directory.

    Returns the Dash application.
    """
    app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

    dpwr = read_pandas(f"{slog_path}/power.feather")
    dslog = read_pandas(f"{slog_path}/slog.feather")

    pmon_raises = get_pmon_raises(dslog)

    def set_legend(f, name):
        f["data"][0]["showlegend"] = True
        f["data"][0]["name"] = name
        return f

    avg_pwr_lines = px.line(dpwr, x="time", y="average_mW").update_traces(
        line_color="red"
    )
    set_legend(avg_pwr_lines, "avg power")
    max_pwr_points = px.scatter(dpwr, x="time", y="max_mW").update_traces(
        marker_color="blue"
    )
    set_legend(max_pwr_points, "max power")
    min_pwr_points = px.scatter(dpwr, x="time", y="min_mW").update_traces(
        marker_color="green"
    )
    set_legend(min_pwr_points, "min power")

    fake_y = np.full(len(pmon_raises), 10.0)
    pmon_points = px.scatter(pmon_raises, x="time", y=fake_y, text="pm_raises")

    fig = go.Figure(data=max_pwr_points.data + avg_pwr_lines.data + pmon_points.data)

    fig.update_layout(
        legend={"yanchor": "top", "y": 0.99, "xanchor": "left", "x": 0.01}
    )

    # App layout
    app.layout = [
        html.Div(children="Meshtastic power analysis tool testing..."),
        dcc.Graph(figure=fig),
    ]

    return app


def main():
    """Entry point of the script."""

    parser = create_argparser()
    args = parser.parse_args()
    if not args.slog:
        args.slog = f"{root_dir()}/latest"

    app = create_dash(slog_path=args.slog)
    port = 8051
    logging.info(f"Running Dash visualization of {args.slog} (publicly accessible)")

    if not args.no_server:
        app.run_server(debug=True, host="0.0.0.0", port=port)
    else:
        logging.info("Exiting without running visualization server")


if __name__ == "__main__":
    main()
