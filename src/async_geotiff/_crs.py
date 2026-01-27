"""Parse a pyproj CRS from a GeoKeyDirectory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyproj import CRS

if TYPE_CHECKING:
    from async_tiff import GeoKeyDirectory

# GeoTIFF model type constants
_MODEL_TYPE_PROJECTED = 1
_MODEL_TYPE_GEOGRAPHIC = 2

# GeoTIFF "user-defined" sentinel value
_USER_DEFINED = 32767


def crs_from_geo_keys(gkd: GeoKeyDirectory) -> CRS:
    """Parse a pyproj CRS from a GeoKeyDirectory.

    Supports both EPSG-coded and user-defined coordinate reference systems.

    Args:
        gkd: The GeoKeyDirectory from a GeoTIFF IFD.

    Returns:
        A pyproj CRS instance.

    Raises:
        ValueError: If the CRS cannot be determined from the geo keys.
    """
    model_type = gkd.model_type

    if model_type == _MODEL_TYPE_PROJECTED:
        return _parse_projected_crs(gkd)

    if model_type == _MODEL_TYPE_GEOGRAPHIC:
        return _parse_geographic_crs(gkd)

    raise ValueError(f"Unsupported GeoTIFF model type: {model_type}")


def _parse_projected_crs(gkd: GeoKeyDirectory) -> CRS:
    """Parse a projected CRS from geo keys."""
    epsg = gkd.projected_type
    if epsg is not None and epsg != _USER_DEFINED:
        return CRS.from_epsg(epsg)

    return _build_user_defined_projected_crs(gkd)


def _parse_geographic_crs(gkd: GeoKeyDirectory) -> CRS:
    """Parse a geographic CRS from geo keys."""
    epsg = gkd.geographic_type
    if epsg is not None and epsg != _USER_DEFINED:
        return CRS.from_epsg(epsg)

    return _build_user_defined_geographic_crs(gkd)


def _build_user_defined_geographic_crs(gkd: GeoKeyDirectory) -> CRS:
    """Build a user-defined geographic CRS from individual geo key parameters.

    Constructs a CRS from the ellipsoid, datum, prime meridian, and angular
    unit parameters stored in the GeoKeyDirectory.
    """
    # Build ellipsoid parameters
    ellipsoid = _build_ellipsoid_params(gkd)

    # Build prime meridian
    pm_name = "Greenwich"
    pm_longitude = 0.0
    if gkd.geog_prime_meridian is not None and gkd.geog_prime_meridian != _USER_DEFINED:
        # Known prime meridian by EPSG code
        pm_name = f"EPSG:{gkd.geog_prime_meridian}"
    elif gkd.geog_prime_meridian_long is not None:
        pm_longitude = gkd.geog_prime_meridian_long
        pm_name = "User-defined"

    # Build datum
    datum_json: dict = {}
    if gkd.geog_geodetic_datum is not None and gkd.geog_geodetic_datum != _USER_DEFINED:
        # Known datum by EPSG code — let pyproj resolve it
        return CRS.from_json_dict(
            {
                "type": "GeographicCRS",
                "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
                "name": gkd.geog_citation or "User-defined",
                "datum": {
                    "type": "GeodeticReferenceFrame",
                    "name": f"Unknown datum based upon EPSG {gkd.geog_geodetic_datum} ellipsoid",
                },
                "datum_ensemble": None,
                "coordinate_system": _geographic_cs(gkd),
            }
        )
    else:
        datum_json = {
            "type": "GeodeticReferenceFrame",
            "name": gkd.geog_citation or "User-defined",
            "ellipsoid": ellipsoid,
            "prime_meridian": {
                "name": pm_name,
                "longitude": pm_longitude,
            },
        }

    return CRS.from_json_dict(
        {
            "type": "GeographicCRS",
            "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
            "name": gkd.geog_citation or "User-defined",
            "datum": datum_json,
            "coordinate_system": _geographic_cs(gkd),
        }
    )


def _build_user_defined_projected_crs(gkd: GeoKeyDirectory) -> CRS:
    """Build a user-defined projected CRS from individual geo key parameters.

    Constructs a CRS from the geographic base CRS and projection parameters
    stored in the GeoKeyDirectory.
    """
    # Build the base geographic CRS
    base_crs = _parse_geographic_crs(gkd)
    base_crs_json = base_crs.to_json_dict()

    # Build the coordinate operation (projection)
    conversion = _build_conversion(gkd)

    # Build the coordinate system for the projected CRS
    cs = _projected_cs(gkd)

    return CRS.from_json_dict(
        {
            "type": "ProjectedCRS",
            "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
            "name": gkd.proj_citation or "User-defined",
            "base_crs": base_crs_json,
            "conversion": conversion,
            "coordinate_system": cs,
        }
    )


def _build_ellipsoid_params(gkd: GeoKeyDirectory) -> dict:
    """Build ellipsoid JSON parameters from geo keys."""
    if gkd.geog_ellipsoid is not None and gkd.geog_ellipsoid != _USER_DEFINED:
        # Known ellipsoid by EPSG code — use parameters from geo keys if present
        ellipsoid: dict = {"name": f"EPSG ellipsoid {gkd.geog_ellipsoid}"}

        if gkd.geog_semi_major_axis is not None:
            ellipsoid["semi_major_axis"] = gkd.geog_semi_major_axis
        if gkd.geog_inv_flattening is not None:
            ellipsoid["inverse_flattening"] = gkd.geog_inv_flattening
        elif gkd.geog_semi_minor_axis is not None:
            ellipsoid["semi_minor_axis"] = gkd.geog_semi_minor_axis

        return ellipsoid

    # Fully user-defined ellipsoid
    semi_major = gkd.geog_semi_major_axis
    if semi_major is None:
        raise ValueError("User-defined ellipsoid requires geog_semi_major_axis")

    ellipsoid: dict = {
        "name": "User-defined",
        "semi_major_axis": semi_major,
    }

    if gkd.geog_inv_flattening is not None:
        ellipsoid["inverse_flattening"] = gkd.geog_inv_flattening
    elif gkd.geog_semi_minor_axis is not None:
        ellipsoid["semi_minor_axis"] = gkd.geog_semi_minor_axis
    else:
        raise ValueError(
            "User-defined ellipsoid requires geog_inv_flattening or geog_semi_minor_axis"
        )

    return ellipsoid


# GeoTIFF coordinate transformation type codes (GeoKey 3075)
# Ref: http://geotiff.maptools.org/spec/geotiff6.html#6.3.3.3
_CT_TRANSVERSE_MERCATOR = 1
_CT_TRANSVERSE_MERCATOR_SOUTH = 2
_CT_OBLIQUE_MERCATOR = 3
_CT_OBLIQUE_MERCATOR_LABORDE = 4
_CT_OBLIQUE_MERCATOR_ROSENMUND = 5
_CT_OBLIQUE_MERCATOR_SPHERICAL = 6
_CT_MERCATOR = 7
_CT_LAMBERT_CONFORMAL_CONIC_2SP = 8
_CT_LAMBERT_CONFORMAL_CONIC_1SP = 9
_CT_LAMBERT_AZIMUTHAL_EQUAL_AREA = 10
_CT_ALBERS_EQUAL_AREA = 11
_CT_AZIMUTHAL_EQUIDISTANT = 12
_CT_STEREOGRAPHIC = 14
_CT_POLAR_STEREOGRAPHIC = 15
_CT_OBLIQUE_STEREOGRAPHIC = 16
_CT_EQUIRECTANGULAR = 17
_CT_CASSINI_SOLDNER = 18
_CT_ORTHOGRAPHIC = 21
_CT_POLYCONIC = 22
_CT_SINUSOIDAL = 24
_CT_NEW_ZEALAND_MAP_GRID = 26
_CT_TRANSVERSE_MERCATOR_SOUTH_ORIENTED = 27


def _build_conversion(gkd: GeoKeyDirectory) -> dict:
    """Build a PROJ JSON conversion (coordinate operation) from geo keys."""
    ct = gkd.proj_coord_trans
    if ct is None:
        raise ValueError("User-defined projected CRS requires proj_coord_trans")

    # Helper to get projection parameters with defaults
    def _param(name: str, value: float | None, default: float = 0.0) -> dict:
        return {"name": name, "value": value if value is not None else default}

    name = "User-defined"
    method: dict
    parameters: list[dict]

    if ct == _CT_TRANSVERSE_MERCATOR:
        name = "Transverse Mercator"
        method = {"name": "Transverse Mercator"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_nat_origin_lat),
            _param("Longitude of natural origin", gkd.proj_nat_origin_long),
            _param("Scale factor at natural origin", gkd.proj_scale_at_nat_origin, 1.0),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_TRANSVERSE_MERCATOR_SOUTH:
        name = "Transverse Mercator (South Orientated)"
        method = {"name": "Transverse Mercator (South Orientated)"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_nat_origin_lat),
            _param("Longitude of natural origin", gkd.proj_nat_origin_long),
            _param("Scale factor at natural origin", gkd.proj_scale_at_nat_origin, 1.0),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct in (
        _CT_OBLIQUE_MERCATOR,
        _CT_OBLIQUE_MERCATOR_LABORDE,
        _CT_OBLIQUE_MERCATOR_ROSENMUND,
        _CT_OBLIQUE_MERCATOR_SPHERICAL,
    ):
        name = "Hotine Oblique Mercator (variant B)"
        method = {"name": "Hotine Oblique Mercator (variant B)"}
        parameters = [
            _param("Latitude of projection centre", gkd.proj_center_lat),
            _param("Longitude of projection centre", gkd.proj_center_long),
            _param("Azimuth of initial line", gkd.proj_azimuth_angle),
            _param("Angle from Rectified to Skew Grid", gkd.proj_azimuth_angle),
            _param("Scale factor on initial line", gkd.proj_scale_at_center, 1.0),
            _param("Easting at projection centre", gkd.proj_center_easting),
            _param("Northing at projection centre", gkd.proj_center_northing),
        ]

    elif ct == _CT_MERCATOR:
        name = "Mercator (variant A)"
        method = {"name": "Mercator (variant A)"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_nat_origin_lat),
            _param("Longitude of natural origin", gkd.proj_nat_origin_long),
            _param("Scale factor at natural origin", gkd.proj_scale_at_nat_origin, 1.0),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_LAMBERT_CONFORMAL_CONIC_2SP:
        name = "Lambert Conic Conformal (2SP)"
        method = {"name": "Lambert Conic Conformal (2SP)"}
        parameters = [
            _param("Latitude of false origin", gkd.proj_false_origin_lat),
            _param("Longitude of false origin", gkd.proj_false_origin_long),
            _param("Latitude of 1st standard parallel", gkd.proj_std_parallel1),
            _param("Latitude of 2nd standard parallel", gkd.proj_std_parallel2),
            _param("Easting at false origin", gkd.proj_false_origin_easting),
            _param("Northing at false origin", gkd.proj_false_origin_northing),
        ]

    elif ct == _CT_LAMBERT_CONFORMAL_CONIC_1SP:
        name = "Lambert Conic Conformal (1SP)"
        method = {"name": "Lambert Conic Conformal (1SP)"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_nat_origin_lat),
            _param("Longitude of natural origin", gkd.proj_nat_origin_long),
            _param("Scale factor at natural origin", gkd.proj_scale_at_nat_origin, 1.0),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_LAMBERT_AZIMUTHAL_EQUAL_AREA:
        name = "Lambert Azimuthal Equal Area"
        method = {"name": "Lambert Azimuthal Equal Area"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_center_lat),
            _param("Longitude of natural origin", gkd.proj_center_long),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_ALBERS_EQUAL_AREA:
        name = "Albers Equal Area"
        method = {"name": "Albers Equal Area"}
        parameters = [
            _param("Latitude of false origin", gkd.proj_false_origin_lat),
            _param("Longitude of false origin", gkd.proj_false_origin_long),
            _param("Latitude of 1st standard parallel", gkd.proj_std_parallel1),
            _param("Latitude of 2nd standard parallel", gkd.proj_std_parallel2),
            _param("Easting at false origin", gkd.proj_false_origin_easting),
            _param("Northing at false origin", gkd.proj_false_origin_northing),
        ]

    elif ct == _CT_AZIMUTHAL_EQUIDISTANT:
        name = "Modified Azimuthal Equidistant"
        method = {"name": "Modified Azimuthal Equidistant"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_center_lat),
            _param("Longitude of natural origin", gkd.proj_center_long),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_STEREOGRAPHIC:
        name = "Stereographic"
        method = {"name": "Stereographic"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_center_lat),
            _param("Longitude of natural origin", gkd.proj_center_long),
            _param("Scale factor at natural origin", gkd.proj_scale_at_center, 1.0),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_POLAR_STEREOGRAPHIC:
        name = "Polar Stereographic (variant B)"
        method = {"name": "Polar Stereographic (variant B)"}
        parameters = [
            _param(
                "Latitude of standard parallel",
                gkd.proj_nat_origin_lat or gkd.proj_std_parallel1,
            ),
            _param(
                "Longitude of origin",
                gkd.proj_straight_vert_pole_long or gkd.proj_nat_origin_long,
            ),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_OBLIQUE_STEREOGRAPHIC:
        name = "Oblique Stereographic"
        method = {"name": "Oblique Stereographic"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_center_lat),
            _param("Longitude of natural origin", gkd.proj_center_long),
            _param("Scale factor at natural origin", gkd.proj_scale_at_center, 1.0),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_EQUIRECTANGULAR:
        name = "Equidistant Cylindrical"
        method = {"name": "Equidistant Cylindrical"}
        parameters = [
            _param(
                "Latitude of 1st standard parallel",
                gkd.proj_std_parallel1 or gkd.proj_center_lat,
            ),
            _param("Longitude of natural origin", gkd.proj_center_long),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_CASSINI_SOLDNER:
        name = "Cassini-Soldner"
        method = {"name": "Cassini-Soldner"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_nat_origin_lat),
            _param("Longitude of natural origin", gkd.proj_nat_origin_long),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_POLYCONIC:
        name = "American Polyconic"
        method = {"name": "American Polyconic"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_nat_origin_lat),
            _param("Longitude of natural origin", gkd.proj_nat_origin_long),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_SINUSOIDAL:
        name = "Sinusoidal"
        method = {"name": "Sinusoidal"}
        parameters = [
            _param("Longitude of natural origin", gkd.proj_center_long),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_ORTHOGRAPHIC:
        name = "Orthographic"
        method = {"name": "Orthographic"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_center_lat),
            _param("Longitude of natural origin", gkd.proj_center_long),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_NEW_ZEALAND_MAP_GRID:
        name = "New Zealand Map Grid"
        method = {"name": "New Zealand Map Grid"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_nat_origin_lat),
            _param("Longitude of natural origin", gkd.proj_nat_origin_long),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    elif ct == _CT_TRANSVERSE_MERCATOR_SOUTH_ORIENTED:
        name = "Transverse Mercator (South Orientated)"
        method = {"name": "Transverse Mercator (South Orientated)"}
        parameters = [
            _param("Latitude of natural origin", gkd.proj_nat_origin_lat),
            _param("Longitude of natural origin", gkd.proj_nat_origin_long),
            _param("Scale factor at natural origin", gkd.proj_scale_at_nat_origin, 1.0),
            _param("False easting", gkd.proj_false_easting),
            _param("False northing", gkd.proj_false_northing),
        ]

    else:
        raise ValueError(f"Unsupported coordinate transformation type: {ct}")

    return {
        "name": name,
        "method": method,
        "parameters": parameters,
    }


def _geographic_cs(gkd: GeoKeyDirectory) -> dict:
    """Build a geographic coordinate system JSON dict from geo keys."""
    angular_unit = "degree"
    if gkd.geog_angular_units is not None:
        # EPSG code 9102 = degree, 9101 = radian, 9105 = grad
        if gkd.geog_angular_units == 9101:
            angular_unit = "radian"
        elif gkd.geog_angular_units == 9105:
            angular_unit = "grad"
        # Default to degree for 9102 and other common cases

    return {
        "subtype": "ellipsoidal",
        "axis": [
            {
                "name": "Latitude",
                "abbreviation": "lat",
                "direction": "north",
                "unit": angular_unit,
            },
            {
                "name": "Longitude",
                "abbreviation": "lon",
                "direction": "east",
                "unit": angular_unit,
            },
        ],
    }


def _projected_cs(gkd: GeoKeyDirectory) -> dict:
    """Build a projected coordinate system JSON dict from geo keys."""
    linear_unit = "metre"
    if gkd.proj_linear_units is not None:
        # EPSG code 9001 = metre, 9002 = foot, 9003 = US survey foot
        if gkd.proj_linear_units == 9002:
            linear_unit = "foot"
        elif gkd.proj_linear_units == 9003:
            linear_unit = {
                "type": "LinearUnit",
                "name": "US survey foot",
                "conversion_factor": 0.30480060960121924,
            }
        # Default to metre for 9001 and other common cases

    return {
        "subtype": "Cartesian",
        "axis": [
            {
                "name": "Easting",
                "abbreviation": "E",
                "direction": "east",
                "unit": linear_unit,
            },
            {
                "name": "Northing",
                "abbreviation": "N",
                "direction": "north",
                "unit": linear_unit,
            },
        ],
    }
