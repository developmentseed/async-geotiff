from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

import pytest

from async_geotiff import GeoTIFF

if TYPE_CHECKING:
    from rasterio.io import DatasetReader

    LoadGeoTIFF = Callable[[str], Awaitable[GeoTIFF]]
    LoadRasterio = Callable[[str], DatasetReader]


@pytest.mark.asyncio
async def test_crs(load_geotiff: LoadGeoTIFF, load_rasterio: LoadRasterio) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)
    with load_rasterio(name) as rasterio_ds:
        assert rasterio_ds.crs == geotiff.crs
