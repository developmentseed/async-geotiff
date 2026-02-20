from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from affine import Affine

from async_geotiff._fetch import FetchTileMixin
from async_geotiff._read import ReadMixin
from async_geotiff._transform import TransformMixin

if TYPE_CHECKING:
    from async_tiff import GeoKeyDirectory, ImageFileDirectory
    from pyproj.crs import CRS

    from async_geotiff import GeoTIFF


@dataclass(init=False, frozen=True, kw_only=True, eq=False, repr=False)
class Overview(ReadMixin, FetchTileMixin, TransformMixin):
    """An overview level of a Cloud-Optimized GeoTIFF image."""

    _geotiff: GeoTIFF
    """A reference to the parent GeoTIFF object.
    """

    _gkd: GeoKeyDirectory
    """The GeoKeyDirectory of the primary IFD.
    """

    _ifd: ImageFileDirectory
    """The IFD for this overview level."""

    _mask_ifd: ImageFileDirectory | None
    """The IFD for the mask associated with this overview level, if any."""

    @classmethod
    def _create(
        cls,
        *,
        geotiff: GeoTIFF,
        gkd: GeoKeyDirectory,
        ifd: ImageFileDirectory,
        mask_ifd: ImageFileDirectory | None,
    ) -> Overview:
        instance = cls.__new__(cls)

        # We use object.__setattr__ because the dataclass is frozen
        object.__setattr__(instance, "_geotiff", geotiff)
        object.__setattr__(instance, "_gkd", gkd)
        object.__setattr__(instance, "_ifd", ifd)
        object.__setattr__(instance, "_mask_ifd", mask_ifd)

        return instance

    @property
    def crs(self) -> CRS:
        """The coordinate reference system of the overview."""
        return self._geotiff.crs

    @property
    def height(self) -> int:
        """The height of the overview in pixels."""
        return self._ifd.image_height

    @property
    def nodata(self) -> int | float | None:
        """The nodata value for the overview, if any."""
        return self._geotiff.nodata

    @property
    def tile_height(self) -> int:
        """The height in pixels per tile of the overview."""
        return self._geotiff.tile_height

    @property
    def tile_width(self) -> int:
        """The width in pixels per tile of the overview."""
        return self._geotiff.tile_width

    @property
    def transform(self) -> Affine:
        """The affine transform mapping pixel coordinates to geographic coordinates.

        Returns:
            Affine: The affine transform.

        """
        full_transform = self._geotiff.transform

        overview_width = self.width
        full_width = self._geotiff.width
        overview_height = self.height
        full_height = self._geotiff.height

        scale_x = full_width / overview_width
        scale_y = full_height / overview_height

        return full_transform * Affine.scale(scale_x, scale_y)

    @property
    def width(self) -> int:
        """The width of the overview in pixels."""
        return self._ifd.image_width
