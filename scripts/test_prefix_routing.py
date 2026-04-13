#!/usr/bin/env python3
"""
Round-trip XModem tests for firmware path prefixes /__int__/ and /__ext__/.

After each successful upload+download round-trip, the harness runs ``listDir``
(MFLIST) on the parent directory and checks that the test file path appears in
the listing (requires firmware with MFLIST support). Use ``--skip-listdir`` to
disable that step (e.g. older firmware).

Run one device at a time: connect only the target radio, then pass --device and
either --port (serial) or --host (TCP). Do not rely on auto port discovery.

Examples:
  python scripts/test_prefix_routing.py --device tdeck --port /dev/ttyUSB0
  python scripts/test_prefix_routing.py --device tdeck --port /dev/ttyUSB0 --trace-xmodem --verbose
  python scripts/test_prefix_routing.py --device rak4631 --port COM5
  python scripts/test_prefix_routing.py --device techo --host 192.168.1.50

Run all suites in order (pauses for you to swap USB between devices):
  python scripts/test_prefix_routing.py --all --port /dev/ttyACM0 --pause-between

Device firmware logs on the same USB link (no second serial client):
  python scripts/test_prefix_routing.py --device tdeck --port /dev/ttyUSB0 --device-log
  Requires the node setting security.debug_log_api_enabled (enable once in the app / admin).

Failure triage (for firmware fixes):
  - Path mount / fsRoute / extFS init issues -> branch nrf-external-flash
  - XModem state (truncate, ACK/NAK, wrong path on remove) -> branch xmodem-external-flash

If OPEN hangs, the device is not returning an xmodem frame on the wire (meshtastic-python retries
up to 10 times per step). Default per-try timeout is short so a dead link fails fast; raise it on
noisy links: `--xmodem-timeout 15`. Use `--verbose` for DEBUG lines from uploadFile/downloadFile.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import json
import os
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Literal

# meshtastic-python repo root (parent of `meshtastic/` package)
_PY_ROOT = Path(__file__).resolve().parent.parent
if str(_PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_PY_ROOT))

from meshtastic.serial_interface import SerialInterface  # noqa: E402
from meshtastic.tcp_interface import TCPInterface  # noqa: E402

DeviceId = Literal["tdeck", "rak4631", "techo"]

DEVICE_ORDER: tuple[DeviceId, ...] = ("tdeck", "rak4631", "techo")

DEVICE_LABELS: dict[DeviceId, str] = {
    "tdeck": "LilyGO T-Deck",
    "rak4631": "RAK4631 (stock / no ext LittleFS mount)",
    "techo": "T-Echo (external QSPI LittleFS when enabled in firmware)",
}


@dataclass
class StepResult:
    device: str
    prefix: str
    direction: str
    device_path: str
    bytes_count: int
    sha256_expected: str
    sha256_got: str
    duration_s: float
    ok: bool
    error: str | None = None


@dataclass
class ListStepResult:
    """Result of verifying an upload via MFLIST ``listDir`` on the parent directory."""

    device: str
    prefix: str
    dir_path: str
    expect_path: str
    row_count: int
    duration_s: float
    ok: bool
    error: str | None = None


@dataclass
class SuiteResult:
    device: str
    ok: bool
    steps: list[StepResult]
    list_steps: list[ListStepResult] = field(default_factory=list)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_payload(size: int, seed: int = 0x4D455348) -> bytes:
    """Deterministic pseudo-random payload (repeatable across runs)."""
    out = bytearray(size)
    state = seed & 0xFFFFFFFF
    for i in range(size):
        # LCG
        state = (1103515245 * state + 12345) & 0xFFFFFFFF
        out[i] = state & 0xFF
    return bytes(out)


def _device_paths(device: DeviceId) -> tuple[str, str]:
    base = f"/__int__/meshforge-test/{device}/int.bin"
    ext = f"/__ext__/meshforge-test/{device}/ext.bin"
    return base, ext


def _prompt(msg: str, skip: bool) -> None:
    if skip:
        print(f"[non-interactive] {msg}")
        return
    try:
        input(f"{msg}\nPress Enter to continue… ")
    except EOFError:
        print("(EOF — continuing)")


def _connect_heartbeat(stop: threading.Event) -> None:
    """Print every few seconds until stop is set (covers SerialInterface waitForConfig)."""
    elapsed = 0
    interval = 3.0
    while not stop.wait(timeout=interval):
        elapsed += int(interval)
        print(
            f"  … API handshake still running (~{elapsed}s) — normal on slow USB / large nodedb; "
            "try --verbose for library DEBUG",
            flush=True,
        )


def _open_interface(
    port: str | None,
    host: str | None,
    tcp_port: int,
    timeout: int,
    *,
    device_log: bool = False,
) -> SerialInterface | TCPInterface:
    if port and host:
        raise SystemExit("Use only one of --port or --host.")
    if not port and not host:
        raise SystemExit(
            "You must specify exactly one transport: --port SERIAL or --host HOST.\n"
            "Auto port scan is disabled for this harness so the wrong device is never touched."
        )
    # Routes FromRadio.log_record -> meshtastic.log.line -> stdout (needs debug_log_api_enabled on device).
    dbg = sys.stdout if device_log else None
    if host:
        return TCPInterface(hostname=host, portNumber=tcp_port, timeout=timeout, debugOut=dbg)
    return SerialInterface(devPath=port, timeout=timeout, debugOut=dbg)


def _run_prefix_roundtrip(
    iface: Any,
    device: DeviceId,
    prefix_name: str,
    device_path: str,
    payload: bytes,
    timeout_s: float,
) -> StepResult:
    node = iface.localNode
    expected = _sha256(payload)
    t0 = time.perf_counter()

    tmp_up = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
    tmp_up.close()
    tmp_down = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
    tmp_down.close()
    try:
        with open(tmp_up.name, "wb") as f:
            f.write(payload)

        print(
            f"  (upload OPEN: meshtastic-python waits up to {timeout_s:g}s per try, max 10 tries — not frozen)",
            flush=True,
        )
        ok_up = node.uploadFile(tmp_up.name, device_path, timeout_s=timeout_s)
        if not ok_up:
            return StepResult(
                device=device,
                prefix=prefix_name,
                direction="upload",
                device_path=device_path,
                bytes_count=len(payload),
                sha256_expected=expected,
                sha256_got="",
                duration_s=time.perf_counter() - t0,
                ok=False,
                error="uploadFile returned False",
            )

        ok_down = node.downloadFile(device_path, tmp_down.name, timeout_s=timeout_s)
        if not ok_down:
            return StepResult(
                device=device,
                prefix=prefix_name,
                direction="download",
                device_path=device_path,
                bytes_count=len(payload),
                sha256_expected=expected,
                sha256_got="",
                duration_s=time.perf_counter() - t0,
                ok=False,
                error="downloadFile returned False",
            )

        with open(tmp_down.name, "rb") as f:
            got = f.read()
        got_hash = _sha256(got)
        if got != payload:
            return StepResult(
                device=device,
                prefix=prefix_name,
                direction="verify",
                device_path=device_path,
                bytes_count=len(payload),
                sha256_expected=expected,
                sha256_got=got_hash,
                duration_s=time.perf_counter() - t0,
                ok=False,
                error=f"size local={len(payload)} got={len(got)}",
            )

        return StepResult(
            device=device,
            prefix=prefix_name,
            direction="roundtrip",
            device_path=device_path,
            bytes_count=len(payload),
            sha256_expected=expected,
            sha256_got=got_hash,
            duration_s=time.perf_counter() - t0,
            ok=True,
            error=None,
        )
    finally:
        for p in (tmp_up.name, tmp_down.name):
            try:
                os.unlink(p)
            except OSError:
                pass


def _run_listdir_check(
    iface: Any,
    device: DeviceId,
    prefix_name: str,
    dir_path: str,
    expect_path: str,
    timeout_s: float,
) -> ListStepResult:
    """Confirm ``expect_path`` appears in ``listDir(dir_path, depth=0)``."""
    t0 = time.perf_counter()
    node = iface.localNode
    rows = node.listDir(dir_path, depth=0, timeout_s=timeout_s)
    dt = time.perf_counter() - t0
    if rows is None:
        return ListStepResult(
            device=device,
            prefix=prefix_name,
            dir_path=dir_path,
            expect_path=expect_path,
            row_count=0,
            duration_s=dt,
            ok=False,
            error="listDir returned None (NAK, timeout, or firmware without MFLIST)",
        )
    paths = [p for p, _ in rows]
    if expect_path in paths:
        return ListStepResult(
            device=device,
            prefix=prefix_name,
            dir_path=dir_path,
            expect_path=expect_path,
            row_count=len(rows),
            duration_s=dt,
            ok=True,
            error=None,
        )
    base = Path(expect_path).name
    matched = [p for p in paths if p.rstrip("/").endswith("/" + base) or p.rstrip("/").endswith(base)]
    if matched:
        return ListStepResult(
            device=device,
            prefix=prefix_name,
            dir_path=dir_path,
            expect_path=expect_path,
            row_count=len(rows),
            duration_s=dt,
            ok=True,
            error=None,
        )
    sample = paths[:12]
    return ListStepResult(
        device=device,
        prefix=prefix_name,
        dir_path=dir_path,
        expect_path=expect_path,
        row_count=len(rows),
        duration_s=dt,
        ok=False,
        error=f"expected path not in listing (sample {sample!r})",
    )


def run_suite(
    device: DeviceId,
    port: str | None,
    host: str | None,
    tcp_port: int,
    payload_size: int,
    iface_timeout: int,
    xmodem_timeout: float,
    skip_prompt: bool,
    device_log: bool = False,
    *,
    skip_listdir: bool = False,
) -> SuiteResult:
    label = DEVICE_LABELS[device]
    print("\n" + "=" * 72)
    print(f"SUITE: {device} — {label}")
    print("Connect ONLY this device for the duration of this suite.")
    _prompt(f"Ready when {label} is connected.", skip_prompt)

    print(
        "  Opening transport + Meshtastic API handshake (serial open, want_config, nodedb). "
        "This phase can take 10–40s on some boards…",
        flush=True,
    )
    if device_log:
        print(
            "  --device-log: printing device LogRecord lines to stdout (enable security.debug_log_api_enabled on the node).",
            flush=True,
        )

    iface: SerialInterface | TCPInterface | None = None
    steps: list[StepResult] = []
    list_steps: list[ListStepResult] = []
    try:
        stop_hb = threading.Event()
        hb_thread = threading.Thread(target=_connect_heartbeat, args=(stop_hb,), daemon=True)
        hb_thread.start()
        t_link = time.perf_counter()
        open_err: list[Exception] = []
        try:
            iface = _open_interface(port, host, tcp_port, iface_timeout, device_log=device_log)
        except Exception as exc:  # pylint: disable=broad-except
            open_err.append(exc)
        finally:
            stop_hb.set()
            hb_thread.join(timeout=2.0)
        link_dt = time.perf_counter() - t_link

        if open_err:
            err = f"could not open interface: {open_err[0]}"
            print(f"  FAIL  connect  ({link_dt:.1f}s)  {err}", flush=True)
            steps.append(
                StepResult(
                    device=device,
                    prefix="(none)",
                    direction="open",
                    device_path="",
                    bytes_count=0,
                    sha256_expected="(n/a)",
                    sha256_got="(n/a)",
                    duration_s=0.0,
                    ok=False,
                    error=err,
                )
            )
            print(f"\nYou may disconnect {label} now (open failed).")
            _prompt("Disconnect complete?", skip_prompt)
            return SuiteResult(device=device, ok=False, steps=steps, list_steps=list_steps)

        print(f"  Transport + handshake finished in {link_dt:.1f}s", flush=True)

        mi = getattr(iface, "myInfo", None)
        nn = getattr(mi, "my_node_num", None) if mi is not None else None
        print(f"  API session ready (my_node_num={nn!r}). Starting transfers…", flush=True)

        payload = _make_payload(payload_size)
        int_path, ext_path = _device_paths(device)
        for prefix_name, path in (("__int__", int_path), ("__ext__", ext_path)):
            print(f"\n--- {prefix_name}: {path} ({len(payload)} bytes) ---")
            r = _run_prefix_roundtrip(iface, device, prefix_name, path, payload, xmodem_timeout)
            steps.append(r)
            status = "PASS" if r.ok else "FAIL"
            print(f"  {status}  {r.direction}  {r.duration_s:.2f}s  sha256={r.sha256_expected[:16]}…")
            if not r.ok:
                print(f"  error: {r.error}")
            elif not skip_listdir:
                parent = str(Path(path).parent)
                print(f"  listDir: {parent} (expect {path!r})", flush=True)
                lr = _run_listdir_check(iface, device, prefix_name, parent, path, xmodem_timeout)
                list_steps.append(lr)
                ls = "PASS" if lr.ok else "FAIL"
                print(f"  {ls}  listDir  {lr.duration_s:.2f}s  rows={lr.row_count}", flush=True)
                if not lr.ok:
                    print(f"  error: {lr.error}", flush=True)
    finally:
        if iface is not None:
            try:
                iface.close()
            except Exception:  # pylint: disable=broad-except
                pass

    print(f"\nYou may disconnect {label} now.")
    _prompt("Disconnect complete?", skip_prompt)

    suite_ok = all(s.ok for s in steps) and all(s.ok for s in list_steps)
    return SuiteResult(device=device, ok=suite_ok, steps=steps, list_steps=list_steps)


# ── Optional XModem round-trip tracing (monkeypatch Node._xmodem_roundtrip) ───

_trace_xmodem_installed = False
_orig_node_xmodem_roundtrip: Any = None


def install_xmodem_trace() -> None:
    """Print each XModem ToRadio send and FromRadio response (or timeout)."""
    global _trace_xmodem_installed, _orig_node_xmodem_roundtrip
    if _trace_xmodem_installed:
        return
    from meshtastic.node import Node

    _orig_node_xmodem_roundtrip = Node._xmodem_roundtrip

    def _wrapped(self: Any, xm: Any, timeout_s: float = Node._XMODEM_TIMEOUT_S) -> Any:
        t0 = time.perf_counter()
        bl = len(xm.buffer) if xm.buffer else 0
        preview = (bytes(xm.buffer)[: min(72, bl)] if bl else b"").decode("utf-8", errors="replace")
        print(
            f"  [xmodem] tx control={int(xm.control)} seq={int(xm.seq)} buf_len={bl} "
            f"timeout={timeout_s:g}s preview={preview!r}",
            flush=True,
        )
        assert _orig_node_xmodem_roundtrip is not None
        resp = _orig_node_xmodem_roundtrip(self, xm, timeout_s)
        dt = time.perf_counter() - t0
        if resp is None:
            print(f"  [xmodem] rx (no response) after {dt:.2f}s", flush=True)
        else:
            br = len(resp.buffer) if resp.buffer else 0
            print(
                f"  [xmodem] rx control={int(resp.control)} seq={int(resp.seq)} buf_len={br} ({dt:.2f}s)",
                flush=True,
            )
        return resp

    Node._xmodem_roundtrip = _wrapped  # type: ignore[method-assign]
    _trace_xmodem_installed = True


def uninstall_xmodem_trace() -> None:
    global _trace_xmodem_installed, _orig_node_xmodem_roundtrip
    if not _trace_xmodem_installed or _orig_node_xmodem_roundtrip is None:
        return
    from meshtastic.node import Node

    Node._xmodem_roundtrip = _orig_node_xmodem_roundtrip  # type: ignore[method-assign]
    _orig_node_xmodem_roundtrip = None
    _trace_xmodem_installed = False


def _emit_json(results: list[SuiteResult]) -> None:
    def ser(obj: Any) -> Any:
        if isinstance(obj, StepResult):
            return asdict(obj)
        if isinstance(obj, ListStepResult):
            return asdict(obj)
        if isinstance(obj, SuiteResult):
            return {
                "device": obj.device,
                "ok": obj.ok,
                "steps": [asdict(s) for s in obj.steps],
                "list_steps": [asdict(s) for s in obj.list_steps],
            }
        raise TypeError(type(obj))

    print(json.dumps([ser(r) for r in results], indent=2))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--device",
        choices=("tdeck", "rak4631", "techo"),
        help="Which device-specific suite to run (one physical radio at a time).",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Run tdeck, then rak4631, then techo in order. Use --pause-between to swap USB between suites.",
    )
    p.add_argument("--port", help="Serial device path (e.g. /dev/ttyACM0). Mutually exclusive with --host.")
    p.add_argument("--host", help="TCP hostname or IP for meshtasticd / TCP bridge.")
    p.add_argument("--tcp-port", type=int, default=4403, help="TCP port when using --host (default 4403).")
    p.add_argument("--size", type=int, default=384, help="Payload size in bytes (default 384 = 3 xmodem chunks).")
    p.add_argument("--iface-timeout", type=int, default=300, help="StreamInterface timeout seconds (default 300).")
    p.add_argument(
        "--xmodem-timeout",
        type=float,
        default=4.0,
        help="Per-call XModem timeout for uploadFile/downloadFile (default 4; increase on flaky USB).",
    )
    p.add_argument(
        "--pause-between",
        action="store_true",
        help="With --all: pause for Enter between device suites (recommended when swapping USB).",
    )
    p.add_argument(
        "--skip-prompt",
        action="store_true",
        help="Non-interactive: print prompts but do not wait for Enter.",
    )
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON summary at end.")
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging for meshtastic.* (serial, mesh, node, xmodem retries).",
    )
    p.add_argument(
        "--trace-xmodem",
        action="store_true",
        help="Print every XModem round-trip (tx control/seq, rx or timeout). Implies progress during OPEN.",
    )
    p.add_argument(
        "--device-log",
        action="store_true",
        help="Print device firmware logs on stdout over the same API link (needs security.debug_log_api_enabled on the node).",
    )
    p.add_argument(
        "--skip-listdir",
        action="store_true",
        help="Do not run MFLIST listDir checks after each successful round-trip (older firmware without MFLIST).",
    )

    args = p.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
        for _logname in (
            "meshtastic",
            "meshtastic.node",
            "meshtastic.mesh_interface",
            "meshtastic.stream_interface",
            "meshtastic.serial_interface",
        ):
            logging.getLogger(_logname).setLevel(logging.DEBUG)
    if args.all and args.device:
        p.error("Do not pass --device together with --all.")
    if not args.all and not args.device:
        p.error("Pass --device <id> or use --all.")
    if bool(args.port) == bool(args.host):
        p.error("Specify exactly one of --port SERIAL or --host HOST (not both, not neither).")

    if args.size < 1:
        p.error("--size must be >= 1")

    devices: tuple[DeviceId, ...] = DEVICE_ORDER if args.all else (args.device,)  # type: ignore[assignment]

    print("Prefix routing XModem harness")
    print("  Transport:", "--host " + args.host if args.host else "--port " + (args.port or ""))
    print("  Payload size:", args.size, "bytes")
    if args.trace_xmodem:
        print("  --trace-xmodem: printing each XModem tx/rx line", flush=True)
    if args.device_log:
        print("  --device-log: firmware LogRecord -> stdout (same USB session)", flush=True)
    if args.skip_listdir:
        print("  --skip-listdir: MFLIST verification disabled", flush=True)

    if args.trace_xmodem:
        install_xmodem_trace()
    try:
        results: list[SuiteResult] = []
        for i, dev in enumerate(devices):
            if args.all and i > 0 and args.pause_between and not args.skip_prompt:
                _prompt(f"Swap USB: next suite is `{dev}` ({DEVICE_LABELS[dev]}).", args.skip_prompt)
            r = run_suite(
                device=dev,
                port=args.port,
                host=args.host,
                tcp_port=args.tcp_port,
                payload_size=args.size,
                iface_timeout=args.iface_timeout,
                xmodem_timeout=args.xmodem_timeout,
                skip_prompt=args.skip_prompt,
                device_log=args.device_log,
                skip_listdir=args.skip_listdir,
            )
            results.append(r)
            line = "PASS" if r.ok else "FAIL"
            print(f"\n>>> {dev}: {line} <<<")

        if args.json:
            _emit_json(results)

        print("\n" + "=" * 72)
        print("SUMMARY (copy/paste)")
        for r in results:
            extra = ""
            if r.list_steps:
                bad = [x for x in r.list_steps if not x.ok]
                extra = f"  listDir: {len(r.list_steps)} step(s)" + (f", {len(bad)} FAIL" if bad else " OK")
            print(f"  {r.device}: {'PASS' if r.ok else 'FAIL'}{extra}")
        any_fail = any(not r.ok for r in results)
        if any_fail:
            print("\nTriage:")
            print("  FS routing / extFS / mount -> nrf-external-flash")
            print("  XModem truncate / ACK path / wrong remove path -> xmodem-external-flash")
        return 1 if any_fail else 0
    finally:
        if args.trace_xmodem:
            uninstall_xmodem_trace()


# ── Unit tests (no device): `pytest scripts/test_prefix_routing.py -q` from repo root ──


def test_run_listdir_check_exact_path():
    from unittest.mock import MagicMock

    node = MagicMock()
    node.listDir.return_value = [("/__int__/meshforge-test/tdeck/int.bin", 10)]
    iface = MagicMock()
    iface.localNode = node
    r = _run_listdir_check(
        iface,
        "tdeck",
        "__int__",
        "/__int__/meshforge-test/tdeck",
        "/__int__/meshforge-test/tdeck/int.bin",
        1.0,
    )
    assert r.ok is True
    assert r.row_count == 1
    assert r.error is None
    node.listDir.assert_called_once_with("/__int__/meshforge-test/tdeck", depth=0, timeout_s=1.0)


def test_run_listdir_check_basename_fallback():
    from unittest.mock import MagicMock

    node = MagicMock()
    # Listed path differs from expected full virtual path but same basename — still accepted
    node.listDir.return_value = [("/some/other/prefix/ext.bin", 10)]
    iface = MagicMock()
    iface.localNode = node
    r = _run_listdir_check(
        iface,
        "techo",
        "__ext__",
        "/__ext__/meshforge-test/techo",
        "/__ext__/meshforge-test/techo/ext.bin",
        2.0,
    )
    assert r.ok is True


def test_run_listdir_check_fails_when_path_missing():
    from unittest.mock import MagicMock

    node = MagicMock()
    node.listDir.return_value = [("/other/file.bin", 5)]
    iface = MagicMock()
    iface.localNode = node
    r = _run_listdir_check(
        iface,
        "tdeck",
        "__ext__",
        "/__ext__/meshforge-test/tdeck",
        "/__ext__/meshforge-test/tdeck/ext.bin",
        1.0,
    )
    assert r.ok is False
    assert r.error is not None
    assert r.row_count == 1


def test_run_listdir_check_none_from_node():
    from unittest.mock import MagicMock

    node = MagicMock()
    node.listDir.return_value = None
    iface = MagicMock()
    iface.localNode = node
    r = _run_listdir_check(iface, "rak4631", "__ext__", "/__ext__/x", "/__ext__/x/y.bin", 0.5)
    assert r.ok is False
    assert "None" in (r.error or "")


def test_emit_json_includes_list_steps():
    sr = SuiteResult(
        device="tdeck",
        ok=True,
        steps=[
            StepResult(
                device="tdeck",
                prefix="__int__",
                direction="roundtrip",
                device_path="/p",
                bytes_count=1,
                sha256_expected="a",
                sha256_got="a",
                duration_s=0.1,
                ok=True,
            )
        ],
        list_steps=[
            ListStepResult(
                device="tdeck",
                prefix="__int__",
                dir_path="/",
                expect_path="/p",
                row_count=3,
                duration_s=0.05,
                ok=True,
            )
        ],
    )
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _emit_json([sr])
    out = json.loads(buf.getvalue())
    assert len(out) == 1
    assert "list_steps" in out[0]
    assert len(out[0]["list_steps"]) == 1
    assert out[0]["list_steps"][0]["expect_path"] == "/p"


if __name__ == "__main__":
    raise SystemExit(main())
