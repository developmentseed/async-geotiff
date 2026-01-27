from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest
from jsonschema import validate

from async_geotiff._crs import projjson_from_geo_keys

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio


@pytest.fixture(scope="session")
def projjson_schema() -> dict:
    """Load the PROJJSON schema bundled with pyproj."""
    import pyproj

    schema_path = os.path.join(
        os.path.dirname(pyproj.__file__),
        "proj_dir",
        "share",
        "proj",
        "projjson.schema.json",
    )
    with open(schema_path) as f:
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
