"""Build the geographic side of a user-defined GeoTIFF CRS.

Follows libgeotiff's `GTIFGetDefn` and the GeogCS block of GDAL's
`GTIFGetOGISDefn`: units come from the unit codes or sizes, the ellipsoid
from its code or explicit axes, the datum from its code or the citation, and
the prime meridian from its code or longitude. Every function takes the
GeoKeys as a plain mapping with async-tiff's attribute names (`dict(gkd)`).

Names matter for CRS equality in PROJ and GDAL only for the datum and the
prime meridian, where a datum named exactly `unknown` matches any datum with
the same ellipsoid and prime meridian. GDAL names them from the citation it
wrote (`Datum = ...`, `Primem = ...`), so this module does the same.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, TypeGuard

from pyproj._crs import CoordinateSystem
from pyproj.crs import GeographicCRS
from pyproj.crs.coordinate_system import Cartesian2DCS, Ellipsoidal2DCS
from pyproj.crs.datum import (
    CustomDatum,
    CustomEllipsoid,
    CustomPrimeMeridian,
    Datum,
    Ellipsoid,
    PrimeMeridian,
)
from pyproj.database import get_units_map

if TYPE_CHECKING:
    from collections.abc import Mapping

USER_DEFINED = 32767
"""GeoKey value meaning "defined by other keys"."""

DEGREES_PER_RADIAN = 180.0 / math.pi
_SPHERE_TOLERANCE = 1e-10

_POLAR_PRESETS: dict[tuple[str, str], str] = {
    ("west", "south"): "WESTING_SOUTHING",
    ("south", "south"): "NORTH_POLE_EASTING_SOUTH_NORTHING_SOUTH",
    ("north", "north"): "SOUTH_POLE_EASTING_NORTH_NORTHING_NORTH",
}
_FOOT_PRESETS: dict[str, str] = {
    "foot": "EASTING_NORTHING_FT",
    "US survey foot": "EASTING_NORTHING_US_FT",
}


@dataclass(frozen=True)
class AngularUnit:
    """The geographic CRS's angular unit."""

    name: str
    to_degrees: float
    """Multiply a value in this unit to get degrees (libgeotiff UOMAngleInDegrees)."""
    conversion_factor: float
    """Radians per unit."""


@dataclass(frozen=True)
class LinearUnit:
    """The projected CRS's linear unit."""

    name: str
    to_metres: float
    """Multiply a value in this unit to get metres (libgeotiff UOMLengthInMeters)."""


DEGREE = AngularUnit(name="degree", to_degrees=1.0, conversion_factor=math.pi / 180)
METRE = LinearUnit(name="metre", to_metres=1.0)


def _is_code(value: object) -> TypeGuard[int]:
    """Whether a GeoKey holds an EPSG code rather than "user-defined" or nothing."""
    return isinstance(value, int) and value != USER_DEFINED


@lru_cache(maxsize=2)
def _units(category: str) -> dict[str, Any]:
    """EPSG units of one category, keyed by code (pyproj keys them by name)."""
    units = get_units_map(auth_name="EPSG", category=category).values()
    return {unit.code: unit for unit in units}


def angular_unit(keys: Mapping[str, Any]) -> AngularUnit:
    """`GeogAngularUnits`, or `GeogAngularUnitSize` in radians, default degree."""
    code = keys.get("geog_angular_units")
    if _is_code(code):
        unit = _units("angular")[str(code)]
        factor = float(unit.conv_factor)
        return AngularUnit(unit.name, factor * DEGREES_PER_RADIAN, factor)
    size = keys.get("geog_angular_unit_size")
    if size is not None:
        return AngularUnit("unknown", float(size) * DEGREES_PER_RADIAN, float(size))
    return DEGREE


def linear_unit(keys: Mapping[str, Any]) -> LinearUnit:
    """`ProjLinearUnits`, or `ProjLinearUnitSize` in metres, default metre."""
    code = keys.get("proj_linear_units")
    if _is_code(code):
        unit = _units("linear")[str(code)]
        return LinearUnit(unit.name, float(unit.conv_factor))
    size = keys.get("proj_linear_unit_size")
    if size is not None:
        return LinearUnit("unknown", float(size))
    return METRE


