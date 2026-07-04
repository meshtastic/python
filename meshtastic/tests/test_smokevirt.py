"""Meshtastic smoke tests with a single virtual device via localhost.

These tests run against a real ``meshtasticd`` instance in simulator mode,
managed by the function-scoped ``firmware_node`` fixture (see conftest.py).
The function scope gives every test a freshly-erased node, so destructive
commands (factory reset, channel mutations) are safe and order-independent.

Strategy
--------
* ``cli_then_verify(port, args, verifier)`` runs a CLI mutation, then opens
  a fresh ``TCPInterface`` and passes it to *verifier* which reads the real
  firmware state back through the Python library. Assertions target the
  protobuf-backed localConfig / channel objects, so they don't break when
  the CLI's stdout wording changes.
* Display-format tests (``--info``, ``--nodes``, ``--debug``, ``--qr``,
  ``--seriallog``) intentionally assert against stdout — that's what they
  actually test.
* Error paths are collapsed into parameterized tests.
"""
from __future__ import annotations

import base64
import re
import time

import pytest

from meshtastic.protobuf import channel_pb2, config_pb2

from .fw_helpers import (
    PAUSE_AFTER_CLI,
    cli_then_verify,
    run_cli,
)

# Some channel mutations cause the firmware to reboot internally. The
# platform doesn't *actually* reboot in sim mode, but we still give it a
# beat to commit the write back to disk before reconnecting.
PAUSE_AFTER_REBOOT = 1.0


# ---------------------------------------------------------------------------
# Section 1: Read-only / display tests (stdout assertions)
# ---------------------------------------------------------------------------

@pytest.mark.smokevirt
def test_smokevirt_info(firmware_node):
    """--info connects and prints the standard summary sections."""
    rc, out = run_cli(firmware_node.port, "--info")
    assert rc == 0, out
    assert re.search(r"Connected to radio", out)
    assert re.search(r"Owner:", out)
    assert re.search(r"My info:", out)
    assert re.search(r"Nodes in mesh:", out)
    assert re.search(r"Preferences:", out)


@pytest.mark.smokevirt
def test_smokevirt_debug(firmware_node):
    """--info --debug should include DEBUG log lines."""
    rc, out = run_cli(firmware_node.port, "--info", "--debug")
    assert rc == 0, out
    assert re.search(r"DEBUG file", out), out


@pytest.mark.smokevirt
def test_smokevirt_nodes(firmware_node):
    """--nodes prints a node table containing the local node."""
    rc, out = run_cli(firmware_node.port, "--nodes")
    assert rc == 0, out
    assert re.search(r"Connected to radio", out)
    # The local node shows up as the only entry on a single-node sim.
    assert re.search(r"(?i)user|name", out)


@pytest.mark.smokevirt
def test_smokevirt_qr(firmware_node):
    """--qr prints a non-empty ANSI QR code on stdout."""
    rc, out = run_cli(firmware_node.port, "--qr")
    assert rc == 0, out
    assert len(out) > 500, f"QR output too short ({len(out)} bytes)"


@pytest.mark.smokevirt
def test_smokevirt_seriallog(firmware_node, tmp_path):
    """--seriallog FILE should write a serial log file."""
    log_path = tmp_path / "serial.log"
    rc, _ = run_cli(
        firmware_node.port, "--info", "--seriallog", str(log_path)
    )
    assert rc == 0
    assert log_path.exists()


@pytest.mark.smokevirt
def test_smokevirt_test_requires_two_devices(firmware_node):
    """--test with a single device fails cleanly."""
    rc, out = run_cli(firmware_node.port, "--test")
    assert rc != 0, out
    assert re.search(r"(?i)at least two devices", out)


# ---------------------------------------------------------------------------
# Section 2: Error paths (parameterized)
# ---------------------------------------------------------------------------

_INVALID_SETTING_CASES = [
    pytest.param(("--get", "a_bad_setting"), id="get"),
    pytest.param(("--set", "a_bad_setting", "foo"), id="set"),
    pytest.param(
        ("--ch-set", "invalid_setting", "foo", "--ch-index", "0"),
        id="ch-set",
    ),
]


