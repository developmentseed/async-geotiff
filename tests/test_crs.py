from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from jsonschema import validate
from pyproj import Transformer
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
    ("variant", "file_name"),
    ALL_TEST_IMAGES,
)
async def test_crs(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    variant: str,
    file_name: str,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)
    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        assert rasterio_ds.crs == geotiff.crs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("variant", "file_name"),
    [
        ("nlcd", "nlcd_landcover"),
        ("source-coop-vizzuality", "hfp_2017_100m_v1-2_cog"),
        ("source-coop-dataforcanada", "O2308000_7586000_cog"),
    ],
)
async def test_crs_custom_projjson_schema(
    load_geotiff: LoadGeoTIFF,
    projjson_schema: dict,
    variant: str,
    file_name: str,
) -> None:
    """Validate that a user-defined CRS produces valid PROJJSON."""
    geotiff = await load_geotiff(file_name, variant=variant)
    projjson = projjson_from_geo_keys(geotiff._gkd)

    validate(instance=projjson, schema=projjson_schema)


class _GeoKeys:
    """Stand-in for `async_tiff.GeoKeyDirectory`; keys that aren't set are None."""

    def __init__(self, **keys: object) -> None:
        self.__dict__.update(keys)

    def __getattr__(self, name: str) -> None:
        return None


NEW_BRUNSWICK_STEREOGRAPHIC_PARAMETERS = [
    {"name": "Latitude of natural origin", "value": 46.5, "unit": "degree"},
    {"name": "Longitude of natural origin", "value": -66.5, "unit": "degree"},
    {"name": "Scale factor at natural origin", "value": 0.999912, "unit": "unity"},
    {"name": "False easting", "value": 2500000.0, "unit": "metre"},
    {"name": "False northing", "value": 7500000.0, "unit": "metre"},
]
"""New Brunswick Stereographic (equivalent to EPSG:2953) conversion parameters."""


@pytest.mark.asyncio
async def test_oblique_stereographic_origin(load_geotiff: LoadGeoTIFF) -> None:
    """Read the Oblique Stereographic origin from the ProjNatOrigin* keys.

    https://github.com/source-cooperative/cog-viewer/issues/40
    """
    geotiff = await load_geotiff(
        "O2308000_7586000_cog",
        variant="source-coop-dataforcanada",
    )
    projjson = projjson_from_geo_keys(geotiff._gkd)

    assert projjson["conversion"]["method"] == {"name": "Oblique Stereographic"}
    assert (
        projjson["conversion"]["parameters"] == NEW_BRUNSWICK_STEREOGRAPHIC_PARAMETERS
    )


@pytest.mark.asyncio
async def test_stereographic_scale_factor(load_geotiff: LoadGeoTIFF) -> None:
    """Read the Stereographic scale factor from ProjScaleAtNatOriginGeoKey.

    GDAL writes CT_Stereographic with the origin in ProjCenter{Lat,Long} but the
    scale factor in ProjScaleAtNatOrigin.
    """
    geotiff = await load_geotiff(
        "O2308000_7586000_cog",
        variant="source-coop-dataforcanada",
    )
    keys = {key: geotiff._gkd[key] for key in geotiff._gkd}
    keys["proj_coord_trans"] = 14
    keys["proj_center_lat"] = keys.pop("proj_nat_origin_lat")
    keys["proj_center_long"] = keys.pop("proj_nat_origin_long")
    projjson = projjson_from_geo_keys(_GeoKeys(**keys))

    assert projjson["conversion"]["method"] == {"name": "Stereographic"}
    assert (
        projjson["conversion"]["parameters"] == NEW_BRUNSWICK_STEREOGRAPHIC_PARAMETERS
    )


@pytest.mark.asyncio
async def test_crs_user_defined_oblique_stereographic(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
) -> None:
    """Parse a user-defined CRS that pyproj accepts and that GDAL agrees with.

    GDAL identifies this CRS by name as EPSG:2953, whose axes are
    northing/easting, so compare positions rather than the CRS objects.
    """
    variant = "source-coop-dataforcanada"
    geotiff = await load_geotiff("O2308000_7586000_cog", variant=variant)
    with load_rasterio("O2308000_7586000_cog", variant=variant) as rasterio_ds:
        x, y = rasterio_ds.transform * (0, 0)
        expected = Transformer.from_crs(
            rasterio_ds.crs,
            "EPSG:4326",
            always_xy=True,
        ).transform(x, y)

    actual = Transformer.from_crs(
        geotiff.crs,
        "EPSG:4326",
        always_xy=True,
    ).transform(x, y)
    assert actual == pytest.approx(expected, abs=1e-9)
