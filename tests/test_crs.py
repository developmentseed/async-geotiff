from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from jsonschema import validate
from pyproj.datadir import get_data_dir

from async_geotiff._crs import projjson_from_geo_keys

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio, Variant


@pytest.fixture(scope="session")
def projjson_schema() -> dict:
    """Load the PROJJSON schema bundled with pyproj."""
    data_dir = get_data_dir()

    with open(f"{data_dir}/projjson.schema.json") as f:
        return json.load(f)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["file_name", "variant"],
    (
        ["float32_1band_lerc_block32", "rasterio"],
        ["uint16_1band_lzw_block128_predictor2", "rasterio"],
        ["uint8_rgb_deflate_block64_cog", "rasterio"],
        ["uint8_1band_deflate_block128_unaligned", "rasterio"],
        ["maxar_opendata_yellowstone_visual", "vantor"],
        ["nlcd_landcover", "nlcd"],
    ),
)
async def test_crs(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    file_name: str,
    variant: Variant,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)
    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        assert rasterio_ds.crs == geotiff.crs


@pytest.mark.asyncio
async def test_crs_custom(
    load_geotiff: LoadGeoTIFF, load_rasterio: LoadRasterio
) -> None:
    name = "nlcd_landcover"

    geotiff = await load_geotiff(name, variant="nlcd")
    with load_rasterio(name, variant="nlcd") as rasterio_ds:
        assert rasterio_ds.crs == geotiff.crs


@pytest.mark.asyncio
async def test_crs_custom_projjson_schema(
    load_geotiff: LoadGeoTIFF, projjson_schema: dict
) -> None:
    """Validate that a user-defined CRS produces valid PROJJSON."""
    name = "nlcd_landcover"

    geotiff = await load_geotiff(name, variant="nlcd")
    projjson = projjson_from_geo_keys(geotiff._gkd)

    validate(instance=projjson, schema=projjson_schema)
