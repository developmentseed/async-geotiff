from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from jsonschema import validate
from pyproj.datadir import get_data_dir

from async_geotiff._crs import projjson_from_geo_keys

from .image_list import ALL_TEST_IMAGES

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio


@pytest.fixture(scope="session")
def projjson_schema() -> dict:
    """Load the PROJJSON schema bundled with pyproj."""
    data_dir = Path(get_data_dir())
    with (data_dir / "projjson.schema.json").open() as f:
        return json.load(f)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "variant"),
    ALL_TEST_IMAGES,
)
async def test_crs(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    file_name: str,
    variant: str,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)
    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        assert rasterio_ds.crs == geotiff.crs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_name", "variant"),
    [("nlcd_landcover", "nlcd")],
)
async def test_crs_custom_projjson_schema(
    load_geotiff: LoadGeoTIFF,
    projjson_schema: dict,
    file_name: str,
    variant: str,
) -> None:
    """Validate that a user-defined CRS produces valid PROJJSON."""
    geotiff = await load_geotiff(file_name, variant=variant)
    projjson = projjson_from_geo_keys(geotiff._gkd)

    validate(instance=projjson, schema=projjson_schema)
