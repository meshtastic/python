"""Meshtastic unit tests for formatter.py"""

import json
from pathlib import Path
import re

from unittest.mock import MagicMock
import pytest

import meshtastic
# from meshtastic.formatter import FormatterFactory, AbstractFormatter, InfoFormatter
from ..protobuf import config_pb2
from ..formatter import FormatterFactory, AbstractFormatter, InfoFormatter
from ..mesh_interface import MeshInterface
try:
    # Depends upon the powermon group, not installed by default
    from ..slog import LogSet
    from ..powermon import SimPowerSupply
except ImportError:
    pytest.skip("Can't import LogSet or SimPowerSupply", allow_module_level=True)


def pskBytes(d):
    """Implement a hook to decode psk to byte as needed for the test"""
    if '__psk__' in d:
        d['__psk__'] = bytearray.fromhex(d['__psk__'])
    return d


@pytest.mark.unit
def test_factory():
    ff = FormatterFactory()
    assert len(ff.infoFormatters) > 0

    # test for at least default formatter which should be returned when passed an empty string
    f = ff.getInfoFormatter('')()
    assert f.getType == 'FormatAsText'

    # test correct return when passing various fmt strings
    f = ff.getInfoFormatter('json')()
    assert f.getType == 'FormatAsJson'
    f = ff.getInfoFormatter('JsOn')()
    assert f.getType == 'FormatAsJson'
    f = ff.getInfoFormatter('JSON')()
    assert f.getType == 'FormatAsJson'
    f = ff.getInfoFormatter('txt')()
    assert f.getType == 'FormatAsText'

    # test behavior when passing 'None' as fmt
    f = ff.getInfoFormatter()()
    assert f.getType == 'FormatAsText'

@pytest.mark.unit
@pytest.mark.parametrize("inFile, expected", [
    ("cfg1.json", {
        "len": 4159,
        "keys": ["Owner", "MyInfo", "Metadata", "Nodes", "Preferences", "ModulePreferences", "Channels", "publicURL"]
    }),
    ("cfg2-OwnerOnly.json", {
        "len": 167,
        "keys": ["Owner", "MyInfo", "Metadata", "Nodes", "Preferences", "ModulePreferences", "Channels"]
    }),
    ("cfg3-NoNodes.json", {
        "len": 3411,
        "keys": ["Owner", "MyInfo", "Metadata", "Preferences", "ModulePreferences", "Channels", "publicURL"]
    }),
    ("cfg4-NoPrefs.json", {
        "len": 2353,
        "keys": ["Owner", "MyInfo", "Metadata", "Channels", "publicURL"]
    }),
    ("cfg5-NoChannels.json", {
        "len": 596,
        "keys": ["Owner", "MyInfo", "Metadata", "publicURL"]
    })
])
def test_jsonFormatter(inFile, expected):
    """Load various test files and convert them to json without errors"""
    formatter = FormatterFactory().getInfoFormatter('json')

    data = json.loads(
        (Path('meshtastic/tests/formatter-test-input') / Path(inFile)).read_text(),
        object_hook=pskBytes)
    formattedData = formatter().formatInfo(data)
    assert len(formattedData) == expected['len']

    allKeysPresent = True
    for k in expected['keys']:
        allKeysPresent = allKeysPresent and re.search(k, formattedData) is not None
    assert allKeysPresent