def parse_citation(citation: str | None) -> dict[str, str]:
    """Parse GDAL's `GCS Name = ...|Datum = ...|Primem = ...|` citation."""
    result: dict[str, str] = {}
    for part in (citation or "").split("|"):
        if "=" in part:
            key, value = part.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def ellipsoid(keys: Mapping[str, Any], citation: Mapping[str, str]) -> Ellipsoid:
    """Build the ellipsoid from its code, or from explicit axes."""
    code = keys.get("geog_ellipsoid")
    semi_major = keys.get("geog_semi_major_axis")
    semi_minor = keys.get("geog_semi_minor_axis")
    inv_flattening = keys.get("geog_inv_flattening")

    if _is_code(code) and semi_major is None:
        return Ellipsoid.from_epsg(code)
    if semi_major is None:
        raise ValueError(
            "A user-defined ellipsoid needs a semi-major axis (GeogSemiMajorAxis)",
        )

    name = citation.get("Ellipsoid")
    if name is None:
        name = Ellipsoid.from_epsg(code).name if _is_code(code) else "unknown"

    if inv_flattening:
        return CustomEllipsoid(
            name=name,
            semi_major_axis=semi_major,
            inverse_flattening=inv_flattening,
        )
    if semi_minor is not None and not math.isclose(
        semi_minor,
        semi_major,
        rel_tol=_SPHERE_TOLERANCE,
    ):
        return CustomEllipsoid(
            name=name,
            semi_major_axis=semi_major,
            semi_minor_axis=semi_minor,
        )
    return CustomEllipsoid(name=name, radius=semi_major)


def prime_meridian(
    keys: Mapping[str, Any],
    citation: Mapping[str, str],
    unit: AngularUnit,
) -> PrimeMeridian:
    """Build the prime meridian from its code, or from its longitude and unit."""
    code = keys.get("geog_prime_meridian")
    if _is_code(code):
        return PrimeMeridian.from_epsg(code)
    longitude = float(keys.get("geog_prime_meridian_long") or 0.0) * unit.to_degrees
    name = citation.get("Primem")
    if name is None:
        name = "Greenwich" if longitude == 0.0 else "unknown"
    return CustomPrimeMeridian(longitude=longitude, name=name)


def datum(
    keys: Mapping[str, Any],
    citation: Mapping[str, str],
    ellipsoid: Ellipsoid,
    prime_meridian: PrimeMeridian,
) -> Datum:
    """Build the datum from its code (which brings its ellipsoid), or user-defined."""
    code = keys.get("geog_geodetic_datum")
    if _is_code(code):
        return Datum.from_epsg(code)
    return CustomDatum(
        name=citation.get("Datum", "unknown"),
        ellipsoid=ellipsoid,
        prime_meridian=prime_meridian,
    )


def ellipsoidal_cs(unit: AngularUnit) -> CoordinateSystem:
    """Build a lon/lat coordinate system in the given angular unit."""
    if unit == DEGREE:
        return Ellipsoidal2DCS()
    json_unit = {
        "type": "AngularUnit",
        "name": unit.name,
        "conversion_factor": unit.conversion_factor,
    }
    return CoordinateSystem.from_json_dict(
        {
            "type": "CoordinateSystem",
            "subtype": "ellipsoidal",
            "axis": [
                {
                    "name": "Longitude",
                    "abbreviation": "lon",
                    "direction": "east",
                    "unit": json_unit,
                },
                {
                    "name": "Latitude",
                    "abbreviation": "lat",
                    "direction": "north",
                    "unit": json_unit,
                },
            ],
        },
    )


def cartesian_cs(unit: LinearUnit, axes: tuple[str, str]) -> CoordinateSystem:
    """Build a projected coordinate system in the given unit and axis directions."""
    if axes == ("east", "north"):
        if unit == METRE:
            return Cartesian2DCS()
        if unit.name in _FOOT_PRESETS:
            return Cartesian2DCS(axis=_FOOT_PRESETS[unit.name])
    elif unit == METRE and axes in _POLAR_PRESETS:
        return Cartesian2DCS(axis=_POLAR_PRESETS[axes])
    json_unit = {
        "type": "LinearUnit",
        "name": unit.name,
        "conversion_factor": unit.to_metres,
    }
    return CoordinateSystem.from_json_dict(
        {
            "type": "CoordinateSystem",
            "subtype": "Cartesian",
            "axis": [
                {
                    "name": "Easting",
                    "abbreviation": "E",
                    "direction": axes[0],
                    "unit": json_unit,
                },
                {
                    "name": "Northing",
                    "abbreviation": "N",
                    "direction": axes[1],
                    "unit": json_unit,
                },
            ],
        },
    )


def geographic_crs(keys: Mapping[str, Any]) -> tuple[GeographicCRS, AngularUnit]:
    """Build a user-defined geographic CRS and return it with its angular unit."""
    citation = parse_citation(keys.get("geog_citation"))
    unit = angular_unit(keys)
    pm = prime_meridian(keys, citation, unit)
    datum_ = datum(keys, citation, ellipsoid(keys, citation), pm)
    crs = GeographicCRS(
        name=citation.get("GCS Name", "unknown"),
        datum=datum_,
        ellipsoidal_cs=ellipsoidal_cs(unit),
    )
    return crs, unit
