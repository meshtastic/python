"""Tests for bin/inject_nanopb_options.py — the nanopb options injection script
and the generated protobuf descriptors it produces.

Part 1 (test_parse_*, test_inject_*): unit-tests the script's logic directly,
using small synthetic proto snippets.

Part 2 (test_descriptor_*): smoke-tests the already-generated _pb2.py files to
confirm the regen pipeline embedded the expected nanopb options.
"""

import importlib.util
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, strategies as st

from meshtastic.protobuf import (
    atak_pb2,
    config_pb2,
    mesh_pb2,
    nanopb_pb2,
    telemetry_pb2,
)

# ---------------------------------------------------------------------------
# Load bin/inject_nanopb_options.py as a module without adding it to the
# package.  __main__ guard means no side-effects on import.
# ---------------------------------------------------------------------------
_SCRIPT_PATH = Path(__file__).parent.parent.parent / "bin" / "inject_nanopb_options.py"


def _load_inject_module():
    spec = importlib.util.spec_from_file_location("inject_nanopb_options", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    with patch.object(sys, "argv", ["inject_nanopb_options.py"]):
        spec.loader.exec_module(mod)
    return mod


_inj = _load_inject_module()

parse_value = _inj.parse_value
parse_options_file = _inj.parse_options_file
format_nanopb_opts = _inj.format_nanopb_opts
inject_into_proto = _inj.inject_into_proto
message_path_matches = _inj.message_path_matches

# Convenience: the nanopb import path the script uses after the sed fixup
NANOPB_IMPORT = 'import "meshtastic/protobuf/nanopb.proto";'


# ===========================================================================
# Part 1 — Script unit tests
# ===========================================================================

# ---------------------------------------------------------------------------
# parse_value
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_value_integer():
    """parse_value converts a decimal string to int."""
    assert parse_value("40") == 40


@pytest.mark.unit
def test_parse_value_negative_integer():
    """parse_value handles negative integer strings."""
    assert parse_value("-1") == -1


@pytest.mark.unit
def test_parse_value_true():
    """parse_value converts 'true' to Python True."""
    assert parse_value("true") is True


@pytest.mark.unit
def test_parse_value_false():
    """parse_value converts 'false' to Python False."""
    assert parse_value("false") is False


@pytest.mark.unit
def test_parse_value_string():
    """parse_value returns non-numeric, non-boolean strings as-is."""
    assert parse_value("IS_8") == "IS_8"


@pytest.mark.unit
@given(st.integers())
def test_parse_value_any_integer_returns_int(n):
    """parse_value always returns int for any decimal integer string."""
    assert parse_value(str(n)) == n


@pytest.mark.unit
@given(st.text())
def test_parse_value_never_crashes(s):
    """parse_value never raises on arbitrary input."""
    result = parse_value(s)
    assert isinstance(result, (int, bool, str))


@pytest.mark.unit
@given(st.text().filter(lambda s: not s.lstrip("-").isdigit() and s.lower() not in ("true", "false")))
def test_parse_value_non_numeric_non_bool_returns_str(s):
    """parse_value returns the original string when it is neither an integer nor a boolean."""
    assert parse_value(s) == s


# ---------------------------------------------------------------------------
# parse_options_file
# ---------------------------------------------------------------------------


def _write_options(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "test.options"
    p.write_text(textwrap.dedent(content))
    return p


@pytest.mark.unit
def test_parse_wildcard(tmp_path):
    """Wildcard pattern (no dot) lands in the wildcard dict."""
    f = _write_options(tmp_path, "*macaddr max_size:6 fixed_length:true\n")
    specific, wildcard = parse_options_file(f)
    assert "macaddr" in wildcard
    assert wildcard["macaddr"] == {"max_size": 6, "fixed_length": True}
    assert specific == {}


@pytest.mark.unit
def test_parse_specific(tmp_path):
    """Single-dot pattern lands in the specific dict with a 2-tuple key."""
    f = _write_options(tmp_path, "*User.long_name max_size:40\n")
    specific, wildcard = parse_options_file(f)
    assert ("User", "long_name") in specific
    assert specific[("User", "long_name")] == {"max_size": 40}
    assert wildcard == {}


@pytest.mark.unit
def test_parse_multilevel(tmp_path):
    """Three-part pattern (Route.Link.uid) produces a 3-tuple key."""
    f = _write_options(tmp_path, "*Route.Link.uid max_size:48\n")
    specific, _ = parse_options_file(f)
    assert ("Route", "Link", "uid") in specific
    assert specific[("Route", "Link", "uid")] == {"max_size": 48}


@pytest.mark.unit
def test_parse_strips_inline_comments(tmp_path):
    """Text after # is ignored."""
    f = _write_options(tmp_path, "*id max_size:16 # node id strings\n")
    _, wildcard = parse_options_file(f)
    assert wildcard["id"] == {"max_size": 16}


@pytest.mark.unit
def test_parse_skips_comment_only_lines(tmp_path):
    """Lines that are entirely comments produce no entries."""
    f = _write_options(tmp_path, "# this is a comment\n*id max_size:16\n")
    _, wildcard = parse_options_file(f)
    assert list(wildcard.keys()) == ["id"]


@pytest.mark.unit
def test_parse_skips_blank_lines(tmp_path):
    """Blank lines are silently ignored."""
    f = _write_options(tmp_path, "\n\n*id max_size:16\n\n")
    _, wildcard = parse_options_file(f)
    assert "id" in wildcard


@pytest.mark.unit
def test_parse_skips_non_python_options(tmp_path):
    """Options not in FIELD_OPTIONS (e.g. anonymous_oneof) are dropped."""
    f = _write_options(tmp_path, "*MeshPacket.payload_variant anonymous_oneof:true\n")
    specific, wildcard = parse_options_file(f)
    # anonymous_oneof is not in FIELD_OPTIONS → no entry should be produced
    assert specific == {}
    assert wildcard == {}


@pytest.mark.unit
def test_parse_merges_repeated_patterns(tmp_path):
    """Two lines for the same pattern are merged."""
    f = _write_options(
        tmp_path,
        "*SecurityConfig.admin_key max_size:32\n"
        "*SecurityConfig.admin_key max_count:3\n",
    )
    specific, _ = parse_options_file(f)
    assert specific[("SecurityConfig", "admin_key")] == {"max_size": 32, "max_count": 3}


@pytest.mark.unit
def test_parse_int_and_bool_values(tmp_path):
    """int_size parses as int; fixed_length parses as bool."""
    f = _write_options(tmp_path, "*Data.payload max_size:233 fixed_length:false\n")
    specific, _ = parse_options_file(f)
    opts = specific[("Data", "payload")]
    assert opts["max_size"] == 233
    assert opts["fixed_length"] is False


# ---------------------------------------------------------------------------
# message_path_matches
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_message_path_matches_simple():
    """A single-element path matches the current message on the stack."""
    stack = [("message", "User")]
    assert message_path_matches(stack, ("User",))


@pytest.mark.unit
def test_message_path_matches_nested():
    """Both a 1-element and 2-element path match correctly against a nested stack."""
    stack = [("message", "Config"), ("message", "DeviceConfig")]
    assert message_path_matches(stack, ("DeviceConfig",))
    assert message_path_matches(stack, ("Config", "DeviceConfig"))


@pytest.mark.unit
def test_message_path_matches_with_oneof_in_stack():
    """oneof frames in the stack are skipped when looking for messages."""
    stack = [("message", "MeshPacket"), ("oneof", "payload_variant")]
    assert message_path_matches(stack, ("MeshPacket",))


@pytest.mark.unit
def test_message_path_no_match():
    """A path with the wrong message name does not match."""
    stack = [("message", "User")]
    assert not message_path_matches(stack, ("Route",))


@pytest.mark.unit
def test_message_path_multilevel_partial_match():
    """A 2-element path must match the last 2 message names on the stack."""
    stack = [("message", "Route"), ("message", "Link")]
    assert message_path_matches(stack, ("Route", "Link"))
    assert not message_path_matches(stack, ("Other", "Link"))


# ---------------------------------------------------------------------------
# format_nanopb_opts
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_format_max_size():
    """max_size is rendered as an integer literal."""
    assert format_nanopb_opts({"max_size": 40}) == "(nanopb).max_size = 40"


@pytest.mark.unit
def test_format_int_size_as_enum():
    """int_size numeric values are rendered as IS_8/IS_16/IS_32/IS_64 enum names."""
    assert format_nanopb_opts({"int_size": 8}) == "(nanopb).int_size = IS_8"
    assert format_nanopb_opts({"int_size": 16}) == "(nanopb).int_size = IS_16"
    assert format_nanopb_opts({"int_size": 32}) == "(nanopb).int_size = IS_32"
    assert format_nanopb_opts({"int_size": 64}) == "(nanopb).int_size = IS_64"


@pytest.mark.unit
def test_format_bool_true():
    """True is rendered as the proto literal 'true'."""
    assert format_nanopb_opts({"fixed_length": True}) == "(nanopb).fixed_length = true"


@pytest.mark.unit
def test_format_bool_false():
    """False is rendered as the proto literal 'false'."""
    assert format_nanopb_opts({"fixed_length": False}) == "(nanopb).fixed_length = false"


# ---------------------------------------------------------------------------
# inject_into_proto — helpers
# ---------------------------------------------------------------------------

_NANOPB_IMPORT_PATH = "meshtastic/protobuf/nanopb.proto"


def _inject(proto_src: str, specific=None, wildcard=None) -> str:
    """Run inject_into_proto with empty dicts as defaults."""
    return inject_into_proto(
        textwrap.dedent(proto_src),
        specific or {},
        wildcard or {},
        _NANOPB_IMPORT_PATH,
    )


# ---------------------------------------------------------------------------
# inject_into_proto — option injection
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_inject_adds_option_to_plain_field():
    """A field with no existing options gets a nanopb annotation."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/channel.proto";
        message User {
          string long_name = 1;
        }
    """
    result = _inject(proto, specific={("User", "long_name"): {"max_size": 40}})
    assert "long_name = 1 [(nanopb).max_size = 40];" in result


@pytest.mark.unit
def test_inject_merges_with_existing_options():
    """nanopb annotation is appended after existing field options."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/channel.proto";
        message User {
          bytes macaddr = 4 [deprecated = true];
        }
    """
    result = _inject(proto, wildcard={"macaddr": {"max_size": 6}})
    assert "[deprecated = true, (nanopb).max_size = 6];" in result


@pytest.mark.unit
def test_inject_int_size_uses_enum_name():
    """int_size values are written as IS_N enum names, not raw integers."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/mesh.proto";
        message Foo {
          uint32 hop_limit = 9;
        }
    """
    result = _inject(proto, specific={("Foo", "hop_limit"): {"int_size": 8}})
    assert "(nanopb).int_size = IS_8" in result


@pytest.mark.unit
def test_inject_wildcard_applied_across_messages():
    """A wildcard option hits the matching field in every message."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/mesh.proto";
        message A {
          bytes macaddr = 1;
        }
        message B {
          bytes macaddr = 2;
        }
    """
    result = _inject(proto, wildcard={"macaddr": {"max_size": 6}})
    assert result.count("(nanopb).max_size = 6") == 2


@pytest.mark.unit
def test_inject_specific_not_leaking_to_other_messages():
    """A message-specific option does NOT apply to a different message's field."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/mesh.proto";
        message User {
          string id = 1;
        }
        message Other {
          string id = 1;
        }
    """
    result = _inject(proto, specific={("User", "id"): {"max_size": 16}})
    # Easier: count annotations — should be exactly one
    assert result.count("(nanopb).max_size = 16") == 1


@pytest.mark.unit
def test_inject_nested_message():
    """A 2-part specific key only hits the field in the correct nested message."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/mesh.proto";
        message Route {
          message Link {
            string uid = 1;
          }
          string uid = 2;
        }
    """
    # Route.Link.uid → key = ('Route', 'Link', 'uid')
    result = _inject(proto, specific={("Route", "Link", "uid"): {"max_size": 48}})
    lines = result.splitlines()
    # Only the uid inside Link should have the annotation
    assert result.count("(nanopb).max_size = 48") == 1
    # Confirm it's the inner one (it has 4 spaces more indent than outer uid)
    annotated = next(l for l in lines if "(nanopb).max_size = 48" in l)
    plain = next(l for l in lines if "uid = 2" in l)
    assert annotated.index("uid") > plain.index("uid")


@pytest.mark.unit
def test_inject_skips_enum_body_values():
    """Enum value lines must not be treated as field declarations."""
    proto = """\
        syntax = "proto3";
        message Foo {
          enum Role {
            CLIENT = 0;
            ROUTER = 2;
          }
          Role role = 1;
        }
    """
    # Wildcard for 'role' should only hit the field, not enum values
    result = _inject(proto, wildcard={"role": {"max_size": 8}})
    assert result.count("(nanopb)") == 1
    assert "(nanopb)" not in next(l for l in result.splitlines() if "CLIENT" in l)


@pytest.mark.unit
def test_inject_optional_qualifier_preserved():
    """The 'optional' qualifier is kept when a field gets an annotation."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/mesh.proto";
        message Foo {
          optional uint32 altitude = 3;
        }
    """
    result = _inject(proto, specific={("Foo", "altitude"): {"int_size": 16}})
    assert "optional uint32 altitude = 3 [(nanopb).int_size = IS_16];" in result


@pytest.mark.unit
def test_inject_repeated_qualifier_preserved():
    """The 'repeated' qualifier is kept when a field gets an annotation."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/mesh.proto";
        message Foo {
          repeated int32 snr = 2;
        }
    """
    result = _inject(proto, specific={("Foo", "snr"): {"max_count": 8}})
    assert "repeated int32 snr = 2 [(nanopb).max_count = 8];" in result


@pytest.mark.unit
def test_inject_multiple_options_on_one_field():
    """Multiple options from the same pattern are all injected on one field."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/mesh.proto";
        message Foo {
          repeated int32 snr = 1;
        }
    """
    result = _inject(proto, specific={("Foo", "snr"): {"max_count": 8, "int_size": 8}})
    assert "(nanopb).max_count = 8" in result
    assert "(nanopb).int_size = IS_8" in result


# ---------------------------------------------------------------------------
# inject_into_proto — import insertion
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_inject_adds_nanopb_import_when_absent():
    """nanopb.proto import is added when the file has other imports."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/mesh.proto";
        message Foo {
          string name = 1;
        }
    """
    result = _inject(proto, wildcard={"name": {"max_size": 30}})
    assert NANOPB_IMPORT in result


@pytest.mark.unit
def test_inject_no_duplicate_nanopb_import():
    """nanopb.proto import is NOT added a second time if already present."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/mesh.proto";
        import "meshtastic/protobuf/nanopb.proto";
        message Foo {
          string name = 1;
        }
    """
    result = _inject(proto, wildcard={"name": {"max_size": 30}})
    assert result.count(NANOPB_IMPORT) == 1


@pytest.mark.unit
def test_inject_import_placed_after_existing_imports():
    """nanopb import appears after the last existing import, not at the top."""
    proto = """\
        syntax = "proto3";
        import "meshtastic/protobuf/mesh.proto";
        message Foo {
          string name = 1;
        }
    """
    result = _inject(proto, wildcard={"name": {"max_size": 30}})
    lines = result.splitlines()
    mesh_idx = next(i for i, l in enumerate(lines) if "mesh.proto" in l)
    nanopb_idx = next(i for i, l in enumerate(lines) if "nanopb.proto" in l)
    assert nanopb_idx == mesh_idx + 1


@pytest.mark.unit
def test_inject_import_after_syntax_when_no_existing_imports():
    """When a proto has no imports, nanopb import goes AFTER the syntax line,
    not before it (regression test for the last_import_idx == -1 bug)."""
    proto = """\
        syntax = "proto3";
        message XModem {
          uint32 seq = 2;
        }
    """
    result = _inject(proto, specific={("XModem", "seq"): {"int_size": 16}})
    lines = result.splitlines()
    syntax_idx = next(i for i, l in enumerate(lines) if l.strip().startswith("syntax"))
    nanopb_idx = next(i for i, l in enumerate(lines) if "nanopb.proto" in l)
    assert nanopb_idx > syntax_idx, "nanopb import must come after the syntax line"
    # syntax line must still be first non-blank line
    first_non_blank = next(l.strip() for l in lines if l.strip())
    assert first_non_blank.startswith("syntax")


@pytest.mark.unit
def test_inject_noop_when_no_options():
    """Proto file is returned unchanged when there are no options to inject."""
    proto = 'syntax = "proto3";\nmessage Foo { string x = 1; }\n'
    result = _inject(proto)
    assert result == proto


# ===========================================================================
# Part 2 — Descriptor integration tests
# Verify that regen-protobufs.sh produced _pb2.py files with nanopb options
# embedded in the serialized descriptors.
# ===========================================================================


def _field_opts(descriptor, *path):
    """Walk a descriptor by field/nested-type path and return its nanopb opts.

    Elements of *path that are message names are looked up in nested_types_by_name;
    the final element is looked up in fields_by_name.
    """
    desc = descriptor
    for step in path[:-1]:
        desc = desc.nested_types_by_name[step]
    field = desc.fields_by_name[path[-1]]
    return field.GetOptions().Extensions[nanopb_pb2.nanopb]


@pytest.mark.unit
def test_descriptor_user_long_name():
    """User.long_name has max_size = 40 from mesh.options."""
    opts = _field_opts(mesh_pb2.DESCRIPTOR.message_types_by_name["User"], "long_name")
    assert opts.max_size == 40


@pytest.mark.unit
def test_descriptor_user_short_name():
    """User.short_name has max_size = 5 from mesh.options."""
    opts = _field_opts(mesh_pb2.DESCRIPTOR.message_types_by_name["User"], "short_name")
    assert opts.max_size == 5


@pytest.mark.unit
def test_descriptor_wildcard_macaddr():
    """Wildcard option from mesh.options applied to User.macaddr."""
    opts = _field_opts(mesh_pb2.DESCRIPTOR.message_types_by_name["User"], "macaddr")
    assert opts.max_size == 6
    assert opts.fixed_length is True


@pytest.mark.unit
def test_descriptor_meshpacket_hop_limit():
    """MeshPacket.hop_limit has int_size = IS_8 from mesh.options."""
    opts = _field_opts(mesh_pb2.DESCRIPTOR.message_types_by_name["MeshPacket"], "hop_limit")
    assert opts.int_size == nanopb_pb2.IS_8


@pytest.mark.unit
def test_descriptor_routediscovery_snr_towards():
    """RouteDiscovery.snr_towards has max_count = 8 and int_size = IS_8 from mesh.options."""
    opts = _field_opts(
        mesh_pb2.DESCRIPTOR.message_types_by_name["RouteDiscovery"], "snr_towards"
    )
    assert opts.max_count == 8
    assert opts.int_size == nanopb_pb2.IS_8


@pytest.mark.unit
def test_descriptor_data_payload():
    """Data.payload has max_size = 233 from mesh.options."""
    opts = _field_opts(mesh_pb2.DESCRIPTOR.message_types_by_name["Data"], "payload")
    assert opts.max_size == 233


@pytest.mark.unit
def test_descriptor_nested_deviceconfig_tzdef():
    """Config.DeviceConfig.tzdef — option on a field inside a nested message."""
    config = config_pb2.DESCRIPTOR.message_types_by_name["Config"]
    opts = _field_opts(config, "DeviceConfig", "tzdef")
    assert opts.max_size == 65


@pytest.mark.unit
def test_descriptor_nested_securityconfig_admin_key():
    """Config.SecurityConfig.admin_key — two options merged from two .options lines."""
    config = config_pb2.DESCRIPTOR.message_types_by_name["Config"]
    opts = _field_opts(config, "SecurityConfig", "admin_key")
    assert opts.max_size == 32
    assert opts.max_count == 3


@pytest.mark.unit
def test_descriptor_multilevel_nested_route_link_uid():
    """Route.Link.uid — three-level nested pattern from atak.options."""
    route = atak_pb2.DESCRIPTOR.message_types_by_name["Route"]
    opts = _field_opts(route, "Link", "uid")
    assert opts.max_size == 48


@pytest.mark.unit
def test_descriptor_telemetry_environment_one_wire_temperature():
    """EnvironmentMetrics.one_wire_temperature has max_count = 8 from telemetry.options."""
    env = telemetry_pb2.DESCRIPTOR.message_types_by_name["EnvironmentMetrics"]
    opts = _field_opts(env, "one_wire_temperature")
    assert opts.max_count == 8
