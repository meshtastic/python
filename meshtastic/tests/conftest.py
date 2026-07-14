"""Common pytest code (place for fixtures)."""

import argparse
from unittest.mock import MagicMock

import pytest

from meshtastic import mt_config

from ..mesh_interface import MeshInterface
from .firmware_harness import (
    CHAIN_TOPOLOGY,
    DEFAULT_BASE_PORT,
    SimMesh,
    find_meshtasticd,
    is_compatible_host,
)
from .fw_helpers import set_region

# Use a different base port for the single-node fixture so it doesn't
# conflict with the multi-node mesh fixture.
SINGLE_NODE_BASE_PORT = DEFAULT_BASE_PORT + 100


def _skip_firmware_if_unavailable() -> None:
    """Skip the test when meshtasticd can't run on this host."""
    if not is_compatible_host():
        pytest.skip("meshtasticd firmware tests require Linux")
    if find_meshtasticd() is None:
        pytest.skip(
            "meshtasticd not found — set MESHTASTICD_BIN or install it on PATH"
        )


@pytest.fixture(scope="function")
def firmware_node():
    """A single meshtasticd sim node for smokevirt tests.

    Function-scoped so every test gets a freshly-erased node with no
    state leaking from previous tests. This makes destructive commands
    (``--reboot``, ``--set factory_reset true``) safe to run and lets
    tests be order-independent.

    Yields the SimNode instance.  The node is booted with a fresh erased
    config and listens on localhost at its TCP port.  Region is set to US
    so modem-preset tests work against firmware >= 2.8, which clamps
    presets to the legal set for the current region.
    """
    _skip_firmware_if_unavailable()
    mesh = SimMesh(n_nodes=1, base_port=SINGLE_NODE_BASE_PORT)
    mesh.start()
    node = mesh.get_node(0)
    set_region(node.port, "US")
    # The region commit restarts the TCP listener, so reconnect the harness
    # interface in case a test wants to use it directly.
    if node.iface is not None:
        try:
            node.iface.close()
        except Exception:  # pylint: disable=broad-except
            pass
    node.connect()
    yield node
    mesh.stop()


@pytest.fixture(scope="function")
def firmware_mesh():
    """A 3-node chain (A-B-C) meshtasticd sim mesh for smokemesh tests.

    Yields the SimMesh instance.  Nodes are connected and the SIMULATOR_APP
    packet bridge is running.  Region is set to US for firmware >= 2.8
    compatibility, interfaces are reconnected after the region change, and
    node DB convergence is awaited.
    """
    _skip_firmware_if_unavailable()
    mesh = SimMesh(n_nodes=3, topology=CHAIN_TOPOLOGY)
    mesh.start()
    for node in mesh.nodes:
        set_region(node.port, "US")
    # The region commit restarts each node's TCP listener, so reconnect the
    # harness interfaces before waiting for convergence.
    for node in mesh.nodes:
        if node.iface is not None:
            try:
                node.iface.close()
            except Exception:  # pylint: disable=broad-except
                pass
        node.connect()
    mesh.wait_for_convergence(timeout=30)
    yield mesh
    mesh.stop()


@pytest.fixture
def reset_mt_config():
    """Fixture to reset mt_config."""
    parser = None
    parser = argparse.ArgumentParser(add_help=False)
    mt_config.reset()
    mt_config.parser = parser


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
