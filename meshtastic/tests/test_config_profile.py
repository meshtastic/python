"""Offline regression tests for configuration profile field names."""
# pylint: disable=redefined-outer-name,too-many-positional-arguments

from pathlib import Path
from typing import Any, Type
from unittest.mock import MagicMock

import pytest
import yaml
from google.protobuf.message import Message

from meshtastic import mt_config
from meshtastic.__main__ import _read_profile, export_config, getPref, main, setPref
from meshtastic.protobuf.channel_pb2 import ChannelSettings  # pylint: disable=no-name-in-module
from meshtastic.protobuf.localonly_pb2 import LocalConfig, LocalModuleConfig  # pylint: disable=no-name-in-module
from meshtastic.serial_interface import SerialInterface

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("reset_mt_config")]


@pytest.mark.parametrize("fmt", ["auto", "yaml"])
def test_shipped_configuration_example(fmt: str) -> None:
    """Load the shipped example from disk and retain its configuration sections."""
    path = Path(__file__).resolve().parents[2] / "example_config.yaml"

    profile = _read_profile(str(path), fmt)

    assert profile.long_name == "Bob TBeam"
    assert profile.config.power.ls_secs == 300
    assert profile.config.power.min_wake_secs == 10
    assert profile.config.power.sds_secs == 4294967295
    assert profile.config.lora.hop_limit == 3
    assert profile.module_config.telemetry.device_update_interval == 900


@pytest.mark.parametrize("fmt", ["auto", "yaml"])
def test_shipped_camel_case_example(fmt: str) -> None:
    """The camel-case example contains current, importable configuration."""
    path = Path(__file__).resolve().parents[2] / "exampleConfig.yaml"

    profile = _read_profile(str(path), fmt)

    assert profile.long_name == "Bob TBeam"
    assert profile.short_name == "BOB"
    assert profile.channel_url
    assert profile.config.lora.region == 1
    assert profile.config.display.screen_on_secs == 31536000


@pytest.fixture
def profile_interface() -> MagicMock:
    """Provide real protobuf configuration with a mocked radio transport."""
    iface = MagicMock(spec=SerialInterface)
    iface.localNode = MagicMock()
    iface.devPath = "offline"
    iface.getLongName.return_value = None
    iface.getShortName.return_value = None
    iface.localNode.getURL.return_value = ""
    iface.getCannedMessage.return_value = None
    iface.getRingtone.return_value = None
    iface.getMyNodeInfo.return_value = {}
    iface.localNode.localConfig = LocalConfig()
    iface.localNode.moduleConfig = LocalModuleConfig()
    iface.getNode.return_value = iface.localNode
    return iface


@pytest.mark.parametrize("camel_case", [False, True])
@pytest.mark.parametrize("fmt", ["auto", "yaml"])
def test_yaml_export_import_clock(
    tmp_path: Path, profile_interface: MagicMock, camel_case: bool, fmt: str
) -> None:
    """The CLI's own exported digit-bearing field survives profile loading."""
    mt_config.camel_case = camel_case
    profile_interface.localNode.localConfig.display.use_12h_clock = True
    exported = export_config(profile_interface)
    assert yaml.safe_load(exported)["config"]["display"]["use12hClock"] is True
    path = tmp_path / "profile.yaml"
    path.write_text(exported, encoding="utf8")

    profile = _read_profile(str(path), fmt)

    assert profile.config.display.use_12h_clock is True


