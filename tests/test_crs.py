from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio


@pytest.mark.asyncio
async def test_crs(load_geotiff: LoadGeoTIFF, load_rasterio: LoadRasterio) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)
    with load_rasterio(name) as rasterio_ds:
        assert rasterio_ds.crs == geotiff.crs


@pytest.mark.asyncio
async def test_crs_custom(
    load_geotiff: LoadGeoTIFF, load_rasterio: LoadRasterio
) -> None:
    name = "nlcd_landcover"

    geotiff = await load_geotiff(name, variant="nlcd")
    with load_rasterio(name, variant="nlcd") as rasterio_ds:
        assert rasterio_ds.crs == geotiff.crs
