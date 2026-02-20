from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

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


class IsTiled(Protocol):
    """Protocol for objects that are tiled and can provide tile dimensions."""

    @property
    def tile_width(self) -> int:
        """The width of tiles in pixels."""
        ...

    @property
    def tile_height(self) -> int:
        """The height of tiles in pixels."""
        ...

    @property
    def height(self) -> int:
        """The height of the image in pixels."""
        ...

    @property
    def width(self) -> int:
        """The width of the image in pixels."""
        ...


class TiledMixin:
    @property
    def tile_count(self: IsTiled) -> tuple[int, int]:
        """The number of tiles in the x and y directions, if the image is tiled."""
        return (
            math.ceil(self.width / self.tile_width),
            math.ceil(self.height / self.tile_height),
        )
