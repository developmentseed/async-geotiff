from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Literal, Self

from affine import Affine
from async_tiff import TIFF

from async_geotiff.enums import Compression, Interleaving, PhotometricInterp

if TYPE_CHECKING:
    from async_tiff import GeoKeyDirectory, ImageFileDirectory

    from async_geotiff import GeoTIFF


class Overview:
    """An overview level of a Cloud-Optimized GeoTIFF image."""

    _geotiff: GeoTIFF
    """A reference to the parent GeoTIFF object.
    """

    _gkd: GeoKeyDirectory
    """The GeoKeyDirectory of the primary IFD.
    """

    _ifd: ImageFileDirectory
    """The IFD for this overview level.
    """

    _mask_ifd: ImageFileDirectory | None
    """The IFD for the mask associated with this overview level, if any.
    """

    _overview_idx: int
    """The overview level (0 is the full resolution image, 1 is the first overview, etc).
    """

    def __init__(
        self,
        geotiff: GeoTIFF,
        gkd: GeoKeyDirectory,
        ifd: ImageFileDirectory,
        mask_ifd: ImageFileDirectory | None,
        overview_idx: int,
    ) -> None:
        self._geotiff = geotiff
        self._gkd = gkd
        self._ifd = ifd
        self._mask_ifd = mask_ifd
        self._overview_idx = overview_idx

    @cached_property
    def transform(self) -> Affine:
        """The affine transform mapping pixel coordinates to geographic coordinates.

        Returns:
            Affine: The affine transform.
        """
        full_transform = self._geotiff.transform

        overview_width = self._ifd.image_width
        full_width = self._geotiff.width
        overview_height = self._ifd.image_height
        full_height = self._geotiff.height

        scale_x = full_width / overview_width
        scale_y = full_height / overview_height

        return full_transform * Affine.scale(scale_x, scale_y)