@pytest.mark.smokevirt
@pytest.mark.parametrize("args", _INVALID_SETTING_CASES)
def test_smokevirt_invalid_setting(firmware_node, args):
    """Invalid --get/--set/--ch-set should print available choices."""
    rc, out = run_cli(firmware_node.port, *args)
    assert rc == 0, out
    assert re.search(r"Choices are", out), out


_PRIMARY_CHANNEL_GUARD_CASES = [
    pytest.param(("--ch-del", "--ch-index", "0"), id="ch-del"),
    pytest.param(("--ch-disable", "--ch-index", "0"), id="ch-disable"),
    pytest.param(("--ch-enable", "--ch-index", "0"), id="ch-enable"),
]


@pytest.mark.smokevirt
@pytest.mark.parametrize("args", _PRIMARY_CHANNEL_GUARD_CASES)
def test_smokevirt_primary_channel_guard(firmware_node, args):
    """Cannot delete/disable/enable the PRIMARY channel."""
    rc, out = run_cli(firmware_node.port, *args)
    assert rc != 0, out
    assert re.search(r"(?i)cannot (delete|enable|disable)(.*primary)?", out), out


# ---------------------------------------------------------------------------
# Section 3: State-mutation tests (CLI mutates, library verifies)
# ---------------------------------------------------------------------------

# --- Owner -----------------------------------------------------------------

def _long_name(iface):
    user = iface.getMyUser()
    return user["longName"] if isinstance(user, dict) else user.long_name


def _short_name(iface):
    user = iface.getMyUser()
    return user["shortName"] if isinstance(user, dict) else user.short_name


def _assert_long_name(iface, expected):
    actual = _long_name(iface)
    assert actual == expected, f"longName: {actual!r} != {expected!r}"


def _assert_short_name(iface, expected):
    actual = _short_name(iface)
    assert actual == expected, f"shortName: {actual!r} != {expected!r}"


@pytest.mark.smokevirt
def test_smokevirt_set_owner(firmware_node):
    """--set-owner changes longName persistently."""
    cli_then_verify(
        firmware_node.port,
        ["--set-owner", "Alice Meshtastic"],
        lambda iface: _assert_long_name(iface, "Alice Meshtastic"),
    )


@pytest.mark.smokevirt
def test_smokevirt_set_owner_short(firmware_node):
    """--set-owner-short updates the shortName persistently."""
    cli_then_verify(
        firmware_node.port,
        ["--set-owner-short", "ALI"],
        lambda iface: _assert_short_name(iface, "ALI"),
    )


# --- Position --------------------------------------------------------------

@pytest.mark.smokevirt
def test_smokevirt_set_location(firmware_node):
    """--setlat/--setlon/--setalt persist a fixed position."""
    def check(iface):
        info = iface.getMyNodeInfo()
        pos = info.get("position", {}) or {}
        assert abs(float(pos.get("latitude", 0)) - 32.7767) < 1e-3, pos
        assert abs(float(pos.get("longitude", 0)) - (-96.7970)) < 1e-3, pos
        assert int(pos.get("altitude", 0)) == 1337, pos

    cli_then_verify(
        firmware_node.port,
        ["--setlat", "32.7767", "--setlon", "-96.7970", "--setalt", "1337"],
        check,
    )


@pytest.mark.smokevirt
def test_smokevirt_remove_position(firmware_node):
    """--remove-position clears any fixed position."""
    run_cli(
        firmware_node.port,
        "--setlat", "10", "--setlon", "20", "--setalt", "30",
    )
    time.sleep(PAUSE_AFTER_CLI)

    def check(iface):
        info = iface.getMyNodeInfo()
        pos = info.get("position", {}) or {}
        # After remove, position should be empty or zero-lat/lon.
        assert "latitude" not in pos or float(pos.get("latitude", 0)) == 0, pos

    cli_then_verify(
        firmware_node.port,
        ["--remove-position"],
        check,
    )


# --- Channels --------------------------------------------------------------

def _channel(iface, idx):
    return iface.localNode.getChannelByChannelIndex(idx)


