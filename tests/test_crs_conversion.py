"""Unit tests for the CT table interpreter.

Inputs are plain dicts with async-tiff's GeoKeyDirectory attribute names.
"""

from __future__ import annotations

import pytest

from async_geotiff._crs_conversion import (
    build_conversion,
    conversion_from_geo_keys,
    resolve_parameters,
    select_variant,
    validate_conversion,
)
from async_geotiff._crs_table import load_table

TABLE = load_table()
TM = TABLE[1]
POLAR = TABLE[15]


def test_resolve_fallback_order():
    values = resolve_parameters(
        TM,
        {"proj_center_lat": 5.0, "proj_center_long": 6.0},
        to_degrees=1.0,
        to_metres=1.0,
    )
    assert values["Latitude of natural origin"] == 5.0
    assert values["Longitude of natural origin"] == 6.0
    assert values["Scale factor at natural origin"] == 1.0
    assert values["False easting"] == 0.0


def test_resolve_zero_is_present():
    values = resolve_parameters(
        TM,
        {"proj_nat_origin_lat": 0.0, "proj_center_lat": 5.0},
        to_degrees=1.0,
        to_metres=1.0,
    )
    assert values["Latitude of natural origin"] == 0.0


def test_resolve_scales_units():
    values = resolve_parameters(
        TM,
        {
            "proj_nat_origin_lat": 52.0,
            "proj_false_easting": 984250.0,
            "proj_scale_at_nat_origin": 0.5,
        },
        to_degrees=0.9,
        to_metres=0.3048006096012192,
    )
    assert values["Latitude of natural origin"] == pytest.approx(46.8)
    assert values["False easting"] == pytest.approx(300000.0)
    assert values["Scale factor at natural origin"] == 0.5


def test_resolve_missing_accessor_raises():
    with pytest.raises(ValueError, match="ProjRectifiedGridAngle"):
        resolve_parameters(TABLE[3], {}, to_degrees=1.0, to_metres=1.0)


def test_mercator_variant_b_when_parallel_present():
    mercator = TABLE[7]
    keys = {"proj_std_parallel1": 30.0, "proj_nat_origin_long": 10.0}
    values = resolve_parameters(mercator, keys, to_degrees=1.0, to_metres=1.0)
    assert select_variant(mercator, values, keys).method_epsg == 9805
    keys = {"proj_scale_at_nat_origin": 0.98}
    values = resolve_parameters(mercator, keys, to_degrees=1.0, to_metres=1.0)
    assert select_variant(mercator, values, keys).method_epsg == 9804


def test_polar_rule_after_unit_scaling():
    def pick(lat: float, scale: float) -> int | None:
        keys = {"proj_nat_origin_lat": lat, "proj_scale_at_nat_origin": scale}
        values = resolve_parameters(POLAR, keys, to_degrees=0.9, to_metres=1.0)
        return select_variant(POLAR, values, keys).method_epsg

    assert pick(100.0, 1.0) == 9829  # 100 grad = 90 degrees, scale 1: variant B
    assert pick(100.0, 0.9) == 9810  # at the pole with a scale: variant A
    keys = {"proj_nat_origin_lat": 71.0, "proj_scale_at_nat_origin": 0.9}
    values = resolve_parameters(POLAR, keys, to_degrees=1.0, to_metres=1.0)
    with pytest.raises(ValueError, match="Polar_Stereographic"):
        select_variant(POLAR, values, keys)


def test_unsupported_ct_raises():
    with pytest.raises(ValueError, match="CT_TransvMercator_Modified_Alaska"):
        conversion_from_geo_keys({"proj_coord_trans": 2}, to_degrees=1.0, to_metres=1.0)


def test_typed_build_equals_proj_string():
    keys = {
        "proj_nat_origin_lat": 0.0,
        "proj_nat_origin_long": -3.5,
        "proj_scale_at_nat_origin": 0.9996,
        "proj_false_easting": 500000.0,
    }
    values = resolve_parameters(TM, keys, to_degrees=1.0, to_metres=1.0)
    typed = build_conversion(TM.variants[0], values)
    assert typed.method_code == "9807"
    assert {p.name: p.value for p in typed.params}[
        "Longitude of natural origin"
    ] == -3.5


def test_proj_string_build_laborde():
    laborde = TABLE[4]
    keys = {
        "proj_center_lat": -18.9,
        "proj_center_long": 46.43722917,
        "proj_azimuth_angle": 18.9,
        "proj_scale_at_center": 0.9995,
        "proj_false_easting": 400000.0,
        "proj_false_northing": 800000.0,
    }
    values = resolve_parameters(laborde, keys, to_degrees=1.0, to_metres=1.0)
    conversion = build_conversion(laborde.variants[0], values)
    assert conversion.method_code == "9813"
    assert {p.name: p.value for p in conversion.params}[
        "Azimuth at projection centre"
    ] == 18.9


def test_validate_catches_dropped_parameter():
    keys = {"proj_nat_origin_lat": 5.0, "proj_nat_origin_long": -3.5}
    values = resolve_parameters(TM, keys, to_degrees=1.0, to_metres=1.0)
    conversion = build_conversion(TM.variants[0], values)
    validate_conversion(conversion, TM.variants[0], values)
    values["Latitude of natural origin"] = 6.0
    with pytest.raises(ValueError, match="Latitude of natural origin"):
        validate_conversion(conversion, TM.variants[0], values)


def test_projection_code_path():
    conversion, axes = conversion_from_geo_keys(
        {"projection": 16033},
        to_degrees=1.0,
        to_metres=1.0,
    )
    assert conversion.method_code == "9807"
    assert {p.name: p.value for p in conversion.params}[
        "Longitude of natural origin"
    ] == 15.0
    assert axes == ("east", "north")


def test_polar_axes():
    north = {
        "proj_coord_trans": 15,
        "proj_nat_origin_lat": 90.0,
        "proj_scale_at_nat_origin": 0.994,
    }
    south = {
        "proj_coord_trans": 15,
        "proj_nat_origin_lat": -71.0,
        "proj_scale_at_nat_origin": 1.0,
    }
    assert conversion_from_geo_keys(north, to_degrees=1.0, to_metres=1.0)[1] == (
        "south",
        "south",
    )
    assert conversion_from_geo_keys(south, to_degrees=1.0, to_metres=1.0)[1] == (
        "north",
        "north",
    )


def test_south_orientated_axes():
    keys = {
        "proj_coord_trans": 27,
        "proj_nat_origin_long": 19.0,
        "proj_scale_at_nat_origin": 1.0,
    }
    conversion, axes = conversion_from_geo_keys(keys, to_degrees=1.0, to_metres=1.0)
    assert conversion.method_code == "9808"
    assert axes == ("west", "south")
