"""Async GeoTIFF and [Cloud-Optimized GeoTIFF][cogeo] (COG) reader for Python.

[cogeo]: https://cogeo.org/
"""

from . import exceptions
from ._array import RasterArray
from ._gdal_metadata import BandStatistics
from ._geotiff import GeoTIFF
from ._overview import Overview
from ._tile import Tile
from ._transform import BoundingBox
from ._version import __version__
from ._windows import Window

__all__ = [
    "BandStatistics",
    "BoundingBox",
    "GeoTIFF",
    "Overview",
    "RasterArray",
    "Tile",
    "Window",
    "__version__",
    "exceptions",
]