def _assert_channel_role(iface, idx, expected_role):
    ch = _channel(iface, idx)
    assert ch is not None, f"channel {idx} missing"
    assert ch.role == expected_role, (
        f"channel {idx} role: {channel_pb2.Channel.Role.Name(ch.role)} "
        f"!= {channel_pb2.Channel.Role.Name(expected_role)}"
    )


def _set_and_verify(port, args, verifier, expect_rc=0):
    """Run CLI, optional reboot pause, verify via fresh interface."""
    cli_then_verify(port, list(args), verifier, expect_rc=expect_rc)


@pytest.mark.smokevirt
def test_smokevirt_ch_set_name(firmware_node):
    """--ch-set name on ch-index 0 persists."""
    def check(iface):
        ch = _channel(iface, 0)
        assert ch is not None
        assert ch.settings.name == "MyChannel", ch

    cli_then_verify(
        firmware_node.port,
        ["--ch-set", "name", "MyChannel", "--ch-index", "0"],
        check,
    )


_CH_PRESETS = [
    ("--ch-longslow", config_pb2.Config.LoRaConfig.ModemPreset.LONG_SLOW),
    ("--ch-longfast", config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST),
    ("--ch-medslow", config_pb2.Config.LoRaConfig.ModemPreset.MEDIUM_SLOW),
    ("--ch-medfast", config_pb2.Config.LoRaConfig.ModemPreset.MEDIUM_FAST),
    ("--ch-shortslow", config_pb2.Config.LoRaConfig.ModemPreset.SHORT_SLOW),
    ("--ch-shortfast", config_pb2.Config.LoRaConfig.ModemPreset.SHORT_FAST),
]


@pytest.mark.smokevirt
@pytest.mark.parametrize("flag,expected_preset", _CH_PRESETS)
def test_smokevirt_ch_preset(firmware_node, flag, expected_preset):
    """Each channel preset sets the LoRa modem_preset config value."""
    def check(iface):
        actual = iface.localNode.localConfig.lora.modem_preset
        assert actual == expected_preset, (
            f"modem_preset: {config_pb2.Config.LoRaConfig.ModemPreset.Name(actual)} "
            f"!= {config_pb2.Config.LoRaConfig.ModemPreset.Name(expected_preset)}"
        )

    cli_then_verify(firmware_node.port, [flag], check)


@pytest.mark.smokevirt
def test_smokevirt_ch_set_downlink_uplink(firmware_node):
    """--ch-set downlink_enabled/uplink_enabled flips both flags."""
    def check_disabled(iface):
        ch = _channel(iface, 0)
        assert ch is not None
        assert ch.settings.downlink_enabled is False, ch
        assert ch.settings.uplink_enabled is False, ch

    cli_then_verify(
        firmware_node.port,
        [
            "--ch-set", "downlink_enabled", "false",
            "--ch-set", "uplink_enabled", "false",
            "--ch-index", "0",
        ],
        check_disabled,
    )

    def check_enabled(iface):
        ch = _channel(iface, 0)
        assert ch is not None
        assert ch.settings.downlink_enabled is True, ch
        assert ch.settings.uplink_enabled is True, ch

    cli_then_verify(
        firmware_node.port,
        [
            "--ch-set", "downlink_enabled", "true",
            "--ch-set", "uplink_enabled", "true",
            "--ch-index", "0",
        ],
        check_enabled,
    )


@pytest.mark.smokevirt
def test_smokevirt_ch_add_then_del(firmware_node):
    """--ch-add creates a SECONDARY channel; --ch-del removes it."""
    # Clean slate: ensure channel 1 is disabled.
    run_cli(firmware_node.port, "--ch-disable", "--ch-index", "1")
    time.sleep(PAUSE_AFTER_REBOOT)

    def check_added(iface):
        ch = _channel(iface, 1)
        assert ch is not None, "secondary channel missing after --ch-add"
        assert ch.role == channel_pb2.Channel.Role.SECONDARY, ch
        assert ch.settings.name == "testing", ch

    cli_then_verify(
        firmware_node.port,
        ["--ch-add", "testing"],
        check_added,
    )

    def check_deleted(iface):
        ch = _channel(iface, 1)
        assert ch is None or ch.role == channel_pb2.Channel.Role.DISABLED, (
            f"channel 1 still present after --ch-del: role={ch.role}"
        )

    cli_then_verify(
        firmware_node.port,
        ["--ch-del", "--ch-index", "1"],
        check_deleted,
    )


