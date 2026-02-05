from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .image_list import ALL_TEST_IMAGES

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("variant", "file_name"),
    ALL_TEST_IMAGES,
)
async def test_ifd_info(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    variant: str,
    file_name: str,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)

    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        assert rasterio_ds.bounds == geotiff.bounds
        assert rasterio_ds.count == geotiff.count
        assert rasterio_ds.dtypes[0] == geotiff.dtype
        assert rasterio_ds.height == geotiff.height
        assert rasterio_ds.nodata == geotiff.nodata
        assert rasterio_ds.res == geotiff.res
        assert rasterio_ds.shape == geotiff.shape
        assert rasterio_ds.transform == geotiff.transform
        assert rasterio_ds.width == geotiff.width


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
