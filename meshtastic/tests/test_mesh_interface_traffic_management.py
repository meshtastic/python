"""Meshtastic unit tests for traffic management handling in mesh_interface.py."""

import pytest

from ..mesh_interface import MeshInterface
from ..protobuf import mesh_pb2


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_handleFromRadio_with_traffic_management_module_config():
    """Test _handleFromRadio with moduleConfig.traffic_management."""
    iface = MeshInterface(noProto=True)
    from_radio = mesh_pb2.FromRadio()
    from_radio.moduleConfig.traffic_management.position_min_interval_secs = 30
    from_radio.moduleConfig.traffic_management.rate_limit_window_secs = 60

    iface._handleFromRadio(from_radio.SerializeToString())

    assert iface.localNode.moduleConfig.traffic_management.position_min_interval_secs == 30
    assert iface.localNode.moduleConfig.traffic_management.rate_limit_window_secs == 60
    iface.close()