@pytest.mark.smokevirt
def test_smokevirt_ch_enable_disable(firmware_node):
    """--ch-disable and --ch-enable toggle a secondary channel's role."""
    # Start clean: ensure channel 1 is disabled.
    run_cli(firmware_node.port, "--ch-disable", "--ch-index", "1")
    time.sleep(PAUSE_AFTER_REBOOT)
    run_cli(firmware_node.port, "--ch-add", "toggle_me")
    time.sleep(PAUSE_AFTER_REBOOT)

    def check_disabled(iface):
        _assert_channel_role(iface, 1, channel_pb2.Channel.Role.DISABLED)

    cli_then_verify(
        firmware_node.port,
        ["--ch-disable", "--ch-index", "1"],
        check_disabled,
    )

    def check_enabled(iface):
        _assert_channel_role(iface, 1, channel_pb2.Channel.Role.SECONDARY)

    cli_then_verify(
        firmware_node.port,
        ["--ch-enable", "--ch-index", "1"],
        check_enabled,
    )


@pytest.mark.smokevirt
def test_smokevirt_ch_del_needs_ch_index(firmware_node):
    """--ch-del without --ch-index should warn and exit non-zero."""
    rc, out = run_cli(firmware_node.port, "--ch-del")
    assert rc != 0, out
    assert re.search(r"(?i)need to specify|ch-index", out), out


# --- URL -------------------------------------------------------------------

@pytest.mark.smokevirt
def test_smokevirt_seturl_default(firmware_node):
    """--seturl applies a known channel URL."""
    url = "https://www.meshtastic.org/d/#CgUYAyIBAQ"

    # Use the fixture's already-connected TCPInterface so the same
    # connection handles the firmware restart after setURL.
    if firmware_node.iface is None:
        pytest.fail("fixture interface not connected")
    iface = firmware_node.iface
    iface.localNode.setURL(url)

    time.sleep(2.0)

    actual = iface.localNode.getURL()
    assert "meshtastic.org" in actual, f"not a channel URL: {actual}"
    # The firmware may reshape the URL and use slightly different base64
    # for the same data (trailing bits are ignored during decode), so we
    # decode both and compare the protobuf payload prefix rather than
    # doing a substring match on the encoded form.
    _, _, frag = actual.partition("/#")
    if not frag:
        _, _, frag = actual.rpartition("#")
    missing = len(frag) % 4
    if missing:
        frag += "=" * (4 - missing)
    actual_bytes: bytes = base64.urlsafe_b64decode(frag)

    _, _, efrag = url.partition("/#")
    missing = len(efrag) % 4
    if missing:
        efrag += "=" * (4 - missing)
    expected_bytes: bytes = base64.urlsafe_b64decode(efrag)

    assert actual_bytes.startswith(expected_bytes), (
        f"URL payload mismatch:\n"
        f"  expected (hex): {expected_bytes.hex()}\n"
        f"  actual (hex):   {actual_bytes.hex()}"
    )


@pytest.mark.smokevirt
def test_smokevirt_seturl_invalid(firmware_node):
    """--seturl with an undecodable URL fails cleanly."""
    url = (
        "https://www.meshtastic.org/c/#"
        "GAMiENTxuzogKQdZ8Lz_q89Oab8qB0RlZmF1bHQ="
    )
    rc, out = run_cli(firmware_node.port, "--seturl", url)
    assert rc != 0, out
    assert re.search(r"(?i)warning|no settings|invalid|error", out), out


# --- Configure -------------------------------------------------------------