@pytest.mark.parametrize("clock_name", ["use12hClock", "use_12h_clock"])
@pytest.mark.parametrize("camel_case", [False, True])
def test_configure_field_names(
    tmp_path: Path,
    profile_interface: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    clock_name: str,
    camel_case: bool,
) -> None:
    """Import canonical/JSON names through main(), retaining unspecified fields."""
    mt_config.camel_case = camel_case
    path = tmp_path / "profile.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "config": {
                    "display": {clock_name: True},
                    "network": {"ipv4Config": {"ip": 123}, "wifiEnabled": True},
                    "bluetooth": {"fixed_pin": 123456},
                    "position": {"positionFlags": "ALTITUDE,SPEED"},
                },
                "module_config": {
                    "externalNotification": {"outputMs": 321},
                    "mqtt": {"proxy_to_client_enabled": True},
                },
            }
        ),
        encoding="utf8",
    )
    local_config = profile_interface.localNode.localConfig
    local_config.display.screen_on_secs = 45
    profile_interface.localNode.moduleConfig.external_notification.enabled = True
    monkeypatch.setattr("sys.argv", ["meshtastic", "--configure", str(path)])
    monkeypatch.setattr(
        "meshtastic.serial_interface.SerialInterface",
        lambda *_, **__: profile_interface,
    )
    monkeypatch.setattr("meshtastic.__main__.time.sleep", lambda _: None)

    main()

    assert local_config.display.use_12h_clock is True
    assert local_config.display.screen_on_secs == 45
    assert local_config.network.ipv4_config.ip == 123
    assert local_config.network.wifi_enabled is True
    assert local_config.bluetooth.fixed_pin == 123456
    assert local_config.position.position_flags == 513
    module_config = profile_interface.localNode.moduleConfig
    assert module_config.external_notification.output_ms == 321
    assert module_config.external_notification.enabled is True
    assert module_config.mqtt.proxy_to_client_enabled is True
    assert profile_interface.localNode.writeConfig.call_count == 6
    profile_interface.localNode.beginSettingsTransaction.assert_called_once()
    profile_interface.localNode.commitSettingsTransaction.assert_called_once()


@pytest.mark.parametrize(
    "container,section,values,error_path",
    [
        ("config", "display", {"unknownClock": True}, "display.unknownClock"),
        ("module_config", "mqtt", {"unknownSetting": True}, "mqtt.unknownSetting"),
        ("config", "unknownSection", {}, "config.unknownSection"),
        ("module_config", "unknownSection", {}, "module_config.unknownSection"),
        (
            "config",
            "network",
            {"ipv4Config": {"unknownIp": 1}},
            "network.ipv4Config.unknownIp",
        ),
        (
            "module_config",
            "mqtt",
            {"mapReportSettings": {"unknownSetting": 1}},
            "mqtt.mapReportSettings.unknownSetting",
        ),
        ("config", "network", {"unknownNested": {}}, "network.unknownNested"),
        ("config", "display", {"use12hClock": {}}, "display.use12hClock"),
        ("config", "display", True, "display"),
        ("config", "network", {"wifiPsk": "short"}, "network.wifiPsk"),
        ("config", "lora", {"region": "UNKNOWN_REGION"}, "lora.region"),
        (
            "config",
            "position",
            {"positionFlags": "UNKNOWN_FLAG"},
            "position.positionFlags",
        ),
        ("module_config", "serial", {"mode": "UNKNOWN_MODE"}, "serial.mode"),
    ],
)
@pytest.mark.parametrize("fmt", ["auto", "yaml"])
def test_configure_rejects_invalid_assignment(
    tmp_path: Path,
    profile_interface: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    container: str,
    section: str,
    values: Any,
    error_path: str,
    fmt: str,
) -> None:
    """Invalid imports exit through the CLI error path before starting writes."""
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump({container: {section: values}}), encoding="utf8")
    monkeypatch.setattr(
        "sys.argv", ["meshtastic", "--configure", str(path), "--export-format", fmt]
    )
    monkeypatch.setattr(
        "meshtastic.serial_interface.SerialInterface",
        lambda *_, **__: profile_interface,
    )
    monkeypatch.setattr("meshtastic.__main__.time.sleep", lambda _: None)

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Aborting due to:" in out
    assert error_path in out
    profile_interface.localNode.beginSettingsTransaction.assert_not_called()
    profile_interface.localNode.writeConfig.assert_not_called()
    profile_interface.localNode.commitSettingsTransaction.assert_not_called()
    profile_interface.close.assert_called()


