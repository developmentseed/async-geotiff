"""Unit tests for the user-defined geographic CRS builder.

Inputs are plain dicts with async-tiff's GeoKeyDirectory attribute names.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from pyproj import CRS

from async_geotiff._crs_geographic import (
    AngularUnit,
    LinearUnit,
    angular_unit,
    cartesian_cs,
    datum,
    ellipsoid,
    ellipsoidal_cs,
    geographic_crs,
    linear_unit,
    parse_citation,
    prime_meridian,
)

MANIFEST = json.loads(
    (
        Path(__file__).parent.parent / "fixtures/geotiff-test-data/crs/manifest.json"
    ).read_text(),
)
ROWS = {row["name"]: row for row in MANIFEST["cases"]}
GRAD = AngularUnit(name="grad", to_degrees=0.9, conversion_factor=math.pi / 200)
DEGREE = AngularUnit(name="degree", to_degrees=1.0, conversion_factor=math.pi / 180)


def test_angular_unit_grad():
    unit = angular_unit({"geog_angular_units": 9105})
    assert unit.name == "grad"
    assert unit.to_degrees == pytest.approx(0.9)


def test_angular_unit_default_degree():
    assert angular_unit({}).to_degrees == 1.0


def test_angular_unit_degree_code_is_exact():
    """libgeotiff treats 9102 as exactly 1.0; pyproj's factor is a hair off."""
    assert angular_unit({"geog_angular_units": 9102}) == DEGREE


def test_angular_unit_zero_factor_raises():
    with pytest.raises(ValueError, match="GeogAngularUnitSize"):
        angular_unit({"geog_angular_units": 32767, "geog_angular_unit_size": 0.0})
    # pyproj reports no conversion factor for some sexagesimal EPSG codes.
    with pytest.raises(ValueError, match="9107"):
        angular_unit({"geog_angular_units": 9107})


def test_angular_unit_size():
    unit = angular_unit(
        {"geog_angular_units": 32767, "geog_angular_unit_size": 0.015707963267949},
    )
    assert unit.name == "unknown"
    assert unit.to_degrees == pytest.approx(0.9)


def test_linear_unit_us_ft():
    unit = linear_unit({"proj_linear_units": 9003})
    assert unit.name == "US survey foot"
    assert unit.to_metres == pytest.approx(0.3048006096012192)


def test_linear_unit_size():
    unit = linear_unit({"proj_linear_units": 32767, "proj_linear_unit_size": 0.5})
    assert unit.to_metres == 0.5


def test_linear_unit_default_metre():
    assert linear_unit({}) == LinearUnit(name="metre", to_metres=1.0)


def test_parse_citation():
    assert parse_citation("GCS Name = unknown|Datum = D|Primem = Paris|") == {
        "GCS Name": "unknown",
        "Datum": "D",
        "Primem": "Paris",
    }
    assert parse_citation(None) == {}


def test_ellipsoid_from_code():
    e = ellipsoid({"geog_ellipsoid": 7030}, {})
    assert e.name == "WGS 84"
    assert e.semi_major_metre == 6378137.0


def test_ellipsoid_from_axes():
    e = ellipsoid(
        {
            "geog_ellipsoid": 32767,
            "geog_semi_major_axis": 6377397.155,
            "geog_inv_flattening": 299.1528128,
        },
        {"Ellipsoid": "Bessel 1841"},
    )
    assert e.name == "Bessel 1841"
    assert e.inverse_flattening == pytest.approx(299.1528128)


def test_ellipsoid_sphere():
    e = ellipsoid(
        {"geog_semi_major_axis": 6371007.181, "geog_semi_minor_axis": 6371007.181},
        {},
    )
    assert e.to_json_dict()["radius"] == 6371007.181


def test_ellipsoid_code_with_only_semi_major_keeps_flattening():
    """libgeotiff seeds the axes from the code and overrides only what keys give."""
    e = ellipsoid({"geog_ellipsoid": 7030, "geog_semi_major_axis": 6378137.0}, {})
    assert e.name == "WGS 84"
    assert e.inverse_flattening == pytest.approx(298.257223563)


def test_ellipsoid_without_shape_raises():
    with pytest.raises(ValueError, match="GeogInvFlattening or GeogSemiMinorAxis"):
        ellipsoid({"geog_semi_major_axis": 6378137.0}, {})


