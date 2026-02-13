from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from async_geotiff._array import Array


@dataclass(frozen=True, kw_only=True, eq=False)
class Tile:
    """A tile from a GeoTIFF, containing array data and grid position."""

    x: int
    """The tile column index in the GeoTIFF or overview."""

    y: int
    """The tile row index in the GeoTIFF or overview."""

    array: Array
    """The array data for this tile."""
