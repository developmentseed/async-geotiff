from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

import pytest

from async_geotiff import GeoTIFF

if TYPE_CHECKING:
    from rasterio.io import DatasetReader

    LoadGeoTIFF = Callable[[str], Awaitable[GeoTIFF]]
    LoadRasterio = Callable[[str], DatasetReader]


@pytest.mark.asyncio
async def test_bounds(load_geotiff: LoadGeoTIFF, load_rasterio: LoadRasterio) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)
    with load_rasterio(name) as rasterio_ds:
        assert rasterio_ds.bounds == geotiff.bounds


@pytest.mark.asyncio
async def test_transform(
    load_geotiff: LoadGeoTIFF, load_rasterio: LoadRasterio
) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)
    with load_rasterio(name) as rasterio_ds:
        assert rasterio_ds.transform == geotiff.transform
        assert rasterio_ds.height == geotiff.height
        assert rasterio_ds.width == geotiff.width
        assert rasterio_ds.shape == geotiff.shape
        assert rasterio_ds.res == geotiff.res


@pytest.mark.asyncio
async def test_xy(load_geotiff: LoadGeoTIFF, load_rasterio: LoadRasterio) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)

    x = geotiff.width // 2
    y = geotiff.height // 2

    with load_rasterio(name) as rasterio_ds:
        for offset in ["center", "ul", "ur", "ll", "lr"]:
            assert rasterio_ds.xy(
                x,
                y,
                offset=offset,
            ) == geotiff.xy(
                x,
                y,
                offset=offset,
            )
