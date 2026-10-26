"""Build a projection (conversion) from GeoKeys by interpreting the CT table.

For a `ProjCoordTransGeoKey` code the table (`_crs_table`) says which PROJ
method applies and which GeoKeys hold each parameter, in libgeotiff's fallback
order. This module resolves the parameters, scales angular and linear values
to degrees and metres with the file's units, picks the method variant, and
builds the conversion with one of pyproj's typed classes, or, for methods
without one, from a PROJ string. Either way the result is checked against the
table so a silently dropped parameter is an error rather than a zero.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from pyproj import CRS
from pyproj.crs.coordinate_operation import (
    AlbersEqualAreaConversion,
    CoordinateOperation,
    EquidistantCylindricalConversion,
    HotineObliqueMercatorBConversion,
    LambertAzimuthalEqualAreaConversion,
    LambertConformalConic1SPConversion,
    LambertConformalConic2SPConversion,
    LambertCylindricalEqualAreaConversion,
    MercatorAConversion,
    MercatorBConversion,
    OrthographicConversion,
    PolarStereographicAConversion,
    PolarStereographicBConversion,
    SinusoidalConversion,
    StereographicConversion,
    TransverseMercatorConversion,
)

from async_geotiff._crs_geographic import DEGREES_PER_RADIAN, USER_DEFINED
from async_geotiff._crs_table import DEFAULT_AXES, Method, Variant, load_table

if TYPE_CHECKING:
    from collections.abc import Mapping

KEY_ACCESSORS: dict[str, str] = {
    "ProjStdParallel1": "proj_std_parallel1",
    "ProjStdParallel2": "proj_std_parallel2",
    "ProjNatOriginLong": "proj_nat_origin_long",
    "ProjNatOriginLat": "proj_nat_origin_lat",
    "ProjFalseEasting": "proj_false_easting",
    "ProjFalseNorthing": "proj_false_northing",
    "ProjFalseOriginLong": "proj_false_origin_long",
    "ProjFalseOriginLat": "proj_false_origin_lat",
    "ProjFalseOriginEasting": "proj_false_origin_easting",
    "ProjFalseOriginNorthing": "proj_false_origin_northing",
    "ProjCenterLong": "proj_center_long",
    "ProjCenterLat": "proj_center_lat",
    "ProjCenterEasting": "proj_center_easting",
    "ProjCenterNorthing": "proj_center_northing",
    "ProjScaleAtNatOrigin": "proj_scale_at_nat_origin",
    "ProjScaleAtCenter": "proj_scale_at_center",
    "ProjAzimuthAngle": "proj_azimuth_angle",
    "ProjStraightVertPoleLong": "proj_straight_vert_pole_long",
}
"""Table key names to async-tiff `GeoKeyDirectory` attributes.

