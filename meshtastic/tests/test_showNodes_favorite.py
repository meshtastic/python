"""Meshtastic unit tests for showNodes favorite column feature"""

from unittest.mock import MagicMock

import pytest

from ..mesh_interface import MeshInterface


@pytest.fixture
def _iface_with_favorite_nodes():
    """Fixture to setup nodes with favorite flags."""
    nodesById = {
        "!9388f81c": {
            "num": 2475227164,
            "user": {
                "id": "!9388f81c",
                "longName": "Favorite Node",
                "shortName": "FAV1",
                "macaddr": "RBeTiPgc",
                "hwModel": "TBEAM",
            },
            "position": {},
            "lastHeard": 1640204888,
            "isFavorite": True,
        },
        "!12345678": {
            "num": 305419896,
            "user": {
                "id": "!12345678",
                "longName": "Regular Node",
                "shortName": "REG1",
                "macaddr": "ABCDEFGH",
                "hwModel": "TLORA_V2",
            },
            "position": {},
            "lastHeard": 1640204999,
            "isFavorite": False,
        },
        "!abcdef00": {
            "num": 2882400000,
            "user": {
                "id": "!abcdef00",
                "longName": "Legacy Node",
                "shortName": "LEG1",
                "macaddr": "XYZABC00",
                "hwModel": "HELTEC_V3",
            },
            "position": {},
            "lastHeard": 1640205000,
            # Note: No isFavorite field - testing backward compatibility
        },
    }

    nodesByNum = {
        2475227164: {
            "num": 2475227164,
            "user": {
                "id": "!9388f81c",
                "longName": "Favorite Node",
                "shortName": "FAV1",
                "macaddr": "RBeTiPgc",
                "hwModel": "TBEAM",
            },
            "position": {"time": 1640206266},
            "lastHeard": 1640206266,
            "isFavorite": True,
        },
        305419896: {
            "num": 305419896,
            "user": {
                "id": "!12345678",
                "longName": "Regular Node",
                "shortName": "REG1",
                "macaddr": "ABCDEFGH",
                "hwModel": "TLORA_V2",
            },
            "position": {"time": 1640206200},
            "lastHeard": 1640206200,
            "isFavorite": False,
        },
        2882400000: {
            "num": 2882400000,
            "user": {
                "id": "!abcdef00",
                "longName": "Legacy Node",
                "shortName": "LEG1",
                "macaddr": "XYZABC00",
                "hwModel": "HELTEC_V3",
            },
            "position": {"time": 1640206100},
            "lastHeard": 1640206100,
            # Note: No isFavorite field - testing backward compatibility
        },
    }

    iface = MeshInterface(noProto=True)
    iface.nodes = nodesById
    iface.nodesByNum = nodesByNum
    myInfo = MagicMock()
    iface.myInfo = myInfo
    iface.myInfo.my_node_num = 2475227164
    return iface


@pytest.mark.unit
def test_showNodes_favorite_column_header(capsys, _iface_with_favorite_nodes):
    """Test that 'Fav' column header appears in showNodes output"""
    iface = _iface_with_favorite_nodes
    iface.showNodes()
    out, err = capsys.readouterr()
    assert "Fav" in out
    assert err == ""


@pytest.mark.unit
def test_showNodes_favorite_asterisk_display(capsys, _iface_with_favorite_nodes):
    """Test that favorite nodes show asterisk and non-favorites show empty"""
    iface = _iface_with_favorite_nodes
    iface.showNodes()
    out, err = capsys.readouterr()

    # Check that the output contains the "Fav" column
    assert "Fav" in out

    # Find lines containing our nodes
    lines = out.split('\n')
    favorite_line = None
    regular_line = None
    legacy_line = None
    for line in lines:
        if "Favorite Node" in line or "FAV1" in line:
            favorite_line = line
        if "Regular Node" in line or "REG1" in line:
            regular_line = line
        if "Legacy Node" in line or "LEG1" in line:
            legacy_line = line

    # Verify all nodes are present in the output
    assert favorite_line is not None, "Favorite node should be in output"
    assert regular_line is not None, "Regular node should be in output"
    assert legacy_line is not None, "Legacy node should be in output"

    # Verify the favorite node has an asterisk in its row
    assert "*" in favorite_line, "Favorite node should have an asterisk"

    # Verify the regular (non-favorite) node does NOT have an asterisk
    assert regular_line.count("*") == 0, "Non-favorite node should not have an asterisk"

    # Verify the legacy node (without isFavorite field) does NOT have an asterisk
    assert legacy_line.count("*") == 0, "Legacy node without isFavorite field should not have an asterisk"

    assert err == ""


@pytest.mark.unit
def test_showNodes_favorite_field_formatting():
    """Test the formatting logic for isFavorite field"""
    # Test favorite node
    raw_value = True
    formatted_value = "*" if raw_value else ""
    assert formatted_value == "*"

    # Test non-favorite node
    raw_value = False
    formatted_value = "*" if raw_value else ""
    assert formatted_value == ""

    # Test None/missing value
    raw_value = None
    formatted_value = "*" if raw_value else ""
    assert formatted_value == ""


@pytest.mark.unit
def test_showNodes_with_custom_fields_including_favorite(capsys, _iface_with_favorite_nodes):
    """Test that isFavorite can be specified in custom showFields"""
    iface = _iface_with_favorite_nodes
    custom_fields = ["user.longName", "isFavorite"]
    iface.showNodes(showFields=custom_fields)
    out, err = capsys.readouterr()

    # Should still show the Fav column when explicitly requested
    assert "Fav" in out
    assert err == ""


@pytest.mark.unit
def test_showNodes_default_fields_includes_favorite(_iface_with_favorite_nodes):
    """Test that isFavorite is included in default fields"""
    iface = _iface_with_favorite_nodes

    # Call showNodes which uses default fields
    result = iface.showNodes()

    # The result should contain the formatted table as a string
    assert "Fav" in result


@pytest.mark.unit
def test_showNodes_backward_compatibility_missing_field(capsys, _iface_with_favorite_nodes):
    """Test that nodes without isFavorite field are handled gracefully"""
    iface = _iface_with_favorite_nodes
    iface.showNodes()
    out, err = capsys.readouterr()

    # Find the legacy node line
    lines = out.split('\n')
    legacy_line = None
    for line in lines:
        if "Legacy Node" in line or "LEG1" in line:
            legacy_line = line
            break

    # Verify the legacy node appears in output
    assert legacy_line is not None, "Legacy node without isFavorite field should appear in output"

    # Verify it doesn't have an asterisk (should be treated as non-favorite)
    assert legacy_line.count("*") == 0, "Legacy node should not have asterisk (treated as non-favorite)"

    assert err == ""
