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

_ASYNC_TIFF = "needs an async-tiff release with keys 2062/3096 (async-tiff#368)"
_PE_STRING = "ESRI PE String read by pyproj differs from GDAL's ESRI morphing"

KNOWN_FAILURES: dict[str, str] = {
    # GeoKeys async-tiff 0.7 does not expose.
    "tmerc_towgs84": _ASYNC_TIFF + "; GeogTOWGS84GeoKey, no BoundCRS",
    "omerc_variant_a": _ASYNC_TIFF + "; ProjRectifiedGridAngleGeoKey",
    "omerc_variant_b": _ASYNC_TIFF + "; ProjRectifiedGridAngleGeoKey",
    "somerc": _ASYNC_TIFF + "; ProjRectifiedGridAngleGeoKey",
    # GDAL's own writer and reader disagree on a prime meridian in grads
    # (spec Q3); we follow libgeotiff's single unit conversion.
    "lcc_1sp_paris_grad": "GDAL converts a grads prime meridian three times on read",
    # ESRI PE String citations: GDAL also applies the Geog* keys and its ESRI
    # name morphing on top of the WKT; pyproj parses the WKT alone.
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
