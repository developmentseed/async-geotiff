from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

import numpy as np
from async_tiff.enums import PlanarConfiguration
from numpy.ma import MaskedArray

from async_geotiff._transform import TransformMixin

if TYPE_CHECKING:
    from affine import Affine
    from async_tiff import Array as AsyncTiffArray
    from numpy.typing import NDArray
    from pyproj.crs import CRS
    from xarray import DataArray


@dataclass(frozen=True, kw_only=True, eq=False)
class Array(TransformMixin):
    """An array representation of data from a GeoTIFF."""

    data: NDArray
    """The array data with shape (bands, height, width)."""

    mask: NDArray[np.bool_] | None
    """The mask array with shape (height, width), if any.

    Values of True indicate valid data; False indicates no data.
    """

    width: int
    """The width of the array in pixels."""

    height: int
    """The height of the array in pixels."""

    count: int
    """The number of bands in the array."""

    transform: Affine
    """The affine transform mapping pixel coordinates to geographic coordinates."""

    crs: CRS
    """The coordinate reference system of the array."""

    nodata: float | None = None
    """The nodata value for the array, if any."""

    @classmethod
    def _create(  # noqa: PLR0913
        cls,
        *,
        data: AsyncTiffArray,
        mask: AsyncTiffArray | None,
        planar_configuration: PlanarConfiguration,
        transform: Affine,
        crs: CRS,
        nodata: float | None,
    ) -> Self:
        """Create an Array from async_tiff data.

        Handles axis reordering to ensure data is always in (bands, height, width)
        order, matching rasterio's convention.
        """
        data_arr = np.asarray(data, copy=False)
        if mask is not None:
            mask_arr = np.asarray(mask, copy=False).astype(np.bool_, copy=False)
            assert mask_arr.ndim == 3  # noqa: S101, PLR2004
            assert mask_arr.shape[2] == 1  # noqa: S101
            # This assumes it's always (height, width, 1)
            mask_arr = np.squeeze(mask_arr, axis=2)
        else:
            mask_arr = None

        assert data_arr.ndim == 3, f"Expected 3D array, got {data_arr.ndim}D"  # noqa: S101, PLR2004

        # async_tiff returns data in the native TIFF order:
        # - Chunky (pixel interleaved): (height, width, bands)
        # - Planar (band interleaved): (bands, height, width)
        # We always want (bands, height, width) to match rasterio.
        if planar_configuration == PlanarConfiguration.Chunky:
            # Transpose from (H, W, C) to (C, H, W)
            data_arr = np.moveaxis(data_arr, -1, 0)

        count, height, width = data_arr.shape

        return cls(
            data=data_arr,
            mask=mask_arr,
            width=width,
            height=height,
            count=count,
            transform=transform,
            crs=crs,
            nodata=nodata,
        )

    def as_masked(self) -> MaskedArray:
        """Return the data as a masked array using the Array mask or nodata value.

        !!! warning
            In a numpy [`MaskedArray`][numpy.ma.MaskedArray], `True`
            indicates invalid (masked) data and `False` indicates valid data.

            This is the inverse convention of a GeoTIFF's mask. The boolean array
            [`Array.mask`][async_geotiff.Array.mask] uses `True` for valid data and
            `False` for invalid data.

        Returns:
            A masked array with the same shape as `data`, where invalid data
                (as indicated by the mask) is masked out.

        """
        if self.mask is not None:
            return MaskedArray(self.data, mask=~self.mask)

        if self.nodata is not None:
            return np.ma.masked_equal(self.data, self.nodata)

        return MaskedArray(self.data)

    def as_xarray(self) -> DataArray:
        """Return the array as an xarray DataArray."""
        import xarray as xr
        from rasterix import RasterIndex

        index = RasterIndex.from_transform(
            self.transform,
            width=self.width,
            height=self.height,
            crs=self.crs,
        )

        return xr.DataArray(
            self.data,
            dims=["band", "y", "x"],
            coords={
                "band": np.arange(1, self.count + 1),
                **xr.Coordinates.from_xindex(index),
            },
        )
