"""Common pytest code (place for fixtures)."""

import argparse

import pytest

from meshtastic.__main__ import Globals

@pytest.fixture
def reset_globals():
    """Fixture to reset globals."""
    parser = None
    parser = argparse.ArgumentParser()
    Globals.getInstance().reset()
    Globals.getInstance().set_parser(parser)
