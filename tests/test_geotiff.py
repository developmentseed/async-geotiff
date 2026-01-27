from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

import pytest

from async_geotiff import GeoTIFF

if TYPE_CHECKING:
    from rasterio.io import DatasetReader


@pytest.mark.asyncio
async def test_height_width(
    load_geotiff: Callable[[str], Awaitable[GeoTIFF]],
    load_rasterio: Callable[[str], DatasetReader],
) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)
    with load_rasterio(name) as rasterio_ds:
        assert rasterio_ds.height == geotiff.height
        assert rasterio_ds.width == geotiff.width


@pytest.mark.asyncio
async def test_transform(
    load_geotiff: Callable[[str], Awaitable[GeoTIFF]],
    load_rasterio: Callable[[str], DatasetReader],
) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)
    with load_rasterio(name) as rasterio_ds:
        assert rasterio_ds.transform == geotiff.transform
