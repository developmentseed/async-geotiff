"""High-level Colormap class for GeoTIFF colormaps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from async_tiff import Colormap as AsyncTiffColormap
    from numpy.typing import NDArray


@dataclass(frozen=True, kw_only=True, eq=False)
class Colormap:
    """A representation of a GeoTIFF colormap.

    GeoTIFF colormaps
    """

    _cmap: AsyncTiffColormap
    """The colormap data held in Rust, accessible via the buffer protocol.

    Has shape `(N, 3)` and is of data type uint16.
    """

    _nodata: int | float | None
    """The nodata value from gdal_nodata, if set."""

    def as_array(self, *, dtype: type[np.uint8 | np.uint16] = np.uint8) -> NDArray:
        """Return the colormap as a NumPy array with shape (N, 3) and dtype uint16.

        Each row corresponds to a color entry in the colormap, with columns
        representing the Red, Green, and Blue components respectively.

        This is the most efficient way to access and apply the colormap data.

        ```py
        geotiff = await GeoTIFF.open(...)
        array = await geotiff.fetch_tile(0, 0)

        colormap = geotiff.colormap
        colormap_array = colormap.as_array()

        rgb_data = colormap_array[array.data[0]]
        # A 3D array with shape (height, width, 3)
        ```

        Returns:
            A NumPy array representation of the colormap.

        """
        cmap_array = np.asarray(self._cmap)
        if dtype == np.uint8:
            return (cmap_array >> 8).astype(np.uint8)
        if dtype == np.uint16:
            return cmap_array
        raise ValueError("dtype must be either np.uint8 or np.uint16.")

    def as_dict(
        self,
        *,
        dtype: type[np.uint8 | np.uint16] = np.uint8,
    ) -> dict[int, tuple[int, int, int]]:
        """Return the colormap as a dictionary mapping indices to RGB tuples.

        Returns:
            A dictionary where keys are indices and values are tuples of
                (Red, Green, Blue) components.

        """
        cmap_array = self.as_array(dtype=dtype)
        return {
            int(idx): (int(r), int(g), int(b))
            for idx, (r, g, b) in enumerate(cmap_array)
        }

    def as_rasterio(self) -> dict[int, tuple[int, int, int, int]]:
        """Return the colormap as a mapping to 8-bit RGBA colors.

        This returns a colormap in the same format as rasterio's
        [`DatasetReader.colormap`][rasterio.io.DatasetReader.colormap] method.

        This is the same as
        [`Colormap.as_dict`][async_geotiff.colormap.Colormap.as_dict] with:

        - `dtype` set to `np.uint8`
        - an added alpha channel set to 255, **except** for the nodata value, if
          defined.

        Returns:
            Mapping of color index value (starting at 0) to RGBA color as a 4-element
                tuple.

        """
        cmap_array = self.as_array(dtype=np.uint8)
        cmap_dict: dict[int, tuple[int, int, int, int]] = {}

        for idx, (r, g, b) in enumerate(cmap_array):
            alpha = 255 if self._nodata is None or idx != self._nodata else 0
            cmap_dict[int(idx)] = (int(r), int(g), int(b), alpha)

        return cmap_dict
