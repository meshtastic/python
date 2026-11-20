"""Tests for module config handling in mesh_interface.py."""

import pytest

from ..mesh_interface import MeshInterface
from ..protobuf import atak_pb2, mesh_pb2, module_config_pb2


MODULE_CONFIG_VARIANTS = tuple(
    field.name
    for field in module_config_pb2.ModuleConfig.DESCRIPTOR.oneofs_by_name[
        "payload_variant"
    ].fields
)


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@pytest.mark.parametrize("variant", MODULE_CONFIG_VARIANTS)
def test_handleFromRadio_copies_every_module_config_variant(variant):
    """Every module config variant received from the radio is retained."""
    iface = MeshInterface(noProto=True)
    from_radio = mesh_pb2.FromRadio()
    getattr(from_radio.moduleConfig, variant).SetInParent()

    iface._handleFromRadio(from_radio.SerializeToString())

    assert iface.localNode.moduleConfig.HasField(variant)
    assert getattr(iface.localNode.moduleConfig, variant) == getattr(
        from_radio.moduleConfig, variant
    )
    iface.close()


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_handleFromRadio_copies_tak_module_config_values():
    """TAK team and role values received from the radio are retained."""
    iface = MeshInterface(noProto=True)
    from_radio = mesh_pb2.FromRadio()
    from_radio.moduleConfig.tak.team = atak_pb2.Cyan
    from_radio.moduleConfig.tak.role = atak_pb2.Medic

    iface._handleFromRadio(from_radio.SerializeToString())

    assert iface.localNode.moduleConfig.HasField("tak")
    assert iface.localNode.moduleConfig.tak == from_radio.moduleConfig.tak
    iface.close()
