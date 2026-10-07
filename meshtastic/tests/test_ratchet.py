"""Direct-message forward secrecy: the settings by name and the per-node column."""

import pytest

from meshtastic.__main__ import setPref
from meshtastic.mesh_interface import MeshInterface
from meshtastic.protobuf import localonly_pb2


@pytest.mark.unit
def test_ratchet_settings_set_by_name():
    config = localonly_pb2.LocalConfig()
    assert setPref(config, "security.ratchet_enabled", "true")
    assert setPref(config, "security.require_ratchet_when_known", "true")
    assert setPref(config, "security.ratchet_interval_secs", "7200")
    assert config.security.ratchet_flags == 0x03
    assert config.security.ratchet_interval_secs == 7200
    assert setPref(config, "security.require_ratchet_when_known", "false")
    assert config.security.ratchet_flags == 0x01


@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
def test_show_nodes_marks_nodes_with_a_ratchet_key():
    iface = MeshInterface(noProto=True)
    iface.nodesByNum = {
        1: {"num": 1, "user": {"id": "!00000001", "longName": "Ratchet Node"}, "lastHeard": 2, "hasRatchet": True},
        2: {"num": 2, "user": {"id": "!00000002", "longName": "Static Node"}, "lastHeard": 1},
    }
    table = iface.showNodes(showFields=["user.longName", "hasRatchet"])
    lines = table.splitlines()
    assert "Ratchet" in lines[1]
    assert "*" in next(line for line in lines if "Ratchet Node" in line)
    assert "*" not in next(line for line in lines if "Static Node" in line)
    iface.close()
