"""Filesystem operations for the Meshtastic mesh interface."""

from __future__ import annotations

import collections
import logging
import threading
import time
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional, Union

from meshtastic.protobuf import admin_pb2, mesh_pb2, xmodem_pb2

logger = logging.getLogger(__name__)


class FsOperationError(Exception):
    """Raised when a filesystem-related operation fails."""


class FsInterface:
    """Encapsulates filesystem and XMODEM logic for `MeshInterface`."""

    def __init__(self, mesh: "MeshInterface") -> None:  # type: ignore[name-defined]
        self._mesh = mesh
        self.entries: "collections.OrderedDict[str, Optional[int]]" = collections.OrderedDict()
        self._xmodem_lock: threading.Lock = threading.Lock()
        self._xmodem_state: Optional[Dict[str, Any]] = None

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def show(self) -> str:
        """Display filesystem entries reported by the radio."""

        if not self.entries:
            message = "No filesystem entries received."
            print(message)
            return message

        rows = []
        for path, size in self.entries.items():
            size_str = str(size) if size or size == 0 else "-"
            rows.append((path, size_str))

        from tabulate import tabulate  # local import to avoid global dependency churn

        table = tabulate(rows, headers=("Path", "Size (bytes)"), tablefmt="plain")
        print(table)
        return table

    def record_file_info(self, file_name: str, size_bytes: Optional[int]) -> None:
        """Update known filesystem entries."""

        self.entries[file_name] = size_bytes

    def download(
        self,
        node_src: str,
        host_dst: Optional[str] = None,
        *,
        overwrite: bool = False,
        timeout: int = 120,
    ) -> str:
        """Download a file from the device."""

        if not node_src:
            raise FsOperationError("Remote path must be provided.")

        node_src_clean = node_src.strip()
        if not node_src_clean:
            raise FsOperationError("Remote path must not be empty.")

        destination = Path(host_dst or ".")
        if destination.is_dir():
            destination = destination / Path(node_src_clean).name

        if destination.exists() and not overwrite:
            raise FsOperationError(f"Destination file '{destination}' already exists.")

        destination.parent.mkdir(parents=True, exist_ok=True)

        transfer_event = threading.Event()
        file_handle = open(destination, "wb")

        with self._xmodem_lock:
            if self._xmodem_state and not self._xmodem_state.get("done"):
                file_handle.close()
                raise FsOperationError("Another XMODEM transfer is already in progress.")
            self._xmodem_state = {
                "mode": "download",
                "expected_seq": 1,
                "file": file_handle,
                "event": transfer_event,
                "path": str(destination),
                "success": None,
                "error": None,
                "done": False,
                "closed": False,
                "remove_local_on_fail": False,
                "delete_remote_on_fail": False,
                "last_activity": time.time(),
            }

        try:
            self._send_xmodem_request(node_src_clean)
        except Exception as ex:
            cleanup_target = None
            with self._xmodem_lock:
                self._complete_xmodem_locked(False, f"Failed to start XMODEM transfer: {ex}")
                cleanup_target = self._cleanup_xmodem_state_locked(remove_partial=True)
            if cleanup_target:
                self._delete_remote_file(cleanup_target)
            raise

        if not transfer_event.wait(timeout):
            cleanup_target = None
            with self._xmodem_lock:
                # Attempt to cancel on timeout
                try:
                    self._send_xmodem_control(xmodem_pb2.XModem.Control.CAN)
                except Exception as ex:
                    logger.debug(f"Failed to send XMODEM cancel: {ex}")
                self._complete_xmodem_locked(False, "Timed out waiting for XMODEM transfer.")
                state = self._xmodem_state
                error_message = "Timed out waiting for XMODEM transfer."
                if state and state.get("error"):
                    error_message = state["error"]
                cleanup_target = self._cleanup_xmodem_state_locked(remove_partial=True)
            if cleanup_target:
                self._delete_remote_file(cleanup_target)
            raise FsOperationError(error_message)

        cleanup_target = None
        with self._xmodem_lock:
            state = self._xmodem_state
            if not state:
                raise FsOperationError("XMODEM transfer state missing.")
            success = bool(state.get("success"))
            error_message = state.get("error")
            destination_path = state.get("path")
            remove_partial = state.get("remove_local_on_fail", False)
            cleanup_target = self._cleanup_xmodem_state_locked(remove_partial=remove_partial)

        if cleanup_target:
            self._delete_remote_file(cleanup_target)

        if not success:
            raise FsOperationError(error_message or "XMODEM transfer failed.")

        return destination_path or str(destination)

    def upload(
        self,
        host_src: Union[str, Path],
        device_dst: Optional[str] = None,
        *,
        overwrite: bool = False,
        timeout: int = 120,
    ) -> str:
        """Upload a file to the device."""

        logger.debug(
            "upload host_src=%s device_dst=%s overwrite=%s timeout=%s",
            host_src,
            device_dst,
            overwrite,
            timeout,
        )

        host_path = Path(host_src).expanduser()
        if not host_path.is_file():
            raise FsOperationError(f"Host source '{host_src}' is not a file.")

        dest_str = device_dst if device_dst is not None else "/"
        if dest_str in ("", "."):
            dest_str = "/"
        logger.debug("upload normalized dest_str='%s'", dest_str)

        if dest_str.endswith("/"):
            remote_path = PurePosixPath(dest_str) / host_path.name
        else:
            remote_path = PurePosixPath(dest_str)
            if str(remote_path).endswith("/"):
                remote_path = remote_path / host_path.name

        if not str(remote_path).startswith("/"):
            remote_path = PurePosixPath("/") / remote_path

        remote_path_str = str(remote_path)
        logger.debug("upload computed remote_path='%s'", remote_path_str)

        if not overwrite and remote_path_str in self.entries:
            raise FsOperationError(
                f"Remote file '{remote_path_str}' already exists (use overwrite=True to replace it)."
            )

        if overwrite:
            logger.debug("upload overwrite=True; deleting existing '%s'", remote_path_str)
            self._delete_remote_file(remote_path_str)

        transfer_event = threading.Event()
        file_handle = open(host_path, "rb")
        logger.debug("upload opened host file '%s'", host_path)

        with self._xmodem_lock:
            if self._xmodem_state and not self._xmodem_state.get("done"):
                file_handle.close()
                raise FsOperationError("Another XMODEM transfer is already in progress.")
            self._xmodem_state = {
                "mode": "upload",
                "expected_seq": 1,
                "file": file_handle,
                "event": transfer_event,
                "path": str(host_path),
                "remote_path": remote_path_str,
                "success": None,
                "error": None,
                "done": False,
                "closed": False,
                "chunk_size": 256,
                "awaiting": "start",
                "max_retries": 5,
                "retries": 0,
                "pending_chunk": None,
                "pending_seq": None,
                "remove_local_on_fail": False,
                "delete_remote_on_fail": False,
                "last_activity": time.time(),
            }

        try:
            self._start_upload(remote_path_str)
        except Exception as ex:
            cleanup_target = None
            with self._xmodem_lock:
                self._complete_xmodem_locked(False, f"Failed to start XMODEM transfer: {ex}")
                cleanup_target = self._cleanup_xmodem_state_locked(remove_partial=True)
            if cleanup_target:
                self._delete_remote_file(cleanup_target)
            raise

        if not transfer_event.wait(timeout):
            cleanup_target = None
            with self._xmodem_lock:
                try:
                    self._send_xmodem_control(xmodem_pb2.XModem.Control.CAN)
                except Exception as ex:
                    logger.debug(f"Failed to send XMODEM cancel: {ex}")
                self._complete_xmodem_locked(
                    False, "Timed out waiting for XMODEM upload to complete."
                )
                state = self._xmodem_state
                error_message = "Timed out waiting for XMODEM transfer."
                if state and state.get("error"):
                    error_message = state["error"]
                cleanup_target = self._cleanup_xmodem_state_locked(remove_partial=True)
            if cleanup_target:
                self._delete_remote_file(cleanup_target)
            raise FsOperationError(error_message)

        cleanup_target = None
        with self._xmodem_lock:
            state = self._xmodem_state
            if not state:
                raise FsOperationError("XMODEM transfer state missing.")
            success = bool(state.get("success"))
            error_message = state.get("error")
            cleanup_target = self._cleanup_xmodem_state_locked(
                remove_partial=state.get("delete_remote_on_fail", False)
            )

        if cleanup_target:
            self._delete_remote_file(cleanup_target)

        if not success:
            raise FsOperationError(error_message or "XMODEM transfer failed.")

        self.entries[remote_path_str] = host_path.stat().st_size

        return remote_path_str

    def delete(self, remote_path: str) -> None:
        """Delete a file from the device filesystem."""

        if not remote_path:
            raise FsOperationError("Remote path must be provided.")

        path_clean = remote_path.strip()
        if not path_clean:
            raise FsOperationError("Remote path must not be empty.")

        normalized = PurePosixPath(path_clean)
        if not str(normalized).startswith("/"):
            normalized = PurePosixPath("/") / normalized

        remote_path_str = str(normalized)

        self._delete_remote_file(remote_path_str)
        self.entries.pop(remote_path_str, None)

    # ---------------------------------------------------------------------
    # Mesh integration helpers
    # ---------------------------------------------------------------------
    def handle_xmodem_packet(self, packet: xmodem_pb2.XModem) -> None:
        """Process an incoming XMODEM packet from the device."""

        control_to_send: Optional[xmodem_pb2.XModem.Control.ValueType] = None
        seq_to_send = packet.seq
        payload_to_send: Optional[bytes] = None
        crc_to_send: Optional[int] = None

        with self._xmodem_lock:
            state = self._xmodem_state
            if not state or state.get("done"):
                return

            control = packet.control
            mode = state.get("mode", "download")

            if mode == "download":
                control_to_send, payload_to_send, crc_to_send = self._handle_download_packet(state, packet)
            elif mode == "upload":
                control_to_send, payload_to_send, crc_to_send, seq_to_send = self._handle_upload_packet(
                    state,
                    packet,
                    seq_to_send,
                )
            else:
                logger.error("Unknown XMODEM mode %s", mode)

        if control_to_send is not None:
            try:
                self._send_xmodem_control(
                    control_to_send,
                    seq_to_send,
                    payload_to_send or b"",
                    crc_to_send,
                )
            except Exception as ex:
                logger.error(f"Failed to send XMODEM control {control_to_send}: {ex}")

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _handle_download_packet(
        self,
        state: Dict[str, Any],
        packet: xmodem_pb2.XModem,
    ) -> tuple[Optional[xmodem_pb2.XModem.Control.ValueType], Optional[bytes], Optional[int]]:
        control_to_send: Optional[xmodem_pb2.XModem.Control.ValueType] = None
        payload_to_send: Optional[bytes] = None
        crc_to_send: Optional[int] = None

        control = packet.control
        if control in (xmodem_pb2.XModem.Control.SOH, xmodem_pb2.XModem.Control.STX):
            expected_seq = state.get("expected_seq", 1)
            seq = packet.seq
            if seq != expected_seq:
                logger.warning(
                    "Unexpected XMODEM sequence. expected=%s got=%s",
                    expected_seq,
                    seq,
                )
                control_to_send = xmodem_pb2.XModem.Control.NAK
                state["last_activity"] = time.time()
            else:
                data = packet.buffer
                crc_local = self._crc16_ccitt(data)
                if packet.crc16 != crc_local:
                    logger.warning(
                        "XMODEM CRC mismatch for %s. expected=%s got=%s",
                        state.get("path"),
                        packet.crc16,
                        crc_local,
                    )
                    control_to_send = xmodem_pb2.XModem.Control.NAK
                    state["last_activity"] = time.time()
                else:
                    try:
                        file_handle = state["file"]
                        file_handle.write(data)
                    except Exception as ex:
                        logger.error("Error writing XMODEM data to %s: %s", state.get("path"), ex)
                        self._complete_xmodem_locked(
                            False,
                            f"Failed writing to {state.get('path')}: {ex}",
                        )
                        control_to_send = xmodem_pb2.XModem.Control.CAN
                    else:
                        state["expected_seq"] = expected_seq + 1
                        state["last_activity"] = time.time()
                        control_to_send = xmodem_pb2.XModem.Control.ACK
        elif control == xmodem_pb2.XModem.Control.EOT:
            control_to_send = xmodem_pb2.XModem.Control.ACK
            self._complete_xmodem_locked(True)
        elif control == xmodem_pb2.XModem.Control.NAK:
            logger.error("Device reported NAK while sending %s", state.get("path"))
            self._complete_xmodem_locked(False, "Device reported NAK during XMODEM transfer.")
        elif control == xmodem_pb2.XModem.Control.CAN:
            logger.error("Device cancelled XMODEM transfer for %s", state.get("path"))
            self._complete_xmodem_locked(False, "Device cancelled the XMODEM transfer.")
        elif control == xmodem_pb2.XModem.Control.ACK:
            # Ignore ACKs from device during download.
            pass
        else:
            logger.error("Unsupported XMODEM control %s", control)
            control_to_send = xmodem_pb2.XModem.Control.CAN
            self._complete_xmodem_locked(False, f"Unsupported XMODEM control {control}.")

        return control_to_send, payload_to_send, crc_to_send

    def _handle_upload_packet(
        self,
        state: Dict[str, Any],
        packet: xmodem_pb2.XModem,
        seq_to_send: int,
    ) -> tuple[
        Optional[xmodem_pb2.XModem.Control.ValueType],
        Optional[bytes],
        Optional[int],
        int,
    ]:
        control_to_send: Optional[xmodem_pb2.XModem.Control.ValueType] = None
        payload_to_send: Optional[bytes] = None
        crc_to_send: Optional[int] = None

        control = packet.control
        awaiting = state.get("awaiting", "start")
        chunk_size = state.get("chunk_size", 128)

        if control == xmodem_pb2.XModem.Control.ACK:
            state["last_activity"] = time.time()
            if awaiting in (None, "start"):
                state["awaiting"] = None
                chunk = state["file"].read(chunk_size)
                if chunk:
                    seq_to_send = state.get("expected_seq", 1)
                    state["expected_seq"] = seq_to_send + 1
                    state["pending_chunk"] = chunk
                    state["pending_seq"] = seq_to_send
                    state["awaiting"] = "data"
                    state["retries"] = 0
                    payload_to_send = chunk
                    crc_to_send = self._crc16_ccitt(chunk)
                    control_to_send = xmodem_pb2.XModem.Control.SOH
                else:
                    state["awaiting"] = "eot"
                    state["retries"] = 0
                    state["eot_sent"] = True
                    control_to_send = xmodem_pb2.XModem.Control.EOT
                    seq_to_send = state.get("expected_seq", 0)
            elif awaiting == "data":
                chunk = state["file"].read(chunk_size)
                if chunk:
                    seq_to_send = state.get("expected_seq", 1)
                    state["expected_seq"] = seq_to_send + 1
                    state["pending_chunk"] = chunk
                    state["pending_seq"] = seq_to_send
                    state["awaiting"] = "data"
                    state["retries"] = 0
                    payload_to_send = chunk
                    crc_to_send = self._crc16_ccitt(chunk)
                    control_to_send = xmodem_pb2.XModem.Control.SOH
                else:
                    state["awaiting"] = "eot"
                    state["retries"] = 0
                    state["eot_sent"] = True
                    control_to_send = xmodem_pb2.XModem.Control.EOT
                    seq_to_send = state.get("expected_seq", 0)
            elif awaiting == "eot":
                self._complete_xmodem_locked(True)
        elif control == xmodem_pb2.XModem.Control.NAK:
            if awaiting in (None, "start"):
                self._complete_xmodem_locked(
                    False,
                    "Device rejected destination path. Ensure directories exist and permissions allow writing.",
                )
                control_to_send = xmodem_pb2.XModem.Control.CAN
            elif awaiting == "data":
                retries = state.get("retries", 0) + 1
                state["retries"] = retries
                if retries > state.get("max_retries", 5):
                    self._complete_xmodem_locked(False, "Too many NAKs received during upload.")
                    control_to_send = xmodem_pb2.XModem.Control.CAN
                else:
                    chunk = state.get("pending_chunk")
                    seq = state.get("pending_seq")
                    if chunk is not None and seq is not None:
                        seq_to_send = seq
                        payload_to_send = chunk
                        crc_to_send = self._crc16_ccitt(chunk)
                        control_to_send = xmodem_pb2.XModem.Control.SOH
            elif awaiting == "eot":
                retries = state.get("retries", 0) + 1
                state["retries"] = retries
                if retries > state.get("max_retries", 5):
                    self._complete_xmodem_locked(False, "Timeout while finalizing upload.")
                    control_to_send = xmodem_pb2.XModem.Control.CAN
                else:
                    control_to_send = xmodem_pb2.XModem.Control.EOT
                    seq_to_send = state.get("expected_seq", 0)
        elif control == xmodem_pb2.XModem.Control.CAN:
            self._complete_xmodem_locked(False, "Device cancelled the XMODEM upload.")
        else:
            logger.debug("Ignoring XMODEM control %s during upload", control)

        return control_to_send, payload_to_send, crc_to_send, seq_to_send

    # ---------------------------------------------------------------------
    # Core primitives
    # ---------------------------------------------------------------------
    @staticmethod
    def _crc16_ccitt(data: bytes) -> int:
        crc16 = 0
        for byte in data:
            crc16 = ((crc16 >> 8) & 0xFF) | ((crc16 << 8) & 0xFFFF)
            crc16 ^= byte
            crc16 ^= (crc16 & 0xFF) >> 4
            crc16 ^= (crc16 << 8) << 4
            crc16 ^= ((crc16 & 0xFF) << 4) << 1
            crc16 &= 0xFFFF
        return crc16

    def _send_xmodem_control(
        self,
        control: xmodem_pb2.XModem.Control.ValueType,
        seq: int = 0,
        payload: bytes = b"",
        crc16: Optional[int] = None,
    ) -> None:
        message = mesh_pb2.ToRadio()
        packet = message.xmodemPacket
        packet.control = control
        packet.seq = seq
        if payload:
            packet.buffer = payload
        if crc16 is not None:
            packet.crc16 = crc16
        self._mesh._sendToRadio(message)

    def _send_xmodem_request(self, node_src: str) -> None:
        request = mesh_pb2.ToRadio()
        packet = request.xmodemPacket
        packet.control = xmodem_pb2.XModem.Control.STX
        packet.seq = 0
        packet.buffer = node_src.encode("utf-8")
        self._mesh._sendToRadio(request)

    def _start_upload(self, remote_path: str) -> None:
        request = mesh_pb2.ToRadio()
        packet = request.xmodemPacket
        packet.control = xmodem_pb2.XModem.Control.SOH
        packet.seq = 0
        packet.buffer = remote_path.encode("utf-8")
        self._mesh._sendToRadio(request)

    def _delete_remote_file(self, remote_path: str) -> None:
        if not remote_path:
            return
        try:
            self._mesh.localNode.ensureSessionKey()
        except Exception:
            logger.debug("Unable to ensure admin session key for delete operation")
        try:
            admin_msg = admin_pb2.AdminMessage()
            admin_msg.delete_file_request = remote_path
            # Fire-and-forget, we do not need a response here.
            self._mesh.localNode._sendAdmin(admin_msg, wantResponse=False)
        except Exception as ex:
            logger.debug(f"Failed to delete remote file {remote_path}: {ex}")

    def _complete_xmodem_locked(self, success: bool, error: Optional[str] = None) -> None:
        state = self._xmodem_state
        if not state or state.get("done"):
            return
        file_handle = state.get("file")
        if file_handle and not state.get("closed"):
            flush_fn = getattr(file_handle, "flush", None)
            if callable(flush_fn):
                try:
                    flush_fn()
                except Exception:
                    pass
            try:
                file_handle.close()
            except Exception:
                pass
            state["closed"] = True
        state["success"] = success
        state["error"] = error
        state["done"] = True
        mode = state.get("mode")
        if mode == "download":
            state["remove_local_on_fail"] = not success
        elif mode == "upload":
            state["delete_remote_on_fail"] = not success
        state["event"].set()

    def _cleanup_xmodem_state_locked(self, remove_partial: bool = False) -> Optional[str]:
        state = self._xmodem_state
        if not state:
            return None
        file_handle = state.get("file")
        if file_handle and not state.get("closed"):
            try:
                file_handle.close()
            except Exception:
                pass
            state["closed"] = True
        remote_cleanup: Optional[str] = None
        mode = state.get("mode")
        path = state.get("path")
        self._xmodem_state = None
        if remove_partial:
            if mode == "download" and path:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception as ex:
                    logger.debug(f"Failed to remove partial download {path}: {ex}")
            elif mode == "upload":
                if state.get("delete_remote_on_fail"):
                    remote_cleanup = state.get("remote_path")
        return remote_cleanup

