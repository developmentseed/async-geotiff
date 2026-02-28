from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from affine import Affine

from .image_list import ALL_COG_IMAGES

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio


@pytest.mark.asyncio
async def test_overview_transform(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)
    ovr = geotiff.overviews[0]

    with load_rasterio(name) as rasterio_ds:
        assert len(geotiff.overviews) == len(rasterio_ds.overviews(1))

        overviews = rasterio_ds.overviews(1)
        overview_level = overviews[0]
        decimated_transform = rasterio_ds.transform * Affine.scale(overview_level)

        assert ovr.transform == decimated_transform


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("variant", "file_name"),
    ALL_COG_IMAGES,
)
async def test_block_shapes_overview(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    variant: str,
    file_name: str,
) -> None:
    """Overview block_shapes matches rasterio's block_shapes at overview level 0."""
    geotiff = await load_geotiff(file_name, variant=variant)
    overview = geotiff.overviews[0]

    with load_rasterio(file_name, variant=variant, OVERVIEW_LEVEL=0) as rasterio_ds:
        assert overview.block_shapes == tuple(rasterio_ds.block_shapes)
