"""Meshtastic unit tests for formatter.py"""

import json
from pathlib import Path
import re
from unittest.mock import MagicMock, patch

import pytest

import meshtastic
import meshtastic.formatter
from meshtastic.formatter import FormatterFactory, AbstractFormatter, InfoFormatter


# from ..formatter import FormatterFactory, FormatAsText

def pskBytes(d):
    """Implement a hook to decode psk to byte as needed for the test"""
    if '__psk__' in d:
        d['__psk__'] = bytearray.fromhex(d['__psk__'])
    return d


@pytest.mark.unit
def test_factory():
    ff = meshtastic.formatter.FormatterFactory()
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
        "len": 4161,
        "keys": ["Owner", "My Info", "Metadata", "Nodes", "Preferences", "Module preferences", "Channels", "publicURL"]
    }),
    ("cfg2-OwnerOnly.json", {
        "len": 169,
        "keys": ["Owner", "My Info", "Metadata", "Nodes", "Preferences", "Module preferences", "Channels"]
    }),
    ("cfg3-NoNodes.json", {
        "len": 3413,
        "keys": ["Owner", "My Info", "Metadata", "Preferences", "Module preferences", "Channels", "publicURL"]
    }),
    ("cfg4-NoPrefs.json", {
        "len": 2354,
        "keys": ["Owner", "My Info", "Metadata", "Channels", "publicURL"]
    }),
    ("cfg5-NoChannels.json", {
        "len": 597,
        "keys": ["Owner", "My Info", "Metadata", "publicURL"]
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
    (("cfg1.json", 'json'), {"len": 4162}),
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