@pytest.mark.parametrize(
    "unknown_key", ["confg", "moduleConfig", "userPrefs", "metadata"]
)
@pytest.mark.parametrize("fmt", ["auto", "yaml"])
def test_configure_rejects_unknown_top_level_key(
    tmp_path: Path,
    profile_interface: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    unknown_key: str,
    fmt: str,
) -> None:
    """Unknown top-level keys must not silently permit a partial import."""
    path = tmp_path / "invalid.yaml"
    path.write_text(
        yaml.safe_dump({"config": {"display": {"use12hClock": True}}, unknown_key: {}}),
        encoding="utf8",
    )
    monkeypatch.setattr(
        "sys.argv", ["meshtastic", "--configure", str(path), "--export-format", fmt]
    )
    monkeypatch.setattr(
        "meshtastic.serial_interface.SerialInterface",
        lambda *_, **__: profile_interface,
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert f"Unknown configuration key: {unknown_key}" in capsys.readouterr().out
    assert profile_interface.localNode.localConfig.ListFields() == []
    profile_interface.localNode.beginSettingsTransaction.assert_not_called()
    profile_interface.localNode.writeConfig.assert_not_called()
    profile_interface.localNode.commitSettingsTransaction.assert_not_called()
    profile_interface.close.assert_called()


@pytest.mark.parametrize(
    "short_key,url_key", [("owner_short", "channel_url"), ("ownerShort", "channelUrl")]
)
def test_profile_top_level_aliases(
    tmp_path: Path, short_key: str, url_key: str
) -> None:
    """Strict top-level validation retains every supported profile setting."""
    path = tmp_path / "aliases.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "owner": "Owner",
                short_key: "OWN",
                url_key: "https://example.com/channel",
                "canned_messages": "Yes|No",
                "ringtone": "tune",
                "location": {"lat": 1, "lon": 2, "alt": 3},
                "config": {},
                "module_config": {},
            }
        ),
        encoding="utf8",
    )

    profile = _read_profile(str(path), "yaml")

    assert profile.long_name == "Owner"
    assert profile.short_name == "OWN"
    assert profile.channel_url == "https://example.com/channel"
    assert profile.canned_messages == "Yes|No"
    assert profile.ringtone == "tune"
    assert profile.fixed_position.latitude_i == 10000000
    assert profile.fixed_position.longitude_i == 20000000
    assert profile.fixed_position.altitude == 3


