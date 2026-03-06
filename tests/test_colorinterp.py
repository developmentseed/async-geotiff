"""Test fetching tiles from a GeoTIFF."""

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
async def test_colorinterp(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    variant: str,
    file_name: str,
) -> None:
    if (variant == "vantor" and file_name == "maxar_opendata_yellowstone_visual") or (
        variant == "rio-tiler" and file_name == "cog_rgb_with_stats"
    ):
        pytest.skip("Should our colorinterp map YCbCr to RGB?")

    geotiff = await load_geotiff(file_name, variant=variant)
    colorinterp = geotiff.colorinterp
    assert colorinterp is not None, "Expected color interpretation to be present."

    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        rasterio_colorinterp = rasterio_ds.colorinterp

    assert rasterio_colorinterp == colorinterp
