"""Conformance of `GeoTIFF.crs` against the geotiff-test-data CRS corpus.

Every row of `crs/manifest.json` is a GDAL-written fixture plus the CRS GDAL
reads back from it. The test asserts PROJ equivalence with that CRS, then a
looser check that a test point projects to the recorded coordinates.

Rows in `KNOWN_FAILURES` are expected to fail today (`xfail(strict=True)`), so
a fix that makes one pass fails the run until the row is removed: the list can
only shrink. Rows the manifest flags (GDAL read no CRS, or PROJ cannot export
it) are skipped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pyproj import CRS, Transformer

from async_geotiff import GeoTIFF

if TYPE_CHECKING:
    from async_tiff.store import LocalStore

CRS_DIR = Path(__file__).parent.parent / "fixtures" / "geotiff-test-data" / "crs"
MANIFEST = json.loads((CRS_DIR / "manifest.json").read_text())
ROWS = {row["name"]: row for row in MANIFEST["cases"]}

_REJECTED_CT = "CT code rejected by _build_conversion"
_INVALID_PROJJSON = "builder emits PROJJSON that PROJ rejects"
_WRONG_VARIANT = "wrong method variant"
_ORIGIN_KEYS = (
    "origin or scale read from the wrong GeoKey, libgeotiff fallback order not applied"
)
_UNITS = "linear parameters labelled metres instead of the projected unit"
_AXES = "projected axis directions not set (south/south, north/north, or west/south)"
_ASYNC_TIFF = "needs an async-tiff release with keys 2062/3096 (async-tiff#368)"
_PE_STRING = "ESRI PE String read by pyproj differs from GDAL's ESRI morphing"

KNOWN_FAILURES: dict[str, str] = {
    # Rejected CT codes (spec section 1).
    "cea": _REJECTED_CT + " (28 Cylindrical Equal Area)",
    "eqdc": _REJECTED_CT + " (13 Equidistant Conic)",
    "gnom": _REJECTED_CT + " (19 Gnomonic)",
    "mill": _REJECTED_CT + " (20 Miller)",
    "robin": _REJECTED_CT + " (23 Robinson)",
    "vandg": _REJECTED_CT + " (25 Van der Grinten)",
    "omerc_variant_b": _REJECTED_CT + " (9815 Hotine Oblique Mercator azimuth centre)",
    "somerc": _REJECTED_CT + " (9815 Hotine Oblique Mercator azimuth centre)",
    # PROJJSON PROJ rejects outright.
    "aea_nad27": _INVALID_PROJJSON + ": EPSG-coded datum without an ellipsoid",
    "tmerc_datum_wgs84": _INVALID_PROJJSON + ": EPSG-coded datum without an ellipsoid",
    "geog_grad_wkt": _INVALID_PROJJSON + ": angular unit grads",
    "lcc_1sp_grad_wkt": _INVALID_PROJJSON + ": angular unit grads",
    "lcc_1sp_paris_grad": _INVALID_PROJJSON
    + ": angular unit grads (also GDAL PM bug, spec Q3)",
    "tmerc_ft": _INVALID_PROJJSON + ": linear unit international foot",
    # Wrong variant.
    "merc_2sp": _WRONG_VARIANT + ": Mercator with ProjStdParallel1 is variant B",
    "stere_polar_a": _WRONG_VARIANT
    + ": polar stereographic at the pole with scale is variant A",
    "stere_south_a": _WRONG_VARIANT
    + ": polar stereographic at the pole with scale is variant A",
    "omerc_variant_a": _WRONG_VARIANT
    + ": CT 3 is variant A; grid angle read from the azimuth key",
    "labrd": _WRONG_VARIANT
    + ": CT 4 is Laborde Oblique Mercator, not Hotine variant B",
    # Origin and scale keys.
    "aeqd": _ORIGIN_KEYS + "; method name maps to Modified Azimuthal Equidistant",
    "sterea": _ORIGIN_KEYS,
    "stere_oblique": _ORIGIN_KEYS,
    "eqc_lat0": _ORIGIN_KEYS + "; latitude of natural origin dropped",
    # Units.
    "lcc_2sp_usft": _UNITS,
    # Axes.
    "stere_polar_b": _AXES,
    "stere_south_b": _AXES,
    "stere_polar_k1_wkt": _AXES,
    "tmso": _AXES,
    # Datum, prime meridian, TOWGS84.
    "lcc_1sp_pm_epsg_tifffile": "EPSG-coded prime meridian read as longitude 0",
    "tmerc_towgs84": _ASYNC_TIFF + "; no BoundCRS",
    # ESRI PE String citations.
    "krovak": _PE_STRING + ": Krovak read as North Orientated",
    "moll": _PE_STRING + ": datum keeps its ESRI name",
}
"""Manifest rows that fail against the current builder, with the reason.

