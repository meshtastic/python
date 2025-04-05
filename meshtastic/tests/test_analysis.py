"""Test analysis processing."""

import logging
import os
import sys

import pytest

try:
    # Depends upon matplotlib & other packages in poetry's analysis group, not installed by default
    from meshtastic.analysis.__main__ import main
except ImportError:
    pytest.skip("Can't import meshtastic.analysis", allow_module_level=True)


@pytest.mark.unit
def test_analysis(caplog):
    """Test analysis processing"""

    cur_dir = os.path.dirname(os.path.abspath(__file__))
    slog_input_dir = os.path.join(cur_dir, "slog-test-input")

    sys.argv = ["fakescriptname", "--no-server", "--slog", slog_input_dir]

    with caplog.at_level(logging.DEBUG):
        logging.getLogger().propagate = True  # Let our testing framework see our logs
        main()

    assert "Exiting without running visualization server" in caplog.text
