"""Mixin class for coordinate transformation methods."""

from __future__ import annotations

from math import floor
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from affine import Affine


class HasTransform(Protocol):
    """Protocol for objects that have an affine transform."""

    @property
    def transform(self) -> Affine: ...


class TransformMixin:
    """Mixin providing coordinate transformation methods.

    Classes using this mixin must implement HasTransform.
    """

    def index(
        self: HasTransform,
        x: float,
        y: float,
        op: Callable[[float], int] = floor,
    ) -> tuple[int, int]:
        """Get the (row, col) index of the pixel containing (x, y).

        Args:
            x: x value in coordinate reference system.
            y: y value in coordinate reference system.
            op: Function to convert fractional pixels to whole numbers
                (floor, ceiling, round). Defaults to math.floor.

        Returns:
            (row index, col index)

        """
        inv_transform = ~self.transform
        # Affine * (x, y) returns tuple[float, float] for 2D coordinates
        col_frac, row_frac = inv_transform * (x, y)  # type: ignore[misc]

        return (op(row_frac), op(col_frac))

    def xy(
        self: HasTransform,
        row: int,
        col: int,
        offset: Literal["center", "ul", "ur", "ll", "lr"] = "center",
    ) -> tuple[float, float]:
        """Get the coordinates (x, y) of a pixel at (row, col).

        The pixel's center is returned by default, but a corner can be returned
        by setting `offset` to one of `"ul"`, `"ur"`, `"ll"`, `"lr"`.

        Args:
            row: Pixel row.
            col: Pixel column.
            offset: Determines if the returned coordinates are for the center of the
                pixel or for a corner.

        Returns:
            (x, y) coordinates in the dataset's CRS.

        """
        if offset == "center":
            c = col + 0.5
            r = row + 0.5
        elif offset == "ul":
            c = col
            r = row
        elif offset == "ur":
            c = col + 1
            r = row
        elif offset == "ll":
            c = col
            r = row + 1
        elif offset == "lr":
            c = col + 1
            r = row + 1
        else:
            raise ValueError(f"Invalid offset value: {offset}")

        return self.transform * (c, r)
