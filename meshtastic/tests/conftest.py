"""Common pytest code (place for fixtures)."""

import argparse
from unittest.mock import MagicMock

import pytest

from meshtastic.__main__ import Globals

from ..mesh_interface import MeshInterface


@pytest.fixture
def reset_globals():
    """Fixture to reset globals."""
    parser = None
    parser = argparse.ArgumentParser()
    Globals.getInstance().reset()
    Globals.getInstance().set_parser(parser)


@pytest.fixture
def iface_with_nodes():
    """Fixture to setup some nodes."""
    nodesById = {
        "!9388f81c": {
            "num": 2475227164,
            "user": {
                "id": "!9388f81c",
                "longName": "Unknown f81c",
                "shortName": "?1C",
                "macaddr": "RBeTiPgc",
                "hwModel": "TBEAM",
            },
            "position": {},
            "lastHeard": 1640204888,
        }
    }

    nodesByNum = {
        2475227164: {
            "num": 2475227164,
            "user": {
                "id": "!9388f81c",
                "longName": "Unknown f81c",
                "shortName": "?1C",
                "macaddr": "RBeTiPgc",
                "hwModel": "TBEAM",
            },
            "position": {"time": 1640206266},
            "lastHeard": 1640206266,
        }
    }
    iface = MeshInterface(noProto=True)
    iface.nodes = nodesById
    iface.nodesByNum = nodesByNum
    myInfo = MagicMock()
    iface.myInfo = myInfo
    iface.myInfo.my_node_num = 2475227164
    return iface
