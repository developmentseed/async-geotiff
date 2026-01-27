from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from affine import Affine

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