def test_datum_from_code_without_ellipsoid_keys():
    """A coded datum implies its ellipsoid; GDAL just happens to write the axes too."""
    crs, _ = geographic_crs({"geographic_type": 32767, "geog_geodetic_datum": 6326})
    assert crs.ellipsoid is not None
    assert crs.ellipsoid.name == "WGS 84"
    assert "World Geodetic System 1984" in crs.datum.name


def test_ellipsoid_requires_semi_major():
    with pytest.raises(ValueError, match="semi-major"):
        ellipsoid({"geog_ellipsoid": 32767}, {})


def test_prime_meridian_from_code():
    pm = prime_meridian({"geog_prime_meridian": 8903}, {}, DEGREE)
    assert pm.name == "Paris"
    assert pm.longitude * pm.unit_conversion_factor * 180 / math.pi == pytest.approx(
        2.33722917,
    )


def test_prime_meridian_in_grads():
    pm = prime_meridian({"geog_prime_meridian_long": 2.0}, {"Primem": "x"}, GRAD)
    assert pm.name == "x"
    assert pm.longitude == pytest.approx(1.8)


def test_prime_meridian_default_greenwich():
    pm = prime_meridian({}, {}, DEGREE)
    assert pm.name == "Greenwich"
    assert pm.longitude == 0.0


def test_datum_from_code_ignores_axes():
    e = ellipsoid({"geog_semi_major_axis": 1.0, "geog_inv_flattening": 300.0}, {})
    d = datum({"geog_geodetic_datum": 6267}, {}, e, prime_meridian({}, {}, DEGREE))
    assert d.name == "North American Datum 1927"


def test_datum_name_from_citation():
    e = ellipsoid({"geog_ellipsoid": 7030}, {})
    d = datum({}, {"Datum": "My datum"}, e, prime_meridian({}, {}, DEGREE))
    assert d.name == "My datum"
    assert d.ellipsoid.name == "WGS 84"


def test_datum_name_unknown():
    e = ellipsoid({"geog_ellipsoid": 7030}, {})
    assert datum({}, {}, e, prime_meridian({}, {}, DEGREE)).name == "unknown"


def test_ellipsoidal_cs_units():
    assert ellipsoidal_cs(DEGREE).to_json_dict()["axis"][0]["unit"] == "degree"
    unit = ellipsoidal_cs(GRAD).to_json_dict()["axis"][0]["unit"]
    assert unit["name"] == "grad"
    assert unit["conversion_factor"] == pytest.approx(math.pi / 200)


def test_cartesian_cs_polar():
    cs = cartesian_cs(LinearUnit(name="metre", to_metres=1.0), ("south", "south"))
    assert [a["direction"] for a in cs.to_json_dict()["axis"]] == ["south", "south"]


def test_cartesian_cs_feet():
    cs = cartesian_cs(linear_unit({"proj_linear_units": 9003}), ("east", "north"))
    assert cs.to_json_dict()["axis"][0]["unit"]["name"] == "US survey foot"


def test_cartesian_cs_user_defined_unit():
    cs = cartesian_cs(LinearUnit(name="unknown", to_metres=0.5), ("east", "north"))
    assert cs.to_json_dict()["axis"][0]["unit"]["conversion_factor"] == 0.5


@pytest.mark.parametrize("name", ["geog_grad_wkt", "longlat_grs80", "geog_sphere"])
def test_geographic_crs_equals_gdal(name: str):
    row = ROWS[name]
    keys = _async_tiff_keys(row["geokeys"])
    crs, unit = geographic_crs(keys)
    expected = CRS.from_json_dict(row["gdal"]["projjson"])
    assert expected.equals(crs, ignore_axis_order=True), crs.to_wkt(pretty=True)
    assert unit.to_degrees == pytest.approx(0.9 if name == "geog_grad_wkt" else 1.0)


def _async_tiff_keys(geokeys: dict) -> dict:
    """Spec key names (manifest) to async-tiff attribute names."""
    names = {
        "GeographicType": "geographic_type",
        "GeogCitation": "geog_citation",
        "GeogGeodeticDatum": "geog_geodetic_datum",
        "GeogPrimeMeridian": "geog_prime_meridian",
        "GeogAngularUnits": "geog_angular_units",
        "GeogAngularUnitSize": "geog_angular_unit_size",
        "GeogEllipsoid": "geog_ellipsoid",
        "GeogSemiMajorAxis": "geog_semi_major_axis",
        "GeogSemiMinorAxis": "geog_semi_minor_axis",
        "GeogInvFlattening": "geog_inv_flattening",
        "GeogPrimeMeridianLong": "geog_prime_meridian_long",
    }
    return {names[k]: v for k, v in geokeys.items() if k in names}
