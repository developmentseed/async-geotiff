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
from typing import Self

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

    @property
    def _col_stop(self) -> int:
        """Column stop index (col_off + width)."""
        return self.col_off + self.width

    @property
    def _row_stop(self) -> int:
        """Row stop index (row_off + height)."""
        return self.row_off + self.height

    @classmethod
    def from_slices(
        cls,
        rows: tuple[int, int] | slice,
        cols: tuple[int, int] | slice,
    ) -> Self:
        """Construct a Window from row and column slices or tuples.

        Args:
            rows: A tuple of (row_start, row_stop) or a slice object.
            cols: A tuple of (col_start, col_stop) or a slice object.

        Returns:
            A new Window object.

        Raises:
            WindowError: If slices are invalid.

        Examples:
            >>> Window.from_slices(rows=(0, 100), cols=(0, 50))
            Window(col_off=0, row_off=0, width=50, height=100)

            >>> Window.from_slices(rows=slice(10, 20), cols=slice(5, 15))
            Window(col_off=5, row_off=10, width=10, height=10)

        """
        if isinstance(rows, slice):
            if rows.start is None or rows.stop is None:
                raise WindowError("Slice start and stop must be specified")
            row_start, row_stop = rows.start, rows.stop
        else:
            if len(rows) != 2:  # noqa: PLR2004
                raise WindowError("rows must have exactly 2 elements (start, stop)")
            row_start, row_stop = rows

        if isinstance(cols, slice):
            if cols.start is None or cols.stop is None:
                raise WindowError("Slice start and stop must be specified")
            col_start, col_stop = cols.start, cols.stop
        else:
            if len(cols) != 2:  # noqa: PLR2004
                raise WindowError("cols must have exactly 2 elements (start, stop)")
            col_start, col_stop = cols

        return cls(
            col_off=col_start,
            row_off=row_start,
            width=max(col_stop - col_start, 0),
            height=max(row_stop - row_start, 0),
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
        col_stop = min(self._col_stop, other._col_stop)
        row_stop = min(self._row_stop, other._row_stop)

        width = col_stop - col_off
        height = row_stop - row_off

        if width <= 0 or height <= 0:
            raise WindowError(f"Windows do not intersect: {self} and {other}")

        return Window(col_off=col_off, row_off=row_off, width=width, height=height)

    def _intersects(self, other: Window) -> bool:
        """Check if this window intersects with another.

        Args:
            other: Another Window object.

        Returns:
            True if the windows overlap, False otherwise.

        """
        col_off = max(self.col_off, other.col_off)
        row_off = max(self.row_off, other.row_off)
        col_stop = min(self._col_stop, other._col_stop)
        row_stop = min(self._row_stop, other._row_stop)

        return (col_stop - col_off) > 0 and (row_stop - row_off) > 0

    def _crop(self, height: int, width: int) -> Window:
        """Crop window to fit within given dimensions.

        Args:
            height: Maximum height (number of rows).
            width: Maximum width (number of columns).

        Returns:
            A new Window cropped to the given bounds.

        """
        row_start = min(max(self.row_off, 0), height)
        col_start = min(max(self.col_off, 0), width)
        row_stop = max(0, min(self._row_stop, height))
        col_stop = max(0, min(self._col_stop, width))

        return Window(
            col_off=col_start,
            row_off=row_start,
            width=col_stop - col_start,
            height=row_stop - row_start,
        )
