"""Meshtastic unit tests for globals.py
"""

import pytest

from ..globals import Globals


@pytest.mark.unit
def test_globals_get_instaance():
    """Test that we can instantiate a Globals instance"""
    ourglobals = Globals.getInstance()
    ourglobals2 = Globals.getInstance()
    assert ourglobals == ourglobals2


@pytest.mark.unit
def test_globals_there_can_be_only_one():
    """Test that we can cannot create two Globals instances"""
    # if we have an instance, delete it
    Globals.getInstance()
    with pytest.raises(Exception) as pytest_wrapped_e:
        # try to create another instance
        Globals()
    assert pytest_wrapped_e.type == Exception
