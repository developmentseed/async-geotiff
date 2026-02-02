"""Async GeoTIFF and [Cloud-Optimized GeoTIFF][cogeo] (COG) reader for Python.

[cogeo]: https://cogeo.org/
"""

from . import exceptions
from ._array import Array
from ._geotiff import GeoTIFF
from ._overview import Overview
from ._tile import Tile
from ._version import __version__
from ._windows import Window

__all__ = [
    "Array",
    "GeoTIFF",
    "Overview",
    "Tile",
    "Window",
    "__version__",
    "exceptions",
]
