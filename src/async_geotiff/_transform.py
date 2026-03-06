"""Mixin class for coordinate transformation methods."""

from __future__ import annotations

import math
from math import floor
from typing import TYPE_CHECKING, Literal, NamedTuple, Protocol, cast

from affine import Affine

if TYPE_CHECKING:
    from collections.abc import Callable

RASTER_TYPE_PIXEL_IS_POINT = 2


def create_transform(
    *,
    model_tiepoint: list[float] | None,
    model_pixel_scale: list[float] | None,
    model_transformation: list[float] | None,
    raster_type: int | None,
) -> Affine:
    if model_tiepoint is not None and model_pixel_scale is not None:
        affine = create_from_model_tiepoint_and_pixel_scale(
            model_tiepoint,
            model_pixel_scale,
        )

    elif model_transformation is not None:
        affine = create_from_model_transformation(model_transformation)
    else:
        raise ValueError("The image does not have an affine transformation.")

    # Offset transform by half pixel for point-interpreted rasters.
    if raster_type == RASTER_TYPE_PIXEL_IS_POINT:
        affine = affine * Affine.translation(-0.5, -0.5)

    return affine


def create_from_model_tiepoint_and_pixel_scale(
    model_tiepoint: list[float],
    model_pixel_scale: list[float],
) -> Affine:
    x_origin = model_tiepoint[3]
    y_origin = model_tiepoint[4]
    x_resolution = model_pixel_scale[0]
    y_resolution = -model_pixel_scale[1]

    return Affine(x_resolution, 0, x_origin, 0, y_resolution, y_origin)


def create_from_model_transformation(model_transformation: list[float]) -> Affine:
    # ModelTransformation is a 4x4 matrix in row-major order
    # [0  1  2  3 ]   [a  b  0  c]
    # [4  5  6  7 ] = [d  e  0  f]
    # [8  9  10 11]   [0  0  1  0]
    # [12 13 14 15]   [0  0  0  1]
    x_origin = model_transformation[3]
    y_origin = model_transformation[7]
    row_rotation = model_transformation[1]
    col_rotation = model_transformation[4]
    x_resolution = model_transformation[0]
    y_resolution = model_transformation[5]

    return Affine(
        x_resolution,
        row_rotation,
        x_origin,
        col_rotation,
        y_resolution,
        y_origin,
    )


# https://github.com/rasterio/rasterio/blob/7689d9dc83a51b7cc12d1707ce6b011885f61560/rasterio/coords.py#L5-L17
class BoundingBox(NamedTuple):
    """Bounding box, defining extent in cartesian coordinates."""

    left: float
    """Left coordinate"""

    bottom: float
    """Bottom coordinate."""

    right: float
    """Right coordinate"""

    top: float
    """Top coordinate"""


class HasTransform(Protocol):
    """Protocol for objects that have an affine transform."""

    @property
    def height(self) -> int:
        """The height of the image in pixels."""
        ...

    @property
    def width(self) -> int:
        """The width of the image in pixels."""
        ...

    @property
    def transform(self) -> Affine: ...


class TransformMixin:
    """Mixin providing coordinate transformation methods.

    Classes using this mixin must implement HasTransform.
    """

    @property
    def bounds(self: HasTransform) -> BoundingBox:
        """Return the bounds of the dataset in the units of its CRS.

        Returns:
            BoundingBox: The bounding box of the dataset.

        """
        tr = self.transform
        width = self.width
        height = self.height

        # TODO: remove explicit casts with affine v3
        # https://github.com/developmentseed/async-geotiff/issues/123

        # non-rotated transform
        if tr.b == tr.d == 0:
            c0x, c0y = cast("tuple[float, float]", tr * (0, 0))
            c2x, c2y = cast("tuple[float, float]", tr * (width, height))
            return BoundingBox(c0x, c2y, c2x, c0y)

        # Rotated transform
        c0x, c0y = cast("tuple[float, float]", tr * (0, 0))
        c1x, c1y = cast("tuple[float, float]", tr * (0, height))
        c2x, c2y = cast("tuple[float, float]", tr * (width, height))
        c3x, c3y = cast("tuple[float, float]", tr * (width, 0))
        xs = (c0x, c1x, c2x, c3x)
        ys = (c0y, c1y, c2y, c3y)
        return BoundingBox(min(xs), min(ys), max(xs), max(ys))

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

    @property
    def res(self: HasTransform) -> tuple[float, float]:
        """Return the (width, height) of pixels in the units of its CRS."""
        transform = self.transform

        # For rotated images, resolution is the magnitude of the pixel size
        # calculated from the transform matrix components
        res_x = math.sqrt(transform.a**2 + transform.d**2)
        res_y = math.sqrt(transform.b**2 + transform.e**2)

        return (res_x, res_y)

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
