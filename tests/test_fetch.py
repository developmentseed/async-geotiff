"""Test fetching tiles from a GeoTIFF."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import pytest
from rasterio.windows import Window

from .image_list import (
    ALL_COG_IMAGES,
    ALL_DATA_IMAGES,
    ALL_MASKED_IMAGES,
)

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("variant", "file_name"),
    ALL_DATA_IMAGES,
)
async def test_fetch(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    variant: str,
    file_name: str,
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
    ("variant", "file_name"),
    ALL_COG_IMAGES,
)
async def test_fetch_overview(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    variant: str,
    file_name: str,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)
    overview = geotiff.overviews[0]

    tile = await overview.fetch_tile(0, 0)

    window = Window(0, 0, overview.tile_width, overview.tile_height)
    with load_rasterio(file_name, variant=variant, OVERVIEW_LEVEL=0) as rasterio_ds:
        rasterio_data = rasterio_ds.read(window=window, boundless=True)

    np.testing.assert_array_equal(tile.array.data, rasterio_data)
    assert tile.array.crs == geotiff.crs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("variant", "file_name"),
    ALL_MASKED_IMAGES,
)
async def test_mask(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    variant: str,
    file_name: str,
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
    ("variant", "file_name"),
    ALL_MASKED_IMAGES,
)
async def test_mask_overview(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    variant: str,
    file_name: str,
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


@pytest.mark.asyncio
async def test_fetch_tile_bounded(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
) -> None:
    """Edge tiles clipped to image bounds match rasterio's non-boundless read."""
    file_name = "uint8_1band_deflate_block128_unaligned"
    geotiff = await load_geotiff(file_name)

    tiles_across = math.ceil(geotiff.width / geotiff.tile_width)
    tiles_down = math.ceil(geotiff.height / geotiff.tile_height)

    # Test every edge tile (last column and last row)
    edge_tiles = [
        (x, y)
        for x in range(tiles_across)
        for y in range(tiles_down)
        if x == tiles_across - 1 or y == tiles_down - 1
    ]

    with load_rasterio(file_name) as rasterio_ds:
        for tx, ty in edge_tiles:
            tile = await geotiff.fetch_tile(tx, ty, boundless=False)

            expected_width = (
                min((tx + 1) * geotiff.tile_width, geotiff.width)
                - tx * geotiff.tile_width
            )
            expected_height = (
                min((ty + 1) * geotiff.tile_height, geotiff.height)
                - ty * geotiff.tile_height
            )

            assert tile.array.width == expected_width, f"tile ({tx},{ty}) width"
            assert tile.array.height == expected_height, f"tile ({tx},{ty}) height"

            window = Window(
                tx * geotiff.tile_width,
                ty * geotiff.tile_height,
                expected_width,
                expected_height,
            )
            rasterio_data = rasterio_ds.read(window=window, boundless=False)

            np.testing.assert_array_equal(
                tile.array.data,
                rasterio_data,
                err_msg=f"tile ({tx},{ty}) data mismatch",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("variant", "file_name"),
    ALL_DATA_IMAGES,
)
async def test_fetch_as_masked(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    variant: str,
    file_name: str,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)

    tile = await geotiff.fetch_tile(0, 0)
    masked_array = tile.array.as_masked()

    window = Window(0, 0, geotiff.tile_width, geotiff.tile_height)
    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        rasterio_data = rasterio_ds.read(window=window, masked=True)

    np.testing.assert_array_equal(masked_array.mask, rasterio_data.mask)
    np.testing.assert_array_equal(masked_array.data, rasterio_data.data)
    assert masked_array.shape == rasterio_data.shape
    assert masked_array.dtype == rasterio_data.dtype