Each entry is `xfail(strict=True)`: when a fix makes a row pass, remove it here.
"""

_DRIFT = "proj.db drift between this environment's PROJ and the generator's"
REGISTRY_DRIFT: dict[str, str] = {
    "epsg_3067": _DRIFT + ": the EPSG:3067 datum is EUREF-FIN in newer registries",
    "epsg_3975": _DRIFT + ": EPSG:3975 was corrected from spherical to ellipsoidal CEA",
}
"""EPSG-coded rows whose definition differs between proj.db versions.

They pass or fail with the installed PROJ, so they are `xfail(strict=False)`.
"""

POINT_TOLERANCE = 1e-3
"""Both projections run in the same PROJ, so only rounding noise is expected."""


def _flagged(row: dict) -> bool:
    return row["gdal"]["projjson"] is None or row["gdal"]["proj4"] is None


def _params() -> list:
    params = []
    for name, row in ROWS.items():
        marks = []
        if _flagged(row):
            marks.append(
                pytest.mark.skip(reason=row["note"] or "flagged in the manifest"),
            )
        elif name in KNOWN_FAILURES:
            marks.append(pytest.mark.xfail(strict=True, reason=KNOWN_FAILURES[name]))
        elif name in REGISTRY_DRIFT:
            marks.append(pytest.mark.xfail(strict=False, reason=REGISTRY_DRIFT[name]))
        params.append(pytest.param(row, id=name, marks=marks))
    return params


def _ellipsoid_longlat(crs: CRS) -> CRS:
    """A degree, Greenwich longlat CRS on the same ellipsoid, as the generator uses."""
    ellipsoid = crs.ellipsoid
    assert ellipsoid is not None
    a = ellipsoid.semi_major_metre
    if ellipsoid.inverse_flattening:
        return CRS.from_proj4(
            f"+proj=longlat +a={a!r} +rf={ellipsoid.inverse_flattening!r}",
        )
    return CRS.from_proj4(f"+proj=longlat +R={a!r}")


@pytest.mark.asyncio
@pytest.mark.parametrize("row", _params())
async def test_crs_matches_gdal(fixture_store: LocalStore, row: dict) -> None:
    geotiff = await GeoTIFF.open(
        path=f"geotiff-test-data/crs/{row['file']}",
        store=fixture_store,
    )
    ours = geotiff.crs
    expected = CRS.from_json_dict(row["gdal"]["projjson"])
    # Geographic axis order is ignored, as rasterio's comparison does: a GeoTIFF's
    # raster axes are x/y regardless of the CRS's declared axis order. Projected
    # axis directions still count.
    assert expected.equals(ours, ignore_axis_order=True), (
        f"\nexpected: {expected.to_wkt(pretty=True)}\nours: {ours.to_wkt(pretty=True)}"
    )

    # The manifest's x/y come from the generator's PROJ, which may use different
    # formulas than this environment's (Equidistant Cylindrical changed between
    # PROJ 9.5 and 9.8). Project with both CRSs here instead, so only the CRS
    # definitions are compared.
    point = row["point"]
    base = _ellipsoid_longlat(expected)
    expected_xy = Transformer.from_crs(base, expected, always_xy=True).transform(
        point["lon"],
        point["lat"],
    )
    ours_xy = Transformer.from_crs(base, ours, always_xy=True).transform(
        point["lon"],
        point["lat"],
    )
    assert ours_xy == pytest.approx(expected_xy, abs=POINT_TOLERANCE)


def test_known_failures_are_listed_cases() -> None:
    for name in {**KNOWN_FAILURES, **REGISTRY_DRIFT}:
        assert name in ROWS, name
        assert not _flagged(ROWS[name]), f"{name} is flagged, not a known failure"
    assert not KNOWN_FAILURES.keys() & REGISTRY_DRIFT.keys()
