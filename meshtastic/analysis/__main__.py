"""Post-run analysis tools for meshtastic."""

import logging
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pyarrow as pa
import pyarrow.feather as feather
from dash import Dash, Input, Output, callback, dash_table, dcc, html
import dash_bootstrap_components as dbc

from .. import mesh_pb2, powermon_pb2

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

# sdir = '/home/kevinh/.local/share/meshtastic/slogs/20240626-152804'
sdir = "/home/kevinh/.local/share/meshtastic/slogs/latest"
dpwr = feather.read_table(f"{sdir}/power.feather").to_pandas(
    types_mapper=dtype_mapping.get
)
dslog = feather.read_table(f"{sdir}/slog.feather").to_pandas(
    types_mapper=dtype_mapping.get
)


def get_board_info():
    """Get the board information from the slog dataframe.

    tuple: A tuple containing the board ID and software version.
    """
    board_info = dslog[dslog["sw_version"].notnull()]
    sw_version = board_info.iloc[0]["sw_version"]
    board_id = mesh_pb2.HardwareModel.Name(board_info.iloc[0]["board_id"])
    return (board_id, sw_version)


pmon_events = dslog[dslog["pm_mask"].notnull()]


pm_masks = pd.Series(pmon_events["pm_mask"]).to_numpy()

# possible to do this with pandas rolling windows if I was smarter?
pm_changes = [(pm_masks[i - 1] ^ x if i != 0 else x) for i, x in enumerate(pm_masks)]
pm_raises = [(pm_masks[i] & x) for i, x in enumerate(pm_changes)]
pm_falls = [(~pm_masks[i] & x if i != 0 else 0) for i, x in enumerate(pm_changes)]


def to_pmon_names(arr) -> list[str]:
    """Convert the power monitor state numbers to their corresponding names.
    """

    def to_pmon_name(n):
        try:
            s = powermon_pb2.PowerMon.State.Name(int(n))
            return s if s != "None" else None
        except ValueError:
            return None

    return [to_pmon_name(x) for x in arr]


pd.options.mode.copy_on_write = True
pmon_events["pm_raises"] = to_pmon_names(pm_raises)
pmon_events["pm_falls"] = to_pmon_names(pm_falls)

pmon_raises = pmon_events[pmon_events["pm_raises"].notnull()]


def create_dash():
    """Create a Dash application for visualizing power consumption data."""
    app = Dash(
        external_stylesheets=[dbc.themes.BOOTSTRAP]
    )

    def set_legend(f, name):
        f["data"][0]["showlegend"] = True
        f["data"][0]["name"] = name
        return f

    df = dpwr
    avg_pwr_lines = px.line(df, x="time", y="average_mW").update_traces(
        line_color="red"
    )
    set_legend(avg_pwr_lines, "avg power")
    max_pwr_points = px.scatter(df, x="time", y="max_mW").update_traces(
        marker_color="blue"
    )
    set_legend(max_pwr_points, "max power")
    min_pwr_points = px.scatter(df, x="time", y="min_mW").update_traces(
        marker_color="green"
    )
    set_legend(min_pwr_points, "min power")

    pmon = pmon_raises
    fake_y = np.full(len(pmon), 10.0)
    pmon_points = px.scatter(pmon, x="time", y=fake_y, text="pm_raises")

    # fig = avg_pwr_lines
    # fig.add_trace(max_pwr_points)
    # don't show minpower because not that interesting: min_pwr_points.data
    fig = go.Figure(data=max_pwr_points.data + avg_pwr_lines.data + pmon_points.data)

    fig.update_layout(legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))

    # App layout
    app.layout = [
        html.Div(children="Early Meshtastic power analysis tool testing..."),
        # dash_table.DataTable(data=df.to_dict('records'), page_size=10),
        dcc.Graph(figure=fig),
    ]

    return app


def main():
    """Entry point of the script."""
    app = create_dash()
    port = 8051
    logging.info(f"Running Dash visualization webapp on port {port} (publicly accessible)")
    app.run_server(debug=True, host='0.0.0.0', port=port)


if __name__ == "__main__":
    main()
