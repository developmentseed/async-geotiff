from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

import numpy as np
from async_tiff.enums import PlanarConfiguration

from async_geotiff._photometric import convert_to_rgb
from async_geotiff._transform import TransformMixin

if TYPE_CHECKING:
    from affine import Affine
    from async_tiff import Array as AsyncTiffArray
    from async_tiff.enums import PhotometricInterpretation
    from numpy.typing import NDArray
    from pyproj.crs import CRS

    from async_geotiff.colormap import Colormap


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

    _photometric_interpretation: PhotometricInterpretation

    _colormap: Colormap | None

    @classmethod
    def _create(  # noqa: PLR0913
        cls,
        *,
        data: AsyncTiffArray,
        mask: AsyncTiffArray | None,
        planar_configuration: PlanarConfiguration,
        transform: Affine,
        crs: CRS,
        photometric_interpretation: PhotometricInterpretation,
        colormap: Colormap | None,
    ) -> Self:
        """Create an Array from async_tiff data.

        Handles axis reordering to ensure data is always in (bands, height, width)
        order, matching rasterio's convention.

        Keyword Args:
            data: The decoded tile data from async_tiff.
            mask: The decoded mask data from async_tiff, if any.
            planar_configuration: The planar configuration of the source IFD.
            transform: The affine transform for this tile.
            crs: The coordinate reference system.
            photometric_interpretation: The photometric interpretation of the data.
            colormap: The colormap, if any.

        Returns:
            An Array with data in (bands, height, width) order.

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
            _photometric_interpretation=photometric_interpretation,
            _colormap=colormap,
        )

    def to_rgb(self) -> NDArray:
        """Convert the array data to RGB format.

        GeoTIFF data may use various photometric interpretations (e.g., grayscale,
        palette color, CMYK, CIELab, YCbCr). This method transforms the data to standard
        RGB format.

        Returns:
            A NumPy array with shape (3, height, width) representing RGB data.

        Raises:
            NotImplementedError: If the photometric interpretation is unsupported.

        """
        return convert_to_rgb(
            self.data,
            photometric_interpretation=self._photometric_interpretation,
            colormap=self._colormap,
        )