`ProjRectifiedGridAngle` is deliberately absent: async-tiff 0.7 does not read
key 3096, and defaulting it silently would build a wrong Hotine Oblique
Mercator.
"""

_NATURAL_ORIGIN = {
    8801: "latitude_natural_origin",
    8802: "longitude_natural_origin",
    8805: "scale_factor_natural_origin",
    8806: "false_easting",
    8807: "false_northing",
}
_FALSE_ORIGIN_2SP = {
    8821: "latitude_false_origin",
    8822: "longitude_false_origin",
    8823: "latitude_first_parallel",
    8824: "latitude_second_parallel",
    8826: "easting_false_origin",
    8827: "northing_false_origin",
}
_ORIGIN_NO_SCALE = {
    code: keyword
    for code, keyword in _NATURAL_ORIGIN.items()
    if keyword != "scale_factor_natural_origin"
}

TYPED: dict[int | str, tuple[type[CoordinateOperation], dict[int, str]]] = {
    9807: (TransverseMercatorConversion, _NATURAL_ORIGIN),
    9804: (MercatorAConversion, _NATURAL_ORIGIN),
    9805: (
        MercatorBConversion,
        {
            8823: "latitude_first_parallel",
            8802: "longitude_natural_origin",
            8806: "false_easting",
            8807: "false_northing",
        },
    ),
    9801: (LambertConformalConic1SPConversion, _NATURAL_ORIGIN),
    9802: (LambertConformalConic2SPConversion, _FALSE_ORIGIN_2SP),
    9822: (AlbersEqualAreaConversion, _FALSE_ORIGIN_2SP),
    9820: (LambertAzimuthalEqualAreaConversion, _ORIGIN_NO_SCALE),
    9810: (PolarStereographicAConversion, _NATURAL_ORIGIN),
    9829: (
        PolarStereographicBConversion,
        {
            8832: "latitude_standard_parallel",
            8833: "longitude_origin",
            8806: "false_easting",
            8807: "false_northing",
        },
    ),
    "Stereographic": (StereographicConversion, _NATURAL_ORIGIN),
    9840: (OrthographicConversion, _ORIGIN_NO_SCALE),
    1028: (
        EquidistantCylindricalConversion,
        {8823: "latitude_first_parallel", **_ORIGIN_NO_SCALE},
    ),
    "Sinusoidal": (
        SinusoidalConversion,
        {
            8802: "longitude_natural_origin",
            8806: "false_easting",
            8807: "false_northing",
        },
    ),
    9835: (
        LambertCylindricalEqualAreaConversion,
        {
            8823: "latitude_first_parallel",
            8802: "longitude_natural_origin",
            8806: "false_easting",
            8807: "false_northing",
        },
    ),
    9815: (
        HotineObliqueMercatorBConversion,
        {
            8811: "latitude_projection_centre",
            8812: "longitude_projection_centre",
            8813: "azimuth_projection_centre",
            8814: "angle_from_rectified_to_skew_grid",
            8815: "scale_factor_projection_centre",
            8816: "easting_projection_centre",
            8817: "northing_projection_centre",
        },
    ),
}
"""Methods with a typed pyproj class, by EPSG code (or PROJ name when there is none).

