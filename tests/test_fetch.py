"""Test fetching tiles from a GeoTIFF."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
from rasterio.windows import Window

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
async def test_fetch(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    file_name: str,
    variant: Variant,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)

    tile = await geotiff.fetch_tile(0, 0)

    window = Window(0, 0, geotiff.tile_width, geotiff.tile_height)
    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        rasterio_data = rasterio_ds.read(window=window)

    np.testing.assert_array_equal(tile.array.data, rasterio_data)
    assert tile.array.crs == geotiff.crs


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
async def test_fetch_overview(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    file_name: str,
    variant: Variant,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)
    overview = geotiff.overviews[0]

    tile = await overview.fetch_tile(0, 0)

    window = Window(0, 0, overview.tile_width, overview.tile_height)
    with load_rasterio(file_name, variant=variant, OVERVIEW_LEVEL=0) as rasterio_ds:
        rasterio_data = rasterio_ds.read(window=window)

    np.testing.assert_array_equal(tile.array.data, rasterio_data)
    assert tile.array.crs == geotiff.crs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "variant"),
    [
        ("maxar_opendata_yellowstone_visual", "vantor"),
    ],
)
async def test_mask(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    file_name: str,
    variant: Variant,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)

    tile = await geotiff.fetch_tile(0, 0)

    assert tile.array.mask is not None
    assert isinstance(tile.array.mask, np.ndarray)
    assert tile.array.mask.dtype == np.bool_
    assert tile.array.mask.shape == tile.array.data.shape[1:]

    window = Window(0, 0, geotiff.tile_width, geotiff.tile_height)
    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        mask = rasterio_ds.dataset_mask(window=window)

    np.testing.assert_array_equal(tile.array.mask, mask.astype(np.bool_))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "variant"),
    [
        ("maxar_opendata_yellowstone_visual", "vantor"),
    ],
)
async def test_mask_overview(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    file_name: str,
    variant: Variant,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)
    overview = geotiff.overviews[0]

    tile = await overview.fetch_tile(0, 0)

    assert tile.array.mask is not None
    assert isinstance(tile.array.mask, np.ndarray)
    assert tile.array.mask.dtype == np.bool_
    assert tile.array.mask.shape == tile.array.data.shape[1:]

    window = Window(0, 0, overview.tile_width, overview.tile_height)
    with load_rasterio(file_name, variant=variant, OVERVIEW_LEVEL=0) as rasterio_ds:
        mask = rasterio_ds.dataset_mask(window=window)

    np.testing.assert_array_equal(tile.array.mask, mask.astype(np.bool_))
