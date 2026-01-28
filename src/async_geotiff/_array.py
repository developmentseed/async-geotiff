from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from affine import Affine
    from numpy.typing import NDArray
    from pyproj import CRS


@dataclass(frozen=True, kw_only=True, eq=False)
class Array:
    """An array representation of data from a GeoTIFF."""

    data: NDArray
    """The raw byte data of the array."""

    mask: NDArray | None
    """The mask array, if any."""

    width: int
    """The width of the array in pixels."""

    height: int
    """The height of the array in pixels."""

    transform: Affine
    """The affine transform mapping pixel coordinates to geographic coordinates."""

    crs: CRS
    """The coordinate reference system of the array."""