@pytest.mark.unit
@pytest.mark.parametrize("inFile, expected", [
    ("cfg1.json", {
        "len": 2390,
        "keys": ["Owner", "My info", "Metadata", "Nodes in mesh", "Preferences", "Module preferences", "Channels", "Primary channel URL"]
    }),
    ("cfg2-OwnerOnly.json", {
        "len": 220,
        "keys": ["Owner", "My info", "Metadata", "Nodes in mesh", "Preferences", "Module preferences", "Channels"]
    }),
    ("cfg3-NoNodes.json", {
        "len": 1717,
        "keys": ["Owner", "My info", "Metadata", "Preferences", "Module preferences", "Channels", "Primary channel URL"]
    }),
    ("cfg4-NoPrefs.json", {
        "len": 754,
        "keys": ["Owner", "My info", "Metadata", "Channels", "Primary channel URL"]
    }),
    ("cfg5-NoChannels.json", {
        "len": 461,
        "keys": ["Owner", "My info", "Metadata", "Nodes in mesh"]
    })
])
def test_txtFormatter(capsys, inFile, expected):
    """Load various test files and convert them to json without errors"""
    formatter = FormatterFactory().getInfoFormatter('')

    data = json.loads(
        (Path('meshtastic/tests/formatter-test-input') / Path(inFile)).read_text(),
        object_hook=pskBytes)
    formattedData = formatter().formatInfo(data)
    assert len(formattedData) == 0

    out, _ = capsys.readouterr()
    assert len(out) == expected['len']

    allKeysPresent = True
    for k in expected['keys']:
        allKeysPresent = allKeysPresent and re.search(k, out) is not None
    assert allKeysPresent


@pytest.mark.unit
def test_ExceptionAbstractClass():
    with pytest.raises(NotImplementedError):
        AbstractFormatter().formatInfo({})


@pytest.mark.unit
@pytest.mark.parametrize("inCfg, expected", [
    (("cfg1.json", 'json'), {"len": 4160}),
    (("cfg1.json", 'txt'), {"len": 2390}),
    (("cfg1.json", None), {"len": 2390})
    ])
def test_InfoFormatter(capsys, inCfg, expected):
    inFile = inCfg[0]
    data = json.loads(
        (Path('meshtastic/tests/formatter-test-input') / Path(inFile)).read_text(),
        object_hook=pskBytes)
    InfoFormatter().format(data, inCfg[1])

    out, _ = capsys.readouterr()
    assert len(out) == expected['len']

@pytest.mark.unit
@pytest.mark.usefixtures("reset_mt_config")
@pytest.mark.parametrize("inFmt, expected", [
    ('json', {"len": 556, "keys": ["!9388f81c", "Unknown f81c", "44:17:93:88:f8:1c", "https://meshtastic.org/e/#EgA"]}),
    ('txt', {"len": 539, "keys": ["!9388f81c", "Unknown f81c", "44:17:93:88:f8:1c", "https://meshtastic.org/e/#EgA"]}),
    (None, {"len": 539, "keys": ["!9388f81c", "Unknown f81c", "44:17:93:88:f8:1c", "https://meshtastic.org/e/#EgA"]})
    ])
def test_fullSequenceTest(capsys, inFmt, expected):
    """Test formatter when exporting data from an instantiated mesh interface
    --> close the loop of data"""
    iface = MeshInterface(noProto=True)

    NODE_ID = "!9388f81c"
    NODE_NUM = 2475227164
    node = {
            "num": NODE_NUM,
            "user": {
                "id": NODE_ID,
                "longName": "Unknown f81c",
                "shortName": "?1C",
                "macaddr": "RBeTiPgc",
                "hwModel": "TBEAM",
            },
            "position": {},
            "lastHeard": 1640204888,
        }

    iface.nodes = {NODE_ID: node}
    iface.nodesByNum = {NODE_NUM: node}

    myInfo = MagicMock()
    iface.myInfo = myInfo

    iface.localNode.localConfig.lora.CopyFrom(config_pb2.Config.LoRaConfig())

    # Also get some coverage of the structured logging/power meter stuff by turning it on as well
    log_set = LogSet(iface, None, SimPowerSupply())

    ifData = iface.getInfo()
    ifData.update(iface.localNode.getInfo())
    iface.close()
    log_set.close()

    InfoFormatter().format(ifData, inFmt)

    out, _ = capsys.readouterr()
    print(out)
    assert len(out) == expected['len']
