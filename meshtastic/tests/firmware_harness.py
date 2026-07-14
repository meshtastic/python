"""Test harness for running real meshtasticd firmware instances.

Launches one or more meshtasticd processes in simulator mode (-s) and bridges
their "over-the-air" packets via the SIMULATOR_APP protocol so that multiple
instances can communicate as if via LoRa, with a configurable topology.

The harness expects meshtasticd to be available on PATH or via the
MESHTASTICD_BIN environment variable.  It does not download or build the
binary itself.
"""
import logging
import os
import platform
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from typing import Dict, List, Optional, Set

from pubsub import pub  # type: ignore[import-untyped]

from meshtastic import BROADCAST_NUM, mesh_pb2, portnums_pb2
from meshtastic.tcp_interface import TCPInterface

logger = logging.getLogger(__name__)

HW_ID_OFFSET = 16
DEFAULT_BASE_PORT = 4404
DEFAULT_RSSI = -50
DEFAULT_SNR = 10.0
BOOT_TIMEOUT = 30
CONNECT_TIMEOUT = 30

CHAIN_TOPOLOGY: Dict[int, Set[int]] = {
    0: {1},
    1: {0, 2},
    2: {1},
}


def find_meshtasticd() -> Optional[str]:
    """Return the path to the meshtasticd binary, or None if not found."""
    env_path = os.environ.get("MESHTASTICD_BIN")
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        return env_path
    return shutil.which("meshtasticd")


def is_compatible_host() -> bool:
    """True when the host can run meshtasticd natively (Linux only)."""
    return platform.system() == "Linux"