@pytest.mark.smokevirt
def test_smokevirt_configure(firmware_node, tmp_path):
    """--configure applies an inline YAML config."""
    cfg_path = tmp_path / "test_config.yaml"
    cfg_path.write_text("""\
owner: Bob TBeam
config:
  position:
    fixed_position: true
""")

    def check(iface):
        _assert_long_name(iface, "Bob TBeam")
        assert iface.localNode.localConfig.position.fixed_position is True

    cli_then_verify(
        firmware_node.port,
        ["--configure", str(cfg_path)],
        check,
        cli_timeout=90,
    )


# --- Ham -------------------------------------------------------------------

@pytest.mark.smokevirt
def test_smokevirt_set_ham(firmware_node):
    """--set-ham sets the ham callsign as the device owner."""
    def check(iface):
        _assert_long_name(iface, "KI1234")

    cli_then_verify(
        firmware_node.port,
        ["--set-ham", "KI1234"],
        check,
    )


# --- Network config --------------------------------------------------------

_NETWORK_SET_CASES = [
    pytest.param(
        "network.wifi_ssid", "some_ssid", "network.wifi_ssid", "some_ssid",
        id="wifi_ssid",
    ),
    pytest.param(
        "network.wifi_psk", "temp1234", "network.wifi_psk", "temp1234",
        id="wifi_psk",
    ),
]


@pytest.mark.smokevirt
@pytest.mark.parametrize("cli_field,cli_value,lib_path,expected", _NETWORK_SET_CASES)
def test_smokevirt_set_network(
    firmware_node, cli_field, cli_value, lib_path, expected
):
    """--set wifi_* should persist in LocalConfig.NetworkConfig fields."""
    def check(iface):
        obj = iface.localNode.localConfig
        for part in lib_path.split("."):
            obj = getattr(obj, part)
        assert obj == expected, f"{lib_path}: {obj!r} != {expected!r}"

    cli_then_verify(
        firmware_node.port,
        ["--set", cli_field, cli_value],
        check,
    )


# --- --get valid settings --------------------------------------------------

_GET_VALID_CASES = [
    pytest.param("network.wifi_ssid", id="wifi_ssid"),
    pytest.param("lora.hop_limit", id="lora_hop_limit"),
    pytest.param("position.position_broadcast_secs", id="pos_broadcast_secs"),
]


@pytest.mark.smokevirt
@pytest.mark.parametrize("field", _GET_VALID_CASES)
def test_smokevirt_get_valid_setting(firmware_node, field):
    """--get of a known setting should print the field, rc==0."""
    rc, out = run_cli(firmware_node.port, "--get", field)
    assert rc == 0, out
    # CLI prints dotted paths as the last segment; match case-insensitively.
    short = field.rsplit(".", 1)[-1]
    assert re.search(short, out, re.IGNORECASE), out


# --- Position flags --------------------------------------------------------

_POS_FIELDS_INPUT = ["ALTITUDE", "ALTITUDE_MSL", "HEADING"]


@pytest.mark.smokevirt
def test_smokevirt_pos_fields(firmware_node):
    """--pos-fields should mount the requested bit flags in the position config."""
    def check(iface):
        flags = iface.localNode.localConfig.position.position_flags
        PosFlags = config_pb2.Config.PositionConfig.PositionFlags
        for name in _POS_FIELDS_INPUT:
            assert flags & int(PosFlags.Value(name)), (
                f"{name} bit not set in position_flags={flags:#x}"
            )

    cli_then_verify(
        firmware_node.port,
        ["--pos-fields"] + _POS_FIELDS_INPUT,
        check,
    )


# ---------------------------------------------------------------------------
# Section 4: Destructive command (factory reset)
# ---------------------------------------------------------------------------

@pytest.mark.smokevirt
def test_smokevirt_factory_reset(firmware_node):
    """--set factory_reset true returns rc=0.

    We only assert the CLI command succeeds. The node's persistent state is
    wiped by the reset and the sandboxed sim process may exit shortly
    after; the function-scoped fixture teardown handles cleaning up the
    (likely-dead) meshtasticd process.
    """
    rc, out = run_cli(firmware_node.port, "--set", "factory_reset", "true")
    assert rc == 0, out
    # The CLI prints a confirmation line before the firmware actually resets.
    assert re.search(r"(?i)factory.?reset|writing", out), out
