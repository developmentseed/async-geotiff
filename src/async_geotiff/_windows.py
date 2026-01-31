"""Window utilities for defining rectangular subsets of rasters.

This module provides a Window class compatible with rasterio's Window API,
but simplified for integer-only operations.

A window can be created directly:

    Window(col_off=0, row_off=0, width=100, height=100)

Or from slice tuples (rasterio-style):

    Window.from_slices(rows=(0, 100), cols=(0, 100))
"""

from __future__ import annotations

from dataclasses import dataclass

from async_geotiff.exceptions import WindowError


@dataclass(frozen=True, slots=True)
class Window:
    """A rectangular subset of a raster.

    Windows define pixel regions using column/row offsets and dimensions.
    This class is compatible with rasterio's Window API but uses integers only.

    Attributes:
        col_off: Column offset (x position of left edge).
        row_off: Row offset (y position of top edge).
        width: Width in pixels (number of columns).
        height: Height in pixels (number of rows).

    """

    col_off: int
    row_off: int
    width: int
    height: int

    def __post_init__(self) -> None:
        """Validate window dimensions."""
        if self.col_off < 0 or self.row_off < 0:
            raise IndexError(
                f"Window start indices must be non-negative, "
                f"got col_off={self.col_off}, row_off={self.row_off}",
            )

        if self.width <= 0:
            raise WindowError(f"Window width must be positive, got {self.width}")

        if self.height <= 0:
            raise WindowError(f"Window height must be positive, got {self.height}")

    def __repr__(self) -> str:
        """Return a nicely formatted representation string."""
        return (
            f"async_geotiff.Window(col_off={self.col_off}, row_off={self.row_off}, "
            f"width={self.width}, height={self.height})"
        )

    def intersection(self, other: Window) -> Window:
        """Compute the intersection with another window.

        Args:
            other: Another Window object.

        Returns:
            A new Window representing the overlapping region.

        Raises:
            WindowError: If windows do not intersect.

        """
        col_off = max(self.col_off, other.col_off)
        row_off = max(self.row_off, other.row_off)
        col_stop = min(self.col_off + self.width, other.col_off + other.width)
        row_stop = min(self.row_off + self.height, other.row_off + other.height)

        width = col_stop - col_off
        height = row_stop - row_off

        if width <= 0 or height <= 0:
            raise WindowError(f"Windows do not intersect: {self} and {other}")

        return Window(col_off=col_off, row_off=row_off, width=width, height=height)