def _wait_for_port(port: int, timeout: int = BOOT_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            s = socket.create_connection(("localhost", port), timeout=0.5)
            s.close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


class SimNode:
    """A single meshtasticd simulator instance."""

    def __init__(self, node_id: int, base_port: int = DEFAULT_BASE_PORT):
        self.node_id = node_id
        self.hw_id = node_id + HW_ID_OFFSET
        self.port = base_port + node_id
        self.process: Optional[subprocess.Popen] = None
        self.workdir: Optional[str] = None
        self.iface: Optional[TCPInterface] = None
        self._log_files: list = []

    @property
    def node_num(self) -> int:
        """The firmware-assigned node number (== hw_id)."""
        if self.iface and self.iface.myInfo:
            return self.iface.myInfo.my_node_num
        return self.hw_id

    def start(self, binary: str) -> None:
        """Launch the meshtasticd process in simulator mode."""
        self.workdir = tempfile.mkdtemp(prefix=f"mtd_node{self.node_id}_")
        vfs_dir = os.path.join(self.workdir, "vfs")
        os.mkdir(vfs_dir)
        # Files are closed in _kill(); keep them open for the process lifetime.
        log_stdout = open(  # pylint: disable=consider-using-with
            os.path.join(self.workdir, "meshtasticd.log"), "wb", buffering=0
        )
        log_stderr = open(  # pylint: disable=consider-using-with
            os.path.join(self.workdir, "meshtasticd.err"), "wb", buffering=0
        )
        self._log_files = [log_stdout, log_stderr]
        self.process = subprocess.Popen(  # pylint: disable=consider-using-with
            [
                binary,
                "-s",
                "-h", str(self.hw_id),
                "-p", str(self.port),
                "-d", vfs_dir,
                "-e",
            ],
            stdout=log_stdout,
            stderr=log_stderr,
            start_new_session=True,
        )
        if not _wait_for_port(self.port):
            self._kill()
            raise RuntimeError(
                f"meshtasticd node {self.node_id} did not start listening on port {self.port}"
            )
    def connect(self) -> None:
        """Open a TCPInterface connection to this node."""
        self.iface = TCPInterface(
            hostname="localhost",
            portNumber=self.port,
            connectNow=False,
        )
        self.iface.myConnect()
        self.iface.connect()

    def close(self) -> None:
        """Close the interface and kill the process."""
        if self.iface is not None:
            try:
                self.iface.localNode.exitSimulator()
            except Exception:
                pass
            try:
                self.iface.close()
            except Exception:
                pass
            self.iface = None
        self._kill()
        if self.workdir:
            shutil.rmtree(self.workdir, ignore_errors=True)
            self.workdir = None

    def _kill(self) -> None:
        for f in self._log_files:
            try:
                f.close()
            except Exception:
                pass
        self._log_files = []
        if self.process is not None:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            try:
                self.process.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except Exception:
                    pass
            # Give OS time to release TCP port (avoid TIME_WAIT preventing
            # next instance from binding the same port)
            time.sleep(1.0)
            self.process = None


class SimMesh:
    """Manages N meshtasticd sim instances and bridges their SIMULATOR_APP packets.

    When *topology* is None every node hears every other node (full mesh).
    Otherwise *topology* maps a transmitter's node index to the set of receiver
    node indices that can hear it.
    """

    def __init__(
        self,
        n_nodes: int = 1,
        topology: Optional[Dict[int, Set[int]]] = None,
        base_port: int = DEFAULT_BASE_PORT,
    ):
        self.n_nodes = n_nodes
        self.topology = topology
        self.base_port = base_port
        self.nodes: List[SimNode] = [
            SimNode(i, base_port) for i in range(n_nodes)
        ]
        self._port_to_idx: Dict[int, int] = {}
        self._started = False

    def start(self) -> None:
        """Launch all nodes, connect, and start the packet bridge."""
        binary = find_meshtasticd()
        if binary is None:
            raise RuntimeError(
                "meshtasticd not found. Set MESHTASTICD_BIN or install it on PATH."
            )

        for node in self.nodes:
            node.start(binary)

        for node in self.nodes:
            node.connect()
            self._port_to_idx[node.port] = node.node_id

        pub.subscribe(self._on_sim_packet, "meshtastic.receive.simulator")
        self._started = True

        if self.n_nodes > 1:
            self._trigger_convergence()

    def _trigger_convergence(self) -> None:
        """Actively trigger NodeInfo exchange instead of waiting passively.

        Sends a NODEINFO_APP packet with wantResponse from each node so the
        firmware's NodeInfoModule responds with its own user info, populating
        all node DBs deterministically.
        """
        for node in self.nodes:
            iface = node.iface
            if iface is None:
                continue
            user = mesh_pb2.User()
            user.id = f"!{node.node_num:08x}"
            user.long_name = f"Node {node.node_id}"
            user.short_name = f"{node.node_id:04d}"[:4]
            user.hw_model = mesh_pb2.HardwareModel.PORTDUINO
            try:
                iface.sendData(
                    user,
                    destinationId=BROADCAST_NUM,
                    portNum=portnums_pb2.PortNum.NODEINFO_APP,
                    wantAck=False,
                    wantResponse=True,
                )
            except Exception as ex:
                logger.debug("NodeInfo trigger for node %d failed: %s", node.node_id, ex)
        time.sleep(5)

    def stop(self) -> None:
        """Shut down all nodes and clean up."""
        if not self._started:
            return
        try:
            pub.unsubscribe(self._on_sim_packet, "meshtastic.receive.simulator")
        except Exception:
            pass
        for node in self.nodes:
            node.close()
        self._started = False

    def get_node(self, idx: int) -> SimNode:
        """Return the SimNode at the given index."""
        return self.nodes[idx]

    def get_iface(self, idx: int) -> TCPInterface:
        """Return the TCPInterface for the node at the given index."""
        iface = self.nodes[idx].iface
        assert iface is not None, f"node {idx} has no interface"
        return iface

    def wait_for_convergence(self, timeout: int = 30) -> bool:
        """Wait until every node sees all others in its node DB.

        Returns True if converged, False if timed out (non-fatal — the packet
        bridge forwards regardless of node DB state).
        """
        if self.n_nodes <= 1:
            return True
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if all(
                node.iface is not None
                and node.iface.nodes is not None
                and len(node.iface.nodes) >= self.n_nodes
                for node in self.nodes
            ):
                return True
            time.sleep(2)
        logger.warning("Mesh did not fully converge within %ds", timeout)
        return False

    def _get_receivers(self, tx_idx: int) -> List[int]:
        """Return node indices that can hear a transmission from *tx_idx*."""
        if self.topology is not None:
            return sorted(self.topology.get(tx_idx, set()))
        return [i for i in range(self.n_nodes) if i != tx_idx]

    def _on_sim_packet(self, interface, packet) -> None:
        """Bridge callback: forward a SIMULATOR_APP packet to receiving nodes."""
        tx_port = getattr(interface, "portNumber", None)
        tx_idx = self._port_to_idx.get(tx_port) if tx_port else None
        if tx_idx is None:
            return

        rx_indices = self._get_receivers(tx_idx)
        if not rx_indices:
            return

        data = packet["decoded"]["payload"]
        if hasattr(data, "SerializeToString"):
            data = data.SerializeToString()

        if len(data) > mesh_pb2.Constants.DATA_PAYLOAD_LEN:
            logger.warning("Simulator payload too big (%d bytes), dropping", len(data))
            return

        mesh_packet = _build_mesh_packet(packet, data)

        for rx_idx in rx_indices:
            rx_iface = self.nodes[rx_idx].iface
            if rx_iface is None:
                continue
            mesh_packet.rx_rssi = DEFAULT_RSSI
            mesh_packet.rx_snr = DEFAULT_SNR
            to_radio = mesh_pb2.ToRadio()
            to_radio.packet.CopyFrom(mesh_packet)
            try:
                rx_iface._sendToRadio(to_radio)
            except Exception as ex:
                logger.error("Error forwarding packet to node %d: %s", rx_idx, ex)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()


def _build_mesh_packet(packet: dict, data: bytes) -> mesh_pb2.MeshPacket:
    """Reconstruct a MeshPacket for SIMULATOR_APP injection."""
    mp = mesh_pb2.MeshPacket()
    mp.decoded.payload = data
    mp.decoded.portnum = portnums_pb2.PortNum.SIMULATOR_APP
    mp.to = packet.get("to", BROADCAST_NUM)
    setattr(mp, "from", packet.get("from", 0))
    mp.id = packet.get("id", 0)
    mp.want_ack = packet.get("wantAck", False)
    mp.hop_limit = packet.get("hopLimit", 0)
    mp.hop_start = packet.get("hopStart", 0)
    mp.via_mqtt = packet.get("viaMQTT", False)
    mp.relay_node = packet.get("relayNode", 0)
    mp.next_hop = packet.get("nextHop", 0)
    mp.channel = int(packet.get("channel", 0))

    decoded = packet.get("decoded", {})
    if "requestId" in decoded:
        mp.decoded.request_id = decoded["requestId"]
    if "wantResponse" in decoded:
        mp.decoded.want_response = decoded["wantResponse"]

    return mp
