"""Async GeoTIFF and [Cloud-Optimized GeoTIFF][cogeo] (COG) reader for Python.

[cogeo]: https://cogeo.org/
"""

from ._array import Array
from ._geotiff import GeoTIFF
from ._overview import Overview
from ._tile import Tile
from ._version import __version__
from .windows import Window

__all__ = ["Array", "GeoTIFF", "Overview", "Tile", "Window", "__version__"]
