"""Test fetching tiles from a GeoTIFF."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio, Variant


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "variant"),
    [
        ("nlcd_landcover", "nlcd"),
    ],
)
async def test_colormap(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    file_name: str,
    variant: Variant,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)
    colormap = geotiff.colormap
    assert colormap is not None, "Expected colormap to be present."

    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        rasterio_colormap = rasterio_ds.colormap(1)

    assert rasterio_colormap == colormap.as_rasterio()

    cmap_array = colormap.as_array(dtype=np.uint8)
    assert cmap_array.dtype == np.uint8
    assert cmap_array.shape == (256, 3)
