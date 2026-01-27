"""Async GeoTIFF and [Cloud-Optimized GeoTIFF][cogeo] (COG) reader for Python.

[cogeo]: https://cogeo.org/
"""

from ._geotiff import GeoTIFF
from ._overview import Overview
from ._version import __version__

__all__ = ["GeoTIFF", "Overview", "__version__"]
