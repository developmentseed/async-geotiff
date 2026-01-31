from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from async_tiff import ImageFileDirectory

    from async_geotiff._array import Array


@dataclass(frozen=True, kw_only=True, eq=False)
class Tile:
    """An array representation of data from a GeoTIFF."""

    x: int
    """The tile column index in the GeoTIFF or overview."""

    y: int
    """The tile row index in the GeoTIFF or overview."""

    _ifd: ImageFileDirectory
    """A reference to the IFD this tile belongs to."""

    array: Array
    """The array data for this tile."""
