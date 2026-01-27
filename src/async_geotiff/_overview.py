from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from affine import Affine

if TYPE_CHECKING:
    from async_tiff import GeoKeyDirectory, ImageFileDirectory

    from async_geotiff import GeoTIFF


@dataclass(init=False, frozen=True, kw_only=True, eq=False, repr=False)
class Overview:
    """An overview level of a Cloud-Optimized GeoTIFF image."""

    _geotiff: GeoTIFF
    """A reference to the parent GeoTIFF object.
    """

    _gkd: GeoKeyDirectory
    """The GeoKeyDirectory of the primary IFD.
    """

    _ifd: tuple[int, ImageFileDirectory]
    """The IFD for this overview level.

    (positional index of the IFD in the TIFF file, IFD object)
    """

    _mask_ifd: tuple[int, ImageFileDirectory] | None
    """The IFD for the mask associated with this overview level, if any.

    (positional index of the IFD in the TIFF file, IFD object)
    """

    @classmethod
    def _create(
        cls,
        *,
        geotiff: GeoTIFF,
        gkd: GeoKeyDirectory,
        ifd: tuple[int, ImageFileDirectory],
        mask_ifd: tuple[int, ImageFileDirectory] | None,
    ) -> Overview:
        instance = cls.__new__(cls)

        # We use object.__setattr__ because the dataclass is frozen
        object.__setattr__(instance, "_geotiff", geotiff)
        object.__setattr__(instance, "_gkd", gkd)
        object.__setattr__(instance, "_ifd", ifd)
        object.__setattr__(instance, "_mask_ifd", mask_ifd)

        return instance

    @property
    def height(self) -> int:
        """The height of the overview in pixels."""
        return self._ifd[1].image_height

    @cached_property
    def transform(self) -> Affine:
        """The affine transform mapping pixel coordinates to geographic coordinates.

        Returns:
            Affine: The affine transform.
        """
        full_transform = self._geotiff.transform

        overview_width = self._ifd[1].image_width
        full_width = self._geotiff.width
        overview_height = self._ifd[1].image_height
        full_height = self._geotiff.height

        scale_x = full_width / overview_width
        scale_y = full_height / overview_height

        return full_transform * Affine.scale(scale_x, scale_y)

    @property
    def width(self) -> int:
        """The width of the overview in pixels."""
        return self._ifd[1].image_width
