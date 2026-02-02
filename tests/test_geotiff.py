from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio, Variant


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "variant"),
    [
        # TODO: support LERC
        # https://github.com/developmentseed/async-geotiff/issues/34
        # ("float32_1band_lerc_block32", "rasterio"), # noqa: ERA001
        ("uint16_1band_lzw_block128_predictor2", "rasterio"),
        ("uint8_1band_deflate_block128_unaligned", "rasterio"),
        ("uint8_rgb_deflate_block64_cog", "rasterio"),
        ("uint8_rgb_webp_block64_cog", "rasterio"),
        ("uint8_rgba_webp_block64_cog", "rasterio"),
        # TODO: debug incorrect data length
        # https://github.com/developmentseed/async-tiff/issues/202
        # ("maxar_opendata_yellowstone_visual", "vantor"), # noqa: ERA001
        ("nlcd_landcover", "nlcd"),
    ],
)
async def test_ifd_info(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    file_name: str,
    variant: Variant,
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
