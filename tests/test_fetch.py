"""Test fetching tiles from a GeoTIFF."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
from rasterio.windows import Window

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio


@pytest.mark.asyncio
async def test_fetch(load_geotiff: LoadGeoTIFF, load_rasterio: LoadRasterio) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)

    tile = await geotiff.fetch_tile(0, 0)

    window = Window(0, 0, geotiff.tile_width, geotiff.tile_height)
    with load_rasterio(name) as rasterio_ds:
        rasterio_data = rasterio_ds.read(window=window)

    np.testing.assert_array_equal(tile.data, rasterio_data)
    assert tile.crs == geotiff.crs


@pytest.mark.asyncio
async def test_fetch_overview(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)
    overview = geotiff.overviews[0]

    tile = await overview.fetch_tile(0, 0)

    window = Window(0, 0, overview.tile_width, overview.tile_height)
    with load_rasterio(name, OVERVIEW_LEVEL=0) as rasterio_ds:
        rasterio_data = rasterio_ds.read(window=window)

    np.testing.assert_array_equal(tile.data, rasterio_data)
    assert tile.crs == geotiff.crs