@pytest.mark.parametrize(
    "config_type,path,canonical,value",
    [
        (LocalConfig, "display.use12hClock", "display.use_12h_clock", True),
        (LocalConfig, "display.use_12h_clock", "display.use_12h_clock", True),
        (LocalConfig, "network.ipv4Config.ip", "network.ipv4_config.ip", 123),
        (LocalConfig, "network.ipv4_config.ip", "network.ipv4_config.ip", 123),
        (LocalConfig, "bluetooth.FixedPin", "bluetooth.fixed_pin", 123456),
        (LocalConfig, "lora.ignoreIncoming", "lora.ignore_incoming", ["1", "2"]),
        (
            LocalModuleConfig,
            "externalNotification.outputMs",
            "external_notification.output_ms",
            123,
        ),
        (
            LocalModuleConfig,
            "external_notification.output_ms",
            "external_notification.output_ms",
            123,
        ),
        (
            LocalModuleConfig,
            "mqtt.mapReportSettings.publishIntervalSecs",
            "mqtt.map_report_settings.publish_interval_secs",
            60,
        ),
        (
            LocalModuleConfig,
            "meshBeacon.broadcastOfferChannel.moduleSettings.positionPrecision",
            "mesh_beacon.broadcast_offer_channel.module_settings.position_precision",
            24,
        ),
    ],
)
def test_set_pref_names(
    config_type: Type[Message],
    path: str,
    canonical: str,
    value: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Resolve every component while retaining legacy spelling and value handling."""
    config = config_type()
    assert setPref(config, path, value) is True
    actual = config
    for part in canonical.split("."):
        actual = getattr(actual, part)
    assert actual == ([1, 2] if isinstance(value, list) else value)
    assert capsys.readouterr().out == f"Set {canonical} to {value}\n"


@pytest.mark.parametrize("camel_case", [False, True])
@pytest.mark.parametrize(
    "path",
    [
        "mqtt.mapReportSettings.publishIntervalSecs",
        "mqtt.map_report_settings.publish_interval_secs",
    ],
)
def test_set_pref_confirmation_style(
    capsys: pytest.CaptureFixture[str], path: str, camel_case: bool
) -> None:
    """Confirmation style applies to every resolved component, not the input spelling."""
    mt_config.camel_case = camel_case
    config = LocalModuleConfig()

    assert setPref(config, path, 60) is True

    expected_path = (
        "mqtt.mapReportSettings.publishIntervalSecs"
        if camel_case
        else "mqtt.map_report_settings.publish_interval_secs"
    )
    assert capsys.readouterr().out == f"Set {expected_path} to 60\n"
    assert config.mqtt.map_report_settings.publish_interval_secs == 60


@pytest.mark.parametrize("camel_case", [False, True])
@pytest.mark.parametrize("name", ["uplink_enabled", "uplinkEnabled", "UplinkEnabled"])
def test_set_channel_pref_names(
    name: str, camel_case: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    """Standalone channel settings retain name aliases."""
    settings = ChannelSettings()
    mt_config.camel_case = camel_case
    assert setPref(settings, name, True) is True
    assert settings.uplink_enabled is True
    expected_name = "uplinkEnabled" if camel_case else "uplink_enabled"
    assert capsys.readouterr().out == f"Set {expected_name} to True\n"


@pytest.mark.parametrize(
    "path",
    ["network.missing.ip", "network.wifiEnabled.ip", "network.missing.deeper.ip"],
)
def test_set_pref_unknown_path(path: str) -> None:
    """Invalid intermediate components return failure without assignment."""
    config = LocalConfig()
    assert setPref(config, path, 1) is False
    assert config.ListFields() == []


def test_yaml_round_trip_local_and_module_fields(
    tmp_path: Path, profile_interface: MagicMock
) -> None:
    """Exported ordinary, nested and digit-bearing values survive YAML import."""
    local_config = profile_interface.localNode.localConfig
    local_config.display.use_12h_clock = True
    local_config.bluetooth.fixed_pin = 123456
    local_config.network.ipv4_config.ip = 123
    module_config = profile_interface.localNode.moduleConfig
    module_config.external_notification.output_ms = 321
    module_config.mqtt.map_report_settings.publish_interval_secs = 60
    module_config.mesh_beacon.broadcast_offer_channel.module_settings.position_precision = 24
    path = tmp_path / "roundtrip.yaml"
    path.write_text(export_config(profile_interface), encoding="utf8")

    profile = _read_profile(str(path), "auto")

    assert profile.config.display == local_config.display
    assert profile.config.bluetooth == local_config.bluetooth
    assert profile.config.network == local_config.network
    assert profile.module_config == module_config


@pytest.mark.parametrize(
    "path,container,section,field,value",
    [
        ("display.use12hClock", "localConfig", "display", "use_12h_clock", True),
        ("display.use_12h_clock", "localConfig", "display", "use_12h_clock", True),
        (
            "externalNotification.outputMs",
            "moduleConfig",
            "external_notification",
            "output_ms",
            123,
        ),
        (
            "external_notification.output_ms",
            "moduleConfig",
            "external_notification",
            "output_ms",
            123,
        ),
    ],
)
def test_cli_set_field_names(
    profile_interface: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    container: str,
    section: str,
    field: str,
    value: Any,
) -> None:
    """Direct --set resolves section aliases and writes the canonical section."""
    monkeypatch.setattr("sys.argv", ["meshtastic", "--set", path, str(value)])
    monkeypatch.setattr(
        "meshtastic.serial_interface.SerialInterface",
        lambda *_, **__: profile_interface,
    )

    main()

    config = getattr(profile_interface.localNode, container)
    assert getattr(getattr(config, section), field) == value
    profile_interface.localNode.writeConfig.assert_called_once_with(section)


@pytest.mark.parametrize("camel_case", [False, True])
@pytest.mark.parametrize(
    "path,container,section,field,value,json_name",
    [
        (
            "display.use12hClock",
            "localConfig",
            "display",
            "use_12h_clock",
            True,
            "use12hClock",
        ),
        (
            "display.use_12h_clock",
            "localConfig",
            "display",
            "use_12h_clock",
            True,
            "use12hClock",
        ),
        (
            "bluetooth.FixedPin",
            "localConfig",
            "bluetooth",
            "fixed_pin",
            123456,
            "fixedPin",
        ),
        (
            "externalNotification.outputMs",
            "moduleConfig",
            "external_notification",
            "output_ms",
            123,
            "outputMs",
        ),
        (
            "external_notification.output_ms",
            "moduleConfig",
            "external_notification",
            "output_ms",
            123,
            "outputMs",
        ),
    ],
)
def test_cli_get_field_names(
    profile_interface: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    camel_case: bool,
    path: str,
    container: str,
    section: str,
    field: str,
    value: Any,
    json_name: str,
) -> None:
    """--get accepts the same local/module aliases as --set in either output mode."""
    mt_config.camel_case = camel_case
    config = getattr(profile_interface.localNode, container)
    setattr(getattr(config, section), field, value)
    monkeypatch.setattr("sys.argv", ["meshtastic", "--get", path])
    monkeypatch.setattr(
        "meshtastic.serial_interface.SerialInterface",
        lambda *_, **__: profile_interface,
    )

    main()

    output_name = json_name if camel_case else field
    assert f"{section}.{output_name}: {value}" in capsys.readouterr().out
    profile_interface.localNode.requestConfig.assert_not_called()
    profile_interface.localNode.writeConfig.assert_not_called()


@pytest.mark.parametrize(
    "path", ["externalNotification", "externalNotification.outputMs"]
)
def test_get_pref_requests_unavailable_section(
    profile_interface: MagicMock, path: str
) -> None:
    """A section alias still requests the canonical config when no values are cached."""
    node = profile_interface.localNode

    assert getPref(node, path) is True

    node.requestConfig.assert_called_once_with(
        node.moduleConfig.DESCRIPTOR.fields_by_name["external_notification"]
    )


def test_get_pref_whole_section_alias(
    profile_interface: MagicMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """Whole-section queries retain their existing output behavior."""
    node = profile_interface.localNode
    node.moduleConfig.external_notification.output_ms = 123

    assert getPref(node, "externalNotification") is True

    assert "external_notification.output_ms: 123" in capsys.readouterr().out
    node.requestConfig.assert_not_called()


@pytest.mark.parametrize("camel_case", [False, True])
@pytest.mark.parametrize(
    "path",
    [
        "display.unknownClock",
        "externalNotification.unknownField",
        "unknownSection",
        "unknownSection.outputMs",
    ],
)
def test_get_pref_unknown_field(
    profile_interface: MagicMock,
    capsys: pytest.CaptureFixture[str],
    path: str,
    camel_case: bool,
) -> None:
    """Unknown queries keep the existing failure result and available choices."""
    mt_config.camel_case = camel_case
    assert getPref(profile_interface.localNode, path) is False

    assert capsys.readouterr().out.startswith(
        f"Unknown configuration field: {path}\nChoices are...\n"
    )
    profile_interface.localNode.requestConfig.assert_not_called()
