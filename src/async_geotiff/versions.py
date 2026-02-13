"""Version information."""

from __future__ import annotations

from async_tiff import __version__ as async_tiff_version

from ._version import __version__


def get_versions() -> dict[str, str]:
    """Get package version information."""
    return {"async-geotiff": __version__, "async-tiff": async_tiff_version}
