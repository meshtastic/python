"""Helpers for determining CLI verbosity modes."""

from enum import Enum, auto
from meshtastic import mt_config


class VerbosityType(Enum):
    PROGRESS_ONLY = auto()
    FULL = auto()
    DEBUG = auto()


def get_cli_verbosity() -> VerbosityType:
    """Return the current CLI verbosity."""
    args = getattr(mt_config, "args", None)
    if not args:
        return VerbosityType.PROGRESS_ONLY
    if getattr(args, "debug", False):
        return VerbosityType.DEBUG
    if getattr(args, "verbose", False):
        return VerbosityType.FULL
    if getattr(args, "debuglib", False) or getattr(args, "listen", False):
        return VerbosityType.DEBUG
    return VerbosityType.PROGRESS_ONLY


def cli_verbosity_full_enabled() -> bool:
    """Return True when CLI output should be fully verbose."""
    return get_cli_verbosity() == VerbosityType.FULL


def cli_verbosity_debug_enabled() -> bool:
    """Return True when CLI debug output should be active."""
    return get_cli_verbosity() == VerbosityType.DEBUG


def cli_verbosity_progress_enabled() -> bool:
    """Return True when CLI should show progress-only updates."""
    return get_cli_verbosity() == VerbosityType.PROGRESS_ONLY

