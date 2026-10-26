"""Parse a pyproj CRS from a GeoKeyDirectory.

In the simple case, a GeoTIFF names its CRS by EPSG code, which goes straight
to `pyproj.CRS.from_epsg`.

In the general case the GeoKeys describe a user-defined CRS. The geographic
side (units, ellipsoid, datum, prime meridian) is built by `_crs_geographic`
and the projection by `_crs_conversion`, which interprets the GeoTIFF
coordinate-transformation table shared through geotiff-test-data. Both follow
libgeotiff and GDAL, and the result is tested against GDAL's own reading of
every fixture in that corpus (`tests/test_crs_conformance.py`).

GDAL also writes an `ESRI PE String = <WKT>` citation for projections GeoTIFF
has no code for; that WKT is parsed directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyproj import CRS
from pyproj.crs import ProjectedCRS

from async_geotiff._crs_conversion import conversion_from_geo_keys
from async_geotiff._crs_geographic import (
    USER_DEFINED,
    angular_unit,
    cartesian_cs,
    geographic_crs,
    linear_unit,
)

if TYPE_CHECKING:
    from async_tiff import GeoKeyDirectory

MODEL_TYPE_PROJECTED = 1
"""GeoTIFF model type constant for projected coordinate systems."""

MODEL_TYPE_GEOGRAPHIC = 2
"""GeoTIFF model type constant for geographic coordinate systems."""

USER_DEFINED_CRS = USER_DEFINED
"""Sentinel value for user-defined CRS."""

# The two "public" functions of this module
__all__ = ["crs_from_geo_keys", "projjson_from_geo_keys"]


def crs_from_geo_keys(gkd: GeoKeyDirectory) -> CRS:
    """Parse a pyproj CRS from a GeoKeyDirectory.

    Supports both EPSG-coded and user-defined CRSes.
    """
    model_type = gkd.model_type

    if model_type == MODEL_TYPE_PROJECTED:
        return _projected_crs(gkd)

    if model_type == MODEL_TYPE_GEOGRAPHIC:
        return _geographic_crs(gkd)

    if model_type == USER_DEFINED_CRS:
        wkt = _esri_pe_string(gkd)
        if wkt is not None:
            return CRS.from_wkt(wkt)

    raise ValueError(f"Unsupported GeoTIFF model type: {model_type}")


def projjson_from_geo_keys(gkd: GeoKeyDirectory) -> dict:
    """Build a PROJJSON dict from a GeoKeyDirectory.

    For EPSG-coded CRSes this is the canonical PROJJSON of that code; for
    user-defined CRSes it is PROJ's own serialization of the CRS built from
    the GeoKeys.
    """
    return crs_from_geo_keys(gkd).to_json_dict()


_ESRI_PE_STRING_PREFIX = "ESRI PE String ="


def _esri_pe_string(gkd: GeoKeyDirectory) -> str | None:
    """Extract a WKT string from an ``ESRI PE String = ...`` proj_citation.

    GDAL stores the full ESRI WKT here when the GeoTIFF has no matching
    EPSG code; pyproj parses it directly via :meth:`CRS.from_wkt`.
    """
    # The GeoTIFF spec defines no text-based CRS encoding; ``ESRI PE String =``
    # is a de facto ArcGIS convention that GDAL/PROJ also read
    citation = gkd.proj_citation
    if citation is None or _ESRI_PE_STRING_PREFIX not in citation:
        return None
    return citation.split(_ESRI_PE_STRING_PREFIX, 1)[1].strip() or None


def _geographic_crs(gkd: GeoKeyDirectory) -> CRS:
    """Build the geographic CRS, by EPSG code or from the Geog* keys."""
    code = gkd.geographic_type
    if code is not None and code != USER_DEFINED_CRS:
        return CRS.from_epsg(code)
    crs, _ = geographic_crs(dict(gkd))
    return crs


def _projected_crs(gkd: GeoKeyDirectory) -> CRS:
    """Build the projected CRS, by EPSG code or from the Geog* and Proj* keys."""
    code = gkd.projected_type
    if code is not None and code != USER_DEFINED_CRS:
        return CRS.from_epsg(code)

    keys = dict(gkd)
    geographic_type = gkd.geographic_type
    if geographic_type is not None and geographic_type != USER_DEFINED_CRS:
        base: CRS = CRS.from_epsg(geographic_type)
        unit = angular_unit(keys)
    else:
        base, unit = geographic_crs(keys)
    linear = linear_unit(keys)
    conversion, axes = conversion_from_geo_keys(
        keys,
        to_degrees=unit.to_degrees,
        to_metres=linear.to_metres,
    )
    return ProjectedCRS(
        name=gkd.proj_citation or gkd.citation or "unknown",
        conversion=conversion,
        geodetic_crs=base,
        cartesian_cs=cartesian_cs(linear, axes),
    )