A typo in a keyword here is a `TypeError`; units are implied; EPSG ids attached.
Every other method goes through a PROJ string (PROJ maps it to the EPSG method).
"""

PROJ_STRING_EXTRAS: dict[int | None, str] = {
    9812: "+no_uoff",  # Hotine Oblique Mercator (variant A)
    9808: "+axis=wsu",  # Transverse Mercator (South Orientated)
}
_PLACEHOLDER_ELLIPSOID = "+ellps=WGS84"
_POLAR_STEREOGRAPHIC = 15
_TOLERANCE = 1e-9


def resolve_parameters(
    method: Method,
    keys: Mapping[str, Any],
    *,
    to_degrees: float,
    to_metres: float,
) -> dict[str, float]:
    """Read every parameter any variant of `method` uses, in degrees and metres.

    The first key present in a parameter's list wins (a stored `0.0` is
    present); a parameter with no key present takes its default.
    """
    values: dict[str, float] = {}
    for parameter in method.all_parameters:
        value = parameter.default
        for key in parameter.keys:
            attribute = KEY_ACCESSORS.get(key)
            if attribute is None:
                raise ValueError(
                    f"GeoKey {key} is not readable by async-tiff, so "
                    f"{method.ct_name} ({method.code}) cannot be built",
                )
            raw = keys.get(attribute)
            if raw is not None:
                value = float(raw)
                break
        if parameter.kind == "angular":
            value *= to_degrees
        elif parameter.kind == "linear":
            value *= to_metres
        values[parameter.name] = value
    return values


def _rule_matches(
    rule: dict,
    values: Mapping[str, float],
    keys: Mapping[str, Any],
) -> bool:
    ((kind, body),) = rule.items()
    if kind == "any":
        return any(_rule_matches(r, values, keys) for r in body)
    if kind == "all":
        return all(_rule_matches(r, values, keys) for r in body)
    if kind == "present":
        return keys.get(KEY_ACCESSORS[body]) is not None
    value = values[body["param"]]
    if kind == "abs_value":
        value = abs(value)
    elif kind != "value":
        raise ValueError(f"Unknown rule in the CT table: {kind}")
    return math.isclose(value, body["equals"], abs_tol=_TOLERANCE)


def select_variant(
    method: Method,
    values: Mapping[str, float],
    keys: Mapping[str, Any],
) -> Variant:
    """Pick the first variant whose rule matches; the last variant has no rule."""
    for variant in method.variants:
        if variant.when is None or _rule_matches(variant.when, values, keys):
            if variant.unrepresentable:
                raise ValueError(
                    f"{method.ct_name} ({method.code}) with these parameters: "
                    f"{variant.unrepresentable}",
                )
            return variant
    raise ValueError(f"No variant of {method.ct_name} ({method.code}) matched")


def _proj_string(variant: Variant, values: Mapping[str, float]) -> str:
    parts = [f"+proj={variant.proj}"]
    parts.extend(
        f"+{parameter.proj}={values[parameter.name]!r}"
        for parameter in variant.parameters
    )
    extra = PROJ_STRING_EXTRAS.get(variant.method_epsg)
    if extra:
        parts.append(extra)
    parts.append(_PLACEHOLDER_ELLIPSOID)
    return " ".join(parts)


def build_conversion(
    variant: Variant,
    values: Mapping[str, float],
) -> CoordinateOperation:
    """Build the conversion for a variant from resolved parameter values."""
    typed = TYPED.get(variant.method_epsg or variant.method_name or "")
    if typed is None:
        # The ellipsoid is a placeholder: the conversion is re-attached to the
        # real geographic CRS by the caller and carries no ellipsoid of its own.
        conversion = CRS.from_proj4(_proj_string(variant, values)).coordinate_operation
        if conversion is None:
            raise ValueError(f"PROJ built no conversion for {variant.method_name}")
        return conversion
    cls, keywords = typed
    kwargs = {}
    for parameter in variant.parameters:
        if parameter.epsg not in keywords:
            raise ValueError(
                f"{variant.method_name}: no keyword for parameter {parameter.name}",
            )
        kwargs[keywords[parameter.epsg]] = values[parameter.name]
    return cls(**kwargs)


def validate_conversion(
    conversion: CoordinateOperation,
    variant: Variant,
    values: Mapping[str, float],
) -> None:
    """Check every table parameter made it into the conversion with its value."""
    by_code = {p.code: p for p in conversion.params if p.code}
    by_name = {p.name: p for p in conversion.params}
    for parameter in variant.parameters:
        found = (
            by_code.get(str(parameter.epsg))
            if parameter.epsg
            else by_name.get(parameter.name)
        )
        if found is None:
            raise ValueError(
                f"{variant.method_name}: parameter {parameter.name} was dropped",
            )
        actual = float(found.value)
        if parameter.kind in ("angular", "azimuth"):
            actual *= found.unit_conversion_factor * DEGREES_PER_RADIAN
        elif parameter.kind == "linear":
            actual *= found.unit_conversion_factor
        expected = values[parameter.name]
        if not math.isclose(actual, expected, rel_tol=_TOLERANCE, abs_tol=_TOLERANCE):
            raise ValueError(
                f"{variant.method_name}: parameter {parameter.name} is {actual}, "
                f"expected {expected}",
            )


def conversion_from_geo_keys(
    keys: Mapping[str, Any],
    *,
    to_degrees: float,
    to_metres: float,
) -> tuple[CoordinateOperation, tuple[str, str]]:
    """Build the conversion and the projected axis directions for a user-defined CRS."""
    ct = keys.get("proj_coord_trans")
    if ct is None:
        projection = keys.get("projection")
        if projection is not None and projection != USER_DEFINED:
            return CoordinateOperation.from_epsg(projection), DEFAULT_AXES
        raise ValueError(
            "A user-defined projected CRS needs ProjCoordTrans or Projection",
        )

    method = load_table().get(int(ct))
    if method is None:
        raise ValueError(f"Unknown coordinate transformation code: {ct}")
    if method.unsupported:
        raise ValueError(
            f"{method.ct_name} ({ct}) is not supported: {method.unsupported}",
        )

    values = resolve_parameters(
        method,
        keys,
        to_degrees=to_degrees,
        to_metres=to_metres,
    )
    variant = select_variant(method, values, keys)
    conversion = build_conversion(variant, values)
    validate_conversion(conversion, variant, values)

    axes = variant.axes
    if method.code == _POLAR_STEREOGRAPHIC:
        # PROJ's WKT1 Polar_Stereographic import sets both axes by the sign of
        # the latitude; GDAL's reading carries it (geotiff-test-data crs/README.md).
        latitude = values["Latitude of natural origin"]
        axes = ("south", "south") if latitude > 0 else ("north", "north")
    return conversion, axes
