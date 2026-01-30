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
        ("uint8_rgb_deflate_block64_cog", "rasterio"),
        ("uint8_1band_deflate_block128_unaligned", "rasterio"),
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

    np.testing.assert_array_equal(tile.data, rasterio_data)
    assert tile.crs == geotiff.crs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "variant"),
    [
        # TODO: support LERC
        # https://github.com/developmentseed/async-geotiff/issues/34
        # ("float32_1band_lerc_block32", "rasterio"), # noqa: ERA001
        ("uint16_1band_lzw_block128_predictor2", "rasterio"),
        ("uint8_rgb_deflate_block64_cog", "rasterio"),
        ("uint8_1band_deflate_block128_unaligned", "rasterio"),
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

    np.testing.assert_array_equal(tile.data, rasterio_data)
    assert tile.crs == geotiff.crs


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

    assert tile.mask is not None
    assert isinstance(tile.mask, np.ndarray)
    assert tile.mask.dtype == np.bool_
    assert tile.mask.shape == tile.data.shape[1:]

    window = Window(0, 0, geotiff.tile_width, geotiff.tile_height)
    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        mask = rasterio_ds.dataset_mask(window=window)

    np.testing.assert_array_equal(tile.mask, mask.astype(np.bool_))


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

    assert tile.mask is not None
    assert isinstance(tile.mask, np.ndarray)
    assert tile.mask.dtype == np.bool_
    assert tile.mask.shape == tile.data.shape[1:]

    window = Window(0, 0, overview.tile_width, overview.tile_height)
    with load_rasterio(file_name, variant=variant, OVERVIEW_LEVEL=0) as rasterio_ds:
        mask = rasterio_ds.dataset_mask(window=window)

    np.testing.assert_array_equal(tile.mask, mask.astype(np.bool_))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "variant"),
    [
        ("uint16_1band_lzw_block128_predictor2", "rasterio"),
        ("uint8_rgb_deflate_block64_cog", "rasterio"),
        ("uint8_1band_deflate_block128_unaligned", "rasterio"),
        ("nlcd_landcover", "nlcd"),
    ],
)
async def test_read_single_tile(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    file_name: str,
    variant: Variant,
) -> None:
    """Test reading a window that fits within a single tile."""
    geotiff = await load_geotiff(file_name, variant=variant)

    # Read a small region within the first tile
    window = ((0, 32), (0, 32))
    result = await geotiff.read(window)

    rasterio_window = Window(0, 0, 32, 32)
    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        rasterio_data = rasterio_ds.read(window=rasterio_window)

    np.testing.assert_array_equal(result.data, rasterio_data)
    assert result.width == 32
    assert result.height == 32
    assert result.crs == geotiff.crs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "variant"),
    [
        ("uint16_1band_lzw_block128_predictor2", "rasterio"),
        ("uint8_rgb_deflate_block64_cog", "rasterio"),
        ("uint8_1band_deflate_block128_unaligned", "rasterio"),
        ("nlcd_landcover", "nlcd"),
    ],
)
async def test_read_spanning_tiles(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    file_name: str,
    variant: Variant,
) -> None:
    """Test reading a window that spans multiple tiles."""
    geotiff = await load_geotiff(file_name, variant=variant)

    # Read a region that spans tile boundaries
    tile_width = geotiff.tile_width
    tile_height = geotiff.tile_height

    # Start in middle of first tile, end in middle of second tile
    col_start = tile_width // 2
    col_stop = min(tile_width + tile_width // 2, geotiff.width)
    row_start = tile_height // 2
    row_stop = min(tile_height + tile_height // 2, geotiff.height)

    window = ((row_start, row_stop), (col_start, col_stop))
    result = await geotiff.read(window)

    rasterio_window = Window(
        col_start,
        row_start,
        col_stop - col_start,
        row_stop - row_start,
    )
    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        rasterio_data = rasterio_ds.read(window=rasterio_window)

    np.testing.assert_array_equal(result.data, rasterio_data)
    assert result.width == col_stop - col_start
    assert result.height == row_stop - row_start


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "variant"),
    [
        ("uint8_rgb_deflate_block64_cog", "rasterio"),
    ],
)
async def test_read_overview(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    file_name: str,
    variant: Variant,
) -> None:
    """Test reading from an overview level."""
    geotiff = await load_geotiff(file_name, variant=variant)
    overview = geotiff.overviews[0]

    window = ((0, 32), (0, 32))
    result = await overview.read(window)

    rasterio_window = Window(0, 0, 32, 32)
    with load_rasterio(file_name, variant=variant, OVERVIEW_LEVEL=0) as rasterio_ds:
        rasterio_data = rasterio_ds.read(window=rasterio_window)

    np.testing.assert_array_equal(result.data, rasterio_data)
    assert result.width == 32
    assert result.height == 32


@pytest.mark.asyncio
async def test_read_bounds_validation(
    load_geotiff: LoadGeoTIFF,
) -> None:
    """Test that read raises IndexError for out-of-bounds windows."""
    geotiff = await load_geotiff("uint8_rgb_deflate_block64_cog", variant="rasterio")

    # Negative start index
    with pytest.raises(IndexError, match="non-negative"):
        await geotiff.read(((-1, 10), (0, 10)))

    # Window extends past image bounds
    with pytest.raises(IndexError, match="outside image bounds"):
        await geotiff.read(((0, geotiff.height + 1), (0, 10)))

    # Zero-size window
    with pytest.raises(IndexError, match="positive dimensions"):
        await geotiff.read(((10, 10), (0, 10)))
