"""Version lookup utilities, isolated for cleanliness"""
import sys

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:  # pragma: no cover - legacy fallback
    from importlib_metadata import PackageNotFoundError, version  # type: ignore

try:
    import pkg_resources
except ImportError:  # pragma: no cover - optional dependency
    pkg_resources = None


def _version_via_importlib() -> str:
    try:
        return version("meshtastic")
    except PackageNotFoundError:
        return "development"


def _version_via_pkg_resources() -> str:
    if pkg_resources is None:
        return "development"

    try:
        return pkg_resources.get_distribution("meshtastic").version  # type: ignore[attr-defined]
    except pkg_resources.DistributionNotFound:  # type: ignore[attr-defined]
        return "development"


def get_active_version() -> str:
    """Get the currently active version using importlib, or pkg_resources if required."""
    if "importlib.metadata" in sys.modules:
        return _version_via_importlib()

    return _version_via_pkg_resources()
