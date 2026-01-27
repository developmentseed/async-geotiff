from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from jsonschema import validate
from pyproj.datadir import get_data_dir

from async_geotiff._crs import projjson_from_geo_keys

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio


@pytest.fixture(scope="session")
def projjson_schema() -> dict:
    """Load the PROJJSON schema bundled with pyproj."""
    data_dir = get_data_dir()

    with open(f"{data_dir}/projjson.schema.json") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_crs(load_geotiff: LoadGeoTIFF, load_rasterio: LoadRasterio) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)
    with load_rasterio(name) as rasterio_ds:
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
