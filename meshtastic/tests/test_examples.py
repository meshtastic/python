"""Meshtastic test that the examples run as expected.
   We assume you have a python virtual environment in current directory.
   If not, you need to run: "python3 -m venv venv", "source venv/bin/activate", "pip install ."
"""
import subprocess

import pytest


@pytest.mark.examples
def test_examples_hello_world_serial_no_arg():
    """Test hello_world_serial without any args"""
    return_value, _ = subprocess.getstatusoutput(
        "source venv/bin/activate; python3 examples/hello_world_serial.py"
    )
    assert return_value == 3


@pytest.mark.examples
def test_examples_hello_world_serial_with_arg(capsys):
    """Test hello_world_serial with arg"""
    return_value, _ = subprocess.getstatusoutput(
        "source venv/bin/activate; python3 examples/hello_world_serial.py hello"
    )
    assert return_value == 1
    _, err = capsys.readouterr()
    assert err == ""
    # TODO: Why does this not work?
    # assert out == 'Warning: No Meshtastic devices detected.'
