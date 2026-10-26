# CRS Conformance Corpus and CT Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `crs/` directory to geotiff-test-data holding GDAL-written GeoTIFF fixtures, a manifest of what GDAL wrote and reads back, cached epsg.io JSON, and the GeoTIFF CT-code-to-PROJ-method table, all regenerable and CI-checked.

**Architecture:** A data-only case list (`crs/cases.py`) feeds one generator (`crs/generate_crs.py`) that writes 8x8 GeoTIFFs with rasterio (or tifffile for hand-built GeoKeys), reads them back with rasterio as the GDAL/PROJ oracle, and records raw GeoKeys plus PROJJSON, proj4, a normalized name-free core, and a test point in `crs/manifest.json`. A hand-written `crs/geotiff-ct-methods.json` transcribes libgeotiff and GDAL; pytest checks the manifest against the files and the table against the manifest.

**Tech Stack:** Python 3.12+, rasterio 1.5 / GDAL 3.12 / PROJ 9.7 (pixi, conda-forge), pyproj 3.7, tifffile, numpy, pytest, pixi tasks.

**Spec:** `dev-docs/specs/2026-10-26-geokey-crs-conformance-design.md` (in async-geotiff; sections 4 and 5 are this plan's scope)

## Global Constraints

- Work in a git worktree of geotiff-test-data under its existing `.worktrees/` directory, branch `kyle/crs-conformance-corpus`, based on `origin/main` (currently `b73b96d`). Never commit on `main`.
- Run everything through pixi (`pixi run ...`); the generator must be deterministic so `scripts/check.sh` passes in CI.
- Fixtures are plain GTiff, 8x8 uint8, one band, no compression, no overviews, written with `GDAL_PAM_ENABLED=NO`; read-back also with `GDAL_PAM_ENABLED=NO`.
- GeoKey names everywhere (manifest `geokeys`, table `keys`, encoder input) are the GeoTIFF spec names without the `GeoKey` suffix: `ProjCoordTrans`, `GeogTOWGS84`, `GTModelType`.
- `manifest.json` is written with `json.dump(..., indent=1, sort_keys=True)` and rows sorted by `name`.
- Rows with `gdal.projjson == null` or `gdal.proj4 == null` are flagged, not tested, and carry a `note`.
- PR text: top `> [!NOTE]` saying Claude wrote it, bottom `🤖 Written by [Claude Code](https://claude.com/claude-code)`. Never merge.
- Ruff with `select = ["I"]` (import sorting) is the only lint; `pytest` from the repo root with `pythonpath = ["."]`.

## Review Focus

1. A PROJ-string case that GDAL identifies as an EPSG CRS writes only `ProjectedCSType = <code>` and silently stops testing the user-defined key path. Pinned in Task 7 (`test_proj_cases_are_user_defined`).
2. A citation string whose terminating `|` is or is not stripped makes `geokeys` disagree with async-tiff's view of the same file. Pinned in Task 1 (`test_decode_existing_fixture`, exact citation values).
3. A `GeogTOWGS84` with three values vs seven must round-trip through the encoder and decoder as a list, not a scalar. Pinned in Task 1 (`test_encode_decode_roundtrip`).
4. Parameters in grads or feet must land in the core in degrees and metres, or the TS side compares the wrong numbers. Pinned in Task 3 (`test_core_of_grads`, `test_core_of_feet`).
5. Regenerating with network blocked must still succeed when `crs/epsg/*.json` already exist. Pinned in Task 4 (`test_fetch_epsg_json_skips_existing`).

---

### Task 1: GeoKey id table, decoder, encoder

**Files:**
- Create: `crs/__init__.py` (empty docstring module)
- Create: `crs/geokeys.py`
- Test: `tests/test_crs_geokeys.py`
- Modify: `pixi.toml` (add `pyproj = ">=3.7,<4"` under `[pypi-dependencies]`; it is only a transitive dependency today)

**Interfaces:**
- Produces: `GEOKEY_IDS: dict[str, int]` mapping spec name (no suffix) to key id, covering 1024-1026, 2048-2062, 3072-3096, 4096-4099, 5120 (`CoordinateEpoch`). `GEOKEY_NAMES: dict[int, str]` is its inverse.
- Produces: `decode_geokeys(path: Path) -> dict[str, int | float | str | list[float]]`: reads tags 34735/34736/34737 with tifffile, returns one entry per directory entry keyed by name (`"unknown_<id>"` for ids not in the table); SHORT values as `int`, a single DOUBLE as `float`, several DOUBLEs as `list[float]`, ASCII as `str` with exactly one trailing `|` removed.
- Produces: `encode_geokeys(keys: dict[str, int | float | str | list[float]]) -> list[tuple]`: tifffile `extratags` triples for tags 34735 (SHORT), 34736 (DOUBLE), 34737 (ASCII), in the form `(tag, dtype_code, count, value, True)` with dtype codes 3, 12, 2; entries sorted by key id as the spec requires; ASCII values get the `|` terminator appended; version header `[1, 1, 0, n]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_crs_geokeys.py
from pathlib import Path

import numpy as np
import tifffile

from crs.geokeys import GEOKEY_IDS, decode_geokeys, encode_geokeys

REPO_ROOT = Path(__file__).parent.parent


def test_geokey_ids_cover_spec():
    assert GEOKEY_IDS["GTModelType"] == 1024
    assert GEOKEY_IDS["GeogTOWGS84"] == 2062
    assert GEOKEY_IDS["ProjRectifiedGridAngle"] == 3096
    assert GEOKEY_IDS["CoordinateEpoch"] == 5120
    assert len(GEOKEY_IDS) == 48


def test_decode_existing_fixture():
    keys = decode_geokeys(
        REPO_ROOT / "real_data/source-coop-dataforcanada/O2308000_7586000_cog.tif"
    )
    assert keys == {
        "GTModelType": 1,
        "GTRasterType": 1,
        "GTCitation": "NAD83(CSRS) / New Brunswick Stereographic",
        "GeographicType": 32767,
        "GeogCitation": "GCS Name = NAD83(CSRS)|Primem = Greenwich|",
        "GeogGeodeticDatum": 6140,
        "GeogAngularUnits": 9102,
        "GeogSemiMajorAxis": 6378137.0,
        "GeogInvFlattening": 298.257222101,
        "GeogPrimeMeridianLong": 0.0,
        "ProjectedCSType": 32767,
        "Projection": 32767,
        "ProjCoordTrans": 16,
        "ProjLinearUnits": 9001,
        "ProjNatOriginLong": -66.5,
        "ProjNatOriginLat": 46.5,
        "ProjFalseEasting": 2500000.0,
        "ProjFalseNorthing": 7500000.0,
        "ProjScaleAtNatOrigin": 0.999912,
    }


def test_encode_decode_roundtrip(tmp_path: Path):
    keys = {
        "GTModelType": 1,
        "GTRasterType": 1,
        "GeographicType": 32767,
        "GeogCitation": "GCS Name = unknown|Primem = Paris|",
        "GeogPrimeMeridian": 8903,
        "GeogSemiMajorAxis": 6378249.2,
        "GeogTOWGS84": [598.1, 73.7, 418.2, 0.202, 0.045, -2.455, 6.7],
        "ProjCoordTrans": 9,
        "ProjRectifiedGridAngle": 90.0,
    }
    path = tmp_path / "keys.tif"
    tifffile.imwrite(path, np.zeros((8, 8), np.uint8), extratags=encode_geokeys(keys))
    assert decode_geokeys(path) == keys


def test_decode_three_value_towgs84(tmp_path: Path):
    keys = {"GTModelType": 2, "GeogTOWGS84": [0.0, 0.0, 0.0]}
    path = tmp_path / "keys.tif"
    tifffile.imwrite(path, np.zeros((8, 8), np.uint8), extratags=encode_geokeys(keys))
    assert decode_geokeys(path)["GeogTOWGS84"] == [0.0, 0.0, 0.0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run pytest tests/test_crs_geokeys.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crs'`

- [ ] **Step 3: Implement `crs/geokeys.py`**

`GEOKEY_IDS` is a literal dict (the 48 names from libgeotiff `geokeys.inc` / OGC 19-008r4 Annex, minus the `GeoKey` suffix; `GTCitation`, `PCSCitation` keep their spec names). `decode_geokeys` reads `tifffile.TiffFile(path).pages[0].tags[34735].value` and slices 34736/34737 by `(location, count, offset)` as the GeoTIFF spec defines. `encode_geokeys` appends doubles and ASCII into their param arrays as it walks the keys sorted by id.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pixi run pytest tests/test_crs_geokeys.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add crs/__init__.py crs/geokeys.py tests/test_crs_geokeys.py pixi.toml pixi.lock
git commit -m "feat(crs): Add GeoKey id table with raw decoder and encoder"
```

### Task 2: Case list

**Files:**
- Create: `crs/cases.py`
- Test: `tests/test_crs_cases.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) class Case: name: str; kind: Literal["proj", "epsg", "wkt", "geokeys"]; value: str | dict[str, int | float | str | list[float]]; note: str = ""; tags: tuple[str, ...] = ()`.
- Produces: `CASES: list[Case]`, every case from spec section 4.3 (CT rows, units, datum/PM variants, 46 EPSG codes, citation forms). `kind == "geokeys"` carries the raw key dict for the tifffile-written fixture.
- Produces: `EPSG_CODES: list[int]` (the 46 codes; `epsg_<code>` cases are generated from it).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crs_cases.py
import re
from collections import Counter

from crs.cases import CASES, EPSG_CODES, Case


def test_case_names_unique_and_well_formed():
    names = [c.name for c in CASES]
    assert len(names) == len(set(names))
    assert all(re.fullmatch(r"[a-z0-9_]+", n) for n in names)


def test_case_kinds():
    kinds = Counter(c.kind for c in CASES)
    assert set(kinds) == {"proj", "epsg", "wkt", "geokeys"}
    assert kinds["epsg"] == len(EPSG_CODES) == 46
    assert kinds["geokeys"] == 1


def test_expected_cases_present():
    names = {c.name for c in CASES}
    for name in (
        "tmerc", "omerc_variant_a", "omerc_variant_b", "labrd", "somerc", "merc_1sp",
        "merc_2sp", "stere_polar_scaled_wkt", "stere_polar_k1_wkt", "tmso", "cea",
        "lcc_2sp_usft", "tmerc_ft", "lcc_1sp_grad_wkt", "geog_grad_wkt", "lcc_1sp_paris_grad",
        "aea_nad27", "tmerc_datum_wgs84", "sinu_sphere", "geog_sphere", "tmerc_towgs84",
        "lcc_1sp_paris_deg_wkt", "lcc_1sp_pm_user", "lcc_1sp_pm_epsg_tifffile",
        "longlat_grs80", "utm_bessel", "moll", "krovak", "esri_54009", "eqearth", "epsg_2953",
    ):
        assert name in names
    assert len(CASES) >= 95


def test_geokeys_case_has_epsg_prime_meridian():
    case = next(c for c in CASES if c.kind == "geokeys")
    assert isinstance(case.value, dict)
    assert case.value["GeogPrimeMeridian"] == 8903
    assert "GeogPrimeMeridianLong" not in case.value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pixi run pytest tests/test_crs_cases.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crs.cases'`

- [ ] **Step 3: Implement `crs/cases.py`**

Transcribe spec 4.3 verbatim. The WKT values the spec names but does not spell out:

```python
_GEOG_WGS84_DEG = 'GEOGCS["unknown",DATUM["unknown",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
_GEOG_CLRK80IGN_GRAD = 'GEOGCS["unknown",DATUM["unknown",SPHEROID["Clarke 1880 (IGN)",6378249.2,293.466021293627]],PRIMEM["Greenwich",0],UNIT["grad",0.01570796326794897]]'
_GEOG_CLRK80IGN_PARIS_DEG = 'GEOGCS["unknown",DATUM["unknown",SPHEROID["Clarke 1880 (IGN)",6378249.2,293.466021293627]],PRIMEM["Paris",2.33722917],UNIT["degree",0.0174532925199433]]'
_LCC_1SP_PARAMS = 'PROJECTION["Lambert_Conformal_Conic_1SP"],PARAMETER["latitude_of_origin",{lat}],PARAMETER["central_meridian",0],PARAMETER["scale_factor",0.99987742],PARAMETER["false_easting",600000],PARAMETER["false_northing",2200000],UNIT["metre",1]'
# stere_polar_scaled_wkt / stere_polar_k1_wkt:
#   f'PROJCS["unknown",{_GEOG_WGS84_DEG},PROJECTION["Polar_Stereographic"],PARAMETER["latitude_of_origin",{lat}],PARAMETER["central_meridian",-45],PARAMETER["scale_factor",{k}],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1]]'
# lcc_1sp_grad_wkt:        f'PROJCS["unknown",{_GEOG_CLRK80IGN_GRAD},{_LCC_1SP_PARAMS.format(lat=52)}]'
# lcc_1sp_paris_deg_wkt:   f'PROJCS["unknown",{_GEOG_CLRK80IGN_PARIS_DEG},{_LCC_1SP_PARAMS.format(lat=46.8)}]'
# geog_grad_wkt:           _GEOG_CLRK80IGN_GRAD
```

The `geokeys` case (`lcc_1sp_pm_epsg_tifffile`) is the `lcc_1sp` key set GDAL writes (see the `lcc_1sp` manifest row after Task 4, or the prior session's dump) with `GeogPrimeMeridianLong` removed, `GeogPrimeMeridian: 8903` added, and `Primem = Paris` in the citation. Case notes: `eqearth` ("GDAL writes no GeoKeys; sidecar disabled"), `lcc_1sp_paris_grad` ("GDAL PM-in-grads round-trip is lossy; see spec Q3"), `stere_polar_scaled_wkt` ("PROJ keeps a non-EPSG Polar_Stereographic method; not exportable"), `utm_bessel` ("GDAL writes ProjectionGeoKey = 16033, no CT key"), `tmerc_towgs84` ("needs async-tiff >= the release with key 2062").

- [ ] **Step 4: Run test to verify it passes**

Run: `pixi run pytest tests/test_crs_cases.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add crs/cases.py tests/test_crs_cases.py
git commit -m "feat(crs): Add the conformance corpus case list"
```

### Task 3: CRS normalization helpers

**Files:**
- Create: `crs/normalize.py`
- Test: `tests/test_crs_normalize.py`

**Interfaces:**
- Produces: `core_of(crs: pyproj.CRS) -> dict` with keys `type` (`crs.type_name` mapped to `"ProjectedCRS" | "GeographicCRS" | "BoundCRS"`), `method` (`{"name": str, "epsg": int | None}` or `None` for geographic), `parameters` (list of `{"epsg": int | None, "name": str, "value": float}`, angular values in degrees, linear in metres, scale as-is, in PROJJSON order), `ellipsoid` (`{"a": float, "rf": float | None, "b": float | None}`, `rf` None and `b` set when `inverse_flattening == 0`), `prime_meridian_deg: float`, `angular_unit_deg: float`, `linear_unit_m: float | None`, `axes: list[str]` (axis directions of the projected CS, or of the geographic CS for a geographic CRS), `towgs84: list[float] | None`. For a BoundCRS the inner CRS is `crs.source_crs` and `towgs84` is `crs.coordinate_operation.towgs84`.
- Produces: `ellipsoid_longlat(crs: pyproj.CRS) -> pyproj.CRS`: `+proj=longlat +a=<a> +rf=<rf>` or `+b=<b>` for a sphere, from the inner CRS's ellipsoid.
- Produces: `point_for(core: dict) -> tuple[float, float]`: `(10.0, 40.0)` when `core["method"]` is None; otherwise `(lon0 + 3, lat)` where `lat` moves 8 degrees away from the equator when `abs(lat0) < 80` and 8 degrees towards it otherwise (`lat0 = 0 -> 8`, `lat0 = -41 -> -49`, `lat0 = 90 -> 82`, `lat0 = -90 -> -82`). `lon0` is the first present of parameter names `Longitude of natural origin`, `Longitude of false origin`, `Longitude of projection centre`, `Longitude of origin` else 0; `lat0` the first of `Latitude of natural origin`, `Latitude of false origin`, `Latitude of projection centre`, `Latitude of standard parallel`, `Latitude of 1st standard parallel` else 0.
- Produces: `project_point(crs: pyproj.CRS, lon: float, lat: float) -> tuple[float, float]`: `Transformer.from_crs(ellipsoid_longlat(crs), crs, always_xy=True).transform(lon, lat)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_crs_normalize.py
import pytest
from pyproj import CRS

from crs.normalize import core_of, ellipsoid_longlat, point_for, project_point

GRAD_WKT = 'PROJCS["unknown",GEOGCS["unknown",DATUM["unknown",SPHEROID["Clarke 1880 (IGN)",6378249.2,293.466021293627]],PRIMEM["Greenwich",0],UNIT["grad",0.01570796326794897]],PROJECTION["Lambert_Conformal_Conic_1SP"],PARAMETER["latitude_of_origin",52],PARAMETER["central_meridian",0],PARAMETER["scale_factor",0.99987742],PARAMETER["false_easting",600000],PARAMETER["false_northing",2200000],UNIT["metre",1]]'


def test_core_of_utm():
    core = core_of(CRS.from_epsg(32633))
    assert core["type"] == "ProjectedCRS"
    assert core["method"] == {"name": "Transverse Mercator", "epsg": 9807}
    assert core["parameters"] == [
        {"epsg": 8801, "name": "Latitude of natural origin", "value": 0.0},
        {"epsg": 8802, "name": "Longitude of natural origin", "value": 15.0},
        {"epsg": 8805, "name": "Scale factor at natural origin", "value": 0.9996},
        {"epsg": 8806, "name": "False easting", "value": 500000.0},
        {"epsg": 8807, "name": "False northing", "value": 0.0},
    ]
    assert core["ellipsoid"] == {"a": 6378137.0, "rf": 298.257223563, "b": None}
    assert core["prime_meridian_deg"] == 0.0
    assert core["angular_unit_deg"] == pytest.approx(1.0)
    assert core["linear_unit_m"] == 1.0
    assert core["axes"] == ["east", "north"]
    assert core["towgs84"] is None


def test_core_of_grads():
    core = core_of(CRS.from_wkt(GRAD_WKT))
    assert core["parameters"][0]["value"] == pytest.approx(46.8)
    assert core["angular_unit_deg"] == pytest.approx(0.9)


def test_core_of_feet():
    core = core_of(CRS.from_proj4("+proj=lcc +lat_1=41.03333 +lat_2=40.66667 +lat_0=40.16667 +lon_0=-74 +x_0=300000 +y_0=0 +ellps=GRS80 +units=us-ft"))
    easting = next(p for p in core["parameters"] if p["epsg"] == 8826)
    assert easting["value"] == pytest.approx(300000.0)
    assert core["linear_unit_m"] == pytest.approx(0.3048006096012192)


def test_core_of_bound_crs():
    core = core_of(CRS.from_proj4("+proj=tmerc +lat_0=0 +lon_0=9 +k=1 +x_0=3500000 +y_0=0 +ellps=bessel +towgs84=598.1,73.7,418.2,0.202,0.045,-2.455,6.7"))
    assert core["type"] == "BoundCRS"
    assert core["method"]["epsg"] == 9807
    assert core["towgs84"] == [598.1, 73.7, 418.2, 0.202, 0.045, -2.455, 6.7]


def test_core_of_sphere_and_geographic():
    core = core_of(CRS.from_proj4("+proj=longlat +R=6371007.181"))
    assert core["type"] == "GeographicCRS"
    assert core["method"] is None
    assert core["ellipsoid"] == {"a": 6371007.181, "rf": None, "b": 6371007.181}
    assert core["linear_unit_m"] is None


def test_core_of_south_orientated_axes():
    core = core_of(CRS.from_proj4("+proj=tmerc +lat_0=0 +lon_0=19 +k=1 +x_0=0 +y_0=0 +axis=wsu +ellps=WGS84"))
    assert core["axes"] == ["west", "south"]


def test_point_for():
    assert point_for(core_of(CRS.from_epsg(32633))) == (18.0, 8.0)
    assert point_for(core_of(CRS.from_proj4("+proj=stere +lat_0=90 +k=0.994 +lon_0=0 +ellps=WGS84"))) == (3.0, 82.0)
    assert point_for(core_of(CRS.from_epsg(4326))) == (10.0, 40.0)


def test_project_point():
    assert project_point(CRS.from_epsg(32633), 15.0, 0.0) == pytest.approx((500000.0, 0.0))
    # A grads geographic CRS: degrees in, grads out.
    assert project_point(CRS.from_wkt(GRAD_WKT).geodetic_crs, 3.0, 54.8) == pytest.approx((3.3333333333, 60.8888888889))


def test_ellipsoid_longlat_sphere():
    assert ellipsoid_longlat(CRS.from_proj4("+proj=sinu +R=6371007.181")).to_proj4().startswith("+proj=longlat +R=6371007.181")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run pytest tests/test_crs_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crs.normalize'`

- [ ] **Step 3: Implement `crs/normalize.py`**

Unit conversion in `core_of`: walk `inner.to_json_dict()["conversion"]["parameters"]`; a `unit` that is a string is `degree`, `metre` or `unity`; a dict has `type` (`AngularUnit` / `LinearUnit` / `ScaleUnit`) and `conversion_factor` (radians per unit or metres per unit); angular value in degrees is `value * factor * 180 / pi`. `angular_unit_deg` comes from `inner.geodetic_crs.axis_info[0].unit_conversion_factor * 180 / pi` (for a geographic CRS, `inner.axis_info`); `linear_unit_m` from `inner.axis_info[0].unit_conversion_factor` when `inner.is_projected`, else None. `prime_meridian_deg` is `pm.longitude * pm.unit_conversion_factor * 180 / pi`. Use `pyproj.CRS.is_bound`, `.source_crs`, `.coordinate_operation.towgs84`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pixi run pytest tests/test_crs_normalize.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add crs/normalize.py tests/test_crs_normalize.py
git commit -m "feat(crs): Add name-free CRS core, test point, and ellipsoid base helpers"
```

### Task 4: Generator: write, read back, manifest row, epsg cache

**Files:**
- Create: `crs/generate_crs.py`
- Test: `tests/test_crs_generate.py`

**Interfaces:**
- Consumes: `Case`, `CASES`, `EPSG_CODES` (Task 2); `decode_geokeys`, `encode_geokeys` (Task 1); `core_of`, `point_for`, `project_point` (Task 3).
- Produces: `write_case(case: Case, path: Path) -> None`: `proj`/`epsg`/`wkt` via `rasterio.open(path, "w", driver="GTiff", width=8, height=8, count=1, dtype="uint8", crs=CRS.from_user_input(value), transform=from_origin(0, 0, 10, 10))` inside `rasterio.Env(GDAL_PAM_ENABLED="NO")`, writing zeros; `geokeys` via `tifffile.imwrite(path, zeros((8, 8), uint8), extratags=encode_geokeys(value))`. For `epsg`, `value` is `"EPSG:<code>"`.
- Produces: `read_back(path: Path) -> pyproj.CRS | None`: `rasterio.open` inside `Env(GDAL_PAM_ENABLED="NO")`, `CRS.from_user_input(ds.crs)` or None when `ds.crs` is falsy.
- Produces: `manifest_row(case: Case, path: Path, crs_dir: Path) -> dict` with the exact keys of spec 4.4: `name`, `file` (POSIX path of `path` relative to `crs_dir`), `input` (`{"kind", "value"}`), `note`, `tags` (list), `geokeys`, `gdal` (`{"projjson", "proj4", "roundtrip"}`; `proj4` None when `to_proj4()` raises `CRSError`; `roundtrip` is `CRS.from_user_input(input).equals(read_back)` for non-`geokeys` kinds, None for `geokeys`; all None when read-back is None), `core` (None when read-back is None), `point` (`{"lon", "lat", "x", "y"}` or None when `projjson` or `proj4` is None), `epsg_json` (`"epsg/<code>.json"` for `epsg`, else None).
- Produces: `fetch_epsg_json(code: int, epsg_dir: Path, *, refresh: bool = False) -> Path`: GET `https://epsg.io/<code>.json` with `urllib.request` only when the file is missing or `refresh`; writes it verbatim.
- Produces: `generate(crs_dir: Path, *, refresh_epsg: bool = False) -> dict`: writes every case to `crs_dir / "fixtures" / f"{name}.tif"`, builds rows, fetches epsg JSON, writes `crs_dir / "manifest.json"` with `{"schema_version": 1, "generator": {...}, "cases": rows_sorted_by_name}`; `generator` is `{"gdal": rasterio.__gdal_version__, "proj": rasterio.__proj_version__, "rasterio": rasterio.__version__, "pyproj": pyproj.__version__}`. `main()` parses `--refresh-epsg` and calls `generate(Path(__file__).parent)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_crs_generate.py
from pathlib import Path

from crs.cases import Case
from crs.generate_crs import fetch_epsg_json, manifest_row, read_back, write_case

TMERC = Case("tmerc", "proj", "+proj=tmerc +lat_0=0 +lon_0=-3.5 +k=0.9996 +x_0=500000 +y_0=0 +ellps=WGS84")


def test_write_and_read_back_proj_case(tmp_path: Path):
    path = tmp_path / "tmerc.tif"
    write_case(TMERC, path)
    assert not (tmp_path / "tmerc.tif.aux.xml").exists()
    crs = read_back(path)
    assert crs is not None
    assert crs.coordinate_operation.method_code == "9807"


def test_manifest_row_proj_case(tmp_path: Path):
    path = tmp_path / "fixtures" / "tmerc.tif"
    path.parent.mkdir()
    write_case(TMERC, path)
    row = manifest_row(TMERC, path, tmp_path)
    assert row["file"] == "fixtures/tmerc.tif"
    assert row["input"] == {"kind": "proj", "value": TMERC.value}
    assert row["geokeys"]["ProjCoordTrans"] == 1
    assert row["geokeys"]["ProjectedCSType"] == 32767
    assert row["gdal"]["roundtrip"] is True
    assert row["gdal"]["proj4"].startswith("+proj=tmerc +lat_0=0 +lon_0=-3.5")
    assert row["gdal"]["projjson"]["type"] == "ProjectedCRS"
    assert row["core"]["method"]["epsg"] == 9807
    assert row["point"]["lon"] == -0.5 and row["point"]["lat"] == 8.0
    assert row["epsg_json"] is None


def test_manifest_row_keyless_case(tmp_path: Path):
    case = Case("eqearth", "proj", "+proj=eqearth +lon_0=0 +ellps=WGS84", note="no keys")
    path = tmp_path / "eqearth.tif"
    write_case(case, path)
    row = manifest_row(case, path, tmp_path)
    assert row["gdal"] == {"projjson": None, "proj4": None, "roundtrip": None}
    assert row["core"] is None and row["point"] is None
    assert row["note"] == "no keys"


def test_manifest_row_geokeys_case(tmp_path: Path):
    case = Case("pm_epsg", "geokeys", {"GTModelType": 2, "GTRasterType": 1, "GeographicType": 32767, "GeogGeodeticDatum": 32767, "GeogEllipsoid": 7030, "GeogPrimeMeridian": 8903, "GeogAngularUnits": 9102})
    path = tmp_path / "pm_epsg.tif"
    write_case(case, path)
    row = manifest_row(case, path, tmp_path)
    assert row["geokeys"] == case.value
    assert row["gdal"]["roundtrip"] is None
    assert row["core"]["prime_meridian_deg"] == pytest.approx(2.33722917)


def test_manifest_row_epsg_case(tmp_path: Path):
    case = Case("epsg_32633", "epsg", "EPSG:32633")
    path = tmp_path / "epsg_32633.tif"
    write_case(case, path)
    row = manifest_row(case, path, tmp_path)
    assert row["geokeys"]["ProjectedCSType"] == 32633
    assert row["epsg_json"] == "epsg/32633.json"


def _no_network(*args, **kwargs):
    raise AssertionError("network used")


def test_fetch_epsg_json_skips_existing(tmp_path: Path, monkeypatch):
    existing = tmp_path / "32633.json"
    existing.write_text("{}")
    monkeypatch.setattr("urllib.request.urlopen", _no_network)
    assert fetch_epsg_json(32633, tmp_path) == existing
```

(Add `import pytest` for `approx`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run pytest tests/test_crs_generate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crs.generate_crs'`

- [ ] **Step 3: Implement `crs/generate_crs.py`**

Guard `main()` with `if __name__ == "__main__":`. `point` for a row: `lon, lat = point_for(core)`, `x, y = project_point(crs, lon, lat)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pixi run pytest tests/test_crs_generate.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add crs/generate_crs.py tests/test_crs_generate.py
git commit -m "feat(crs): Add the corpus generator"
```

### Task 5: Generate the corpus; wire pixi, check.sh, info.sh, README

**Files:**
- Modify: `pixi.toml` (`[tasks]`: `generate-crs = "python -m crs.generate_crs"`)
- Modify: `scripts/check.sh` (run `pixi run generate-crs` after `pixi run generate`)
- Modify: `scripts/info.sh` (`find . -path ./crs -prune -o -name "*.tif" -type f -print`)
- Modify: `README.md` (one paragraph under Usage pointing at `crs/README.md`)
- Create: `crs/README.md`, `crs/fixtures/*.tif`, `crs/manifest.json`, `crs/epsg/*.json`

**Interfaces:**
- Consumes: `generate` via the pixi task.

- [ ] **Step 1: Add the pixi task and script changes**

- [ ] **Step 2: Generate**

Run: `pixi run generate-crs`
Expected: `crs/fixtures/` holds one `.tif` per case (about 97 files, each under 2 KB), `crs/epsg/` holds 46 JSON files, `crs/manifest.json` exists, and no `.aux.xml` anywhere under `crs/`. If the network is unavailable, copy the 46 cached files from the prior session's scratchpad (`.../scratchpad/prior/epsg/`) into `crs/epsg/` first.

- [ ] **Step 3: Check determinism**

Run: `pixi run generate-crs && git status --porcelain crs/`
Expected: after a second run, `git status` shows only the first run's untracked files (no modified files between runs). Then `bash scripts/check.sh` must pass once everything is committed.

- [ ] **Step 4: Inspect the manifest for surprises**

Run: `pixi run python -c "import json; m=json.load(open('crs/manifest.json')); print([c['name'] for c in m['cases'] if c['gdal']['projjson'] is None or c['gdal']['proj4'] is None]); print([c['name'] for c in m['cases'] if c['input']['kind']=='proj' and c['geokeys'].get('ProjectedCSType', 32767) != 32767])"`
Expected: first list is exactly `['eqearth', 'stere_polar_scaled_wkt']`; second list is empty. If a `proj` case was identified as an EPSG code, change its parameters in `cases.py` (spec 4.3) and regenerate.

- [ ] **Step 5: Write `crs/README.md`**

Sections: what the corpus is and that GDAL/PROJ is the oracle; how to regenerate (`pixi run generate-crs`, `--refresh-epsg`); case kinds; the manifest schema (copy spec 4.4 with the no-suffix key naming and the `axes` list); the table schema (copy spec 5.1-5.2, including the `when` grammar and the three rules); which rows are flagged and why; links to the libgeotiff/GDAL/PROJ sources with the pinned commit and tag.

- [ ] **Step 6: Commit**

```bash
git add pixi.toml scripts/check.sh scripts/info.sh README.md crs/README.md crs/fixtures crs/manifest.json crs/epsg
git commit -m "feat(crs): Generate the conformance corpus and manifest"
```

### Task 6: CT table

**Files:**
- Create: `crs/geotiff-ct-methods.json`
- Test: `tests/test_crs_table.py`

**Interfaces:**
- Produces: the JSON of spec 5.1-5.3: `schema_version: 1`, `sources`, `units`, `methods` keyed by CT code string for 1-28 and 9815; 2, 5, 6 carry only `ct_name` and `unsupported`; 7 has two variants (`{"present": "ProjStdParallel1"}` first); 15 has three (`{"value": {"param": "Scale factor at natural origin", "equals": 1}}`, then `{"abs_value": {"param": "Latitude of natural origin", "equals": 90}}`, then an `unrepresentable` default); 27 has `"axes": ["west", "south"]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_crs_table.py
import json
from pathlib import Path

TABLE = json.loads((Path(__file__).parent.parent / "crs/geotiff-ct-methods.json").read_text())
MANIFEST = json.loads((Path(__file__).parent.parent / "crs/manifest.json").read_text())
KINDS = {"angular", "linear", "scale", "azimuth"}
RULE_KEYS = {"present", "abs_value", "value", "any", "all"}


def _rule_ok(rule: dict) -> bool:
    (key, body), = rule.items()
    if key in ("any", "all"):
        return all(_rule_ok(r) for r in body)
    if key == "present":
        return isinstance(body, str)
    return set(body) == {"param", "equals"} and key in RULE_KEYS


def test_table_covers_every_ct_code():
    assert set(TABLE["methods"]) == {str(c) for c in range(1, 29)} | {"9815"}
    assert {c for c, m in TABLE["methods"].items() if "unsupported" in m} == {"2", "5", "6"}


def test_variants_are_well_formed():
    for code, method in TABLE["methods"].items():
        if "unsupported" in method:
            assert set(method) == {"ct_name", "unsupported"}
            continue
        variants = method["variants"]
        assert "when" not in variants[-1]
        for v in variants[:-1]:
            assert _rule_ok(v["when"])
        for v in variants:
            if "unrepresentable" in v:
                continue
            assert set(v["method"]) == {"name", "epsg", "proj"}
            for p in v["parameters"]:
                assert set(p) >= {"name", "epsg", "proj", "kind", "keys", "default"}
                assert p["kind"] in KINDS
                assert p["keys"] and all(k in TABLE["units"]["angular_keys"] + TABLE["units"]["linear_keys"] + ["ProjScaleAtNatOrigin", "ProjScaleAtCenter", "ProjAzimuthAngle"] for k in p["keys"])
            assert v.get("axes", ["east", "north"]) in (["east", "north"], ["west", "south"])
            assert "gdal" in v
        assert "libgeotiff" in method


def test_variant_rules():
    assert TABLE["methods"]["7"]["variants"][0]["when"] == {"present": "ProjStdParallel1"}
    assert TABLE["methods"]["15"]["variants"][0]["when"] == {"value": {"param": "Scale factor at natural origin", "equals": 1}}
    assert TABLE["methods"]["15"]["variants"][1]["when"] == {"abs_value": {"param": "Latitude of natural origin", "equals": 90}}
    assert "unrepresentable" in TABLE["methods"]["15"]["variants"][2]
    assert TABLE["methods"]["27"]["variants"][0]["axes"] == ["west", "south"]


def test_every_supported_method_has_a_fixture():
    seen = {str(c["geokeys"].get("ProjCoordTrans")) for c in MANIFEST["cases"]}
    for code, method in TABLE["methods"].items():
        if "unsupported" not in method:
            assert code in seen, code


def test_every_fixture_ct_code_is_in_table():
    for c in MANIFEST["cases"]:
        ct = c["geokeys"].get("ProjCoordTrans")
        if ct is not None:
            assert str(ct) in TABLE["methods"], c["name"]


def test_table_method_names_match_manifest():
    """For every tested fixture with a CT code, the method GDAL read is one of the table's variants."""
    for c in MANIFEST["cases"]:
        ct = c["geokeys"].get("ProjCoordTrans")
        if ct is None or c["gdal"]["proj4"] is None:
            continue
        names = {v["method"]["name"] for v in TABLE["methods"][str(ct)]["variants"] if "method" in v}
        assert c["core"]["method"]["name"] in names, (c["name"], c["core"]["method"]["name"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run pytest tests/test_crs_table.py -v`
Expected: FAIL with `FileNotFoundError` for `geotiff-ct-methods.json`

- [ ] **Step 3: Write `crs/geotiff-ct-methods.json`**

Transcribe spec 5.3 row by row, with each parameter's `keys` from the common fallbacks in spec 5.3 and the `kind` from spec 5.1. Method names and EPSG codes must match what `core.method` shows in the manifest for that CT code (the last test enforces this; fix the table, not the manifest). Parameter EPSG codes: 8801-8807 (natural origin, scale, FE, FN), 8821-8827 (false origin, 1st/2nd parallel, E/N at false origin), 8811-8817 (projection centre, azimuth, grid angle, scale, E/N at centre), 8823/8824 for standard parallels, 8832/8833 for Polar B's standard parallel / longitude of origin. Non-EPSG methods (Stereographic, Gnomonic, Miller, Robinson, Sinusoidal, Van Der Grinten, Azimuthal Equidistant and Equidistant Conic if PROJ reports no code) get `"epsg": null` on the method and the parameter names PROJ uses in the manifest.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pixi run pytest tests/test_crs_table.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add crs/geotiff-ct-methods.json tests/test_crs_table.py
git commit -m "feat(crs): Add the GeoTIFF CT code to PROJ method table"
```

### Task 7: Corpus integrity tests and PR

**Files:**
- Create: `tests/test_crs_corpus.py`
- Modify: `crs/README.md` (mention the tests)

**Interfaces:**
- Consumes: `decode_geokeys` (Task 1), `CASES` (Task 2), `crs/manifest.json` (Task 5).

- [ ] **Step 1: Write the tests**

```python
# tests/test_crs_corpus.py
import json
from pathlib import Path

import pytest

from crs.cases import CASES
from crs.geokeys import decode_geokeys

CRS_DIR = Path(__file__).parent.parent / "crs"
MANIFEST = json.loads((CRS_DIR / "manifest.json").read_text())
ROWS = {c["name"]: c for c in MANIFEST["cases"]}


def test_manifest_matches_case_list():
    assert sorted(ROWS) == sorted(c.name for c in CASES)
    assert [c["name"] for c in MANIFEST["cases"]] == sorted(ROWS)


@pytest.mark.parametrize("name", sorted(ROWS))
def test_fixture_geokeys_match_manifest(name: str):
    row = ROWS[name]
    path = CRS_DIR / row["file"]
    assert path.exists()
    assert not path.with_name(path.name + ".aux.xml").exists()
    assert decode_geokeys(path) == row["geokeys"]


def test_proj_cases_are_user_defined():
    for row in MANIFEST["cases"]:
        if row["input"]["kind"] != "proj" or row["gdal"]["projjson"] is None:
            continue
        keys = row["geokeys"]
        assert keys.get("ProjectedCSType", 32767) == 32767, row["name"]
        assert keys.get("GeographicType", 32767) == 32767, row["name"]


def test_flagged_rows():
    flagged = {r["name"] for r in MANIFEST["cases"] if r["gdal"]["projjson"] is None or r["gdal"]["proj4"] is None}
    assert flagged == {"eqearth", "stere_polar_scaled_wkt"}
    assert all(ROWS[n]["note"] for n in flagged)


def test_epsg_rows_have_cached_json():
    for row in MANIFEST["cases"]:
        if row["input"]["kind"] == "epsg":
            assert (CRS_DIR / row["epsg_json"]).exists(), row["name"]


def test_point_rows():
    for row in MANIFEST["cases"]:
        if row["gdal"]["proj4"] is not None:
            assert set(row["point"]) == {"lon", "lat", "x", "y"}, row["name"]
```

- [ ] **Step 2: Run the full suite**

Run: `pixi run test && pixi run ruff check . 2>/dev/null || pixi run python -m ruff check .`
Expected: all tests pass (the per-fixture test runs ~97 times); ruff reports nothing. If `ruff` is not in the pixi env, run it via `uvx ruff check .` as CI's `ruff-action` does.

- [ ] **Step 3: Run the CI check script**

Run: `bash scripts/check.sh`
Expected: ends with "All generated files are up to date."

- [ ] **Step 4: Commit and push**

```bash
git add tests/test_crs_corpus.py crs/README.md
git commit -m "test(crs): Check fixtures, manifest, and table against each other"
git push -u origin kyle/crs-conformance-corpus
```

- [ ] **Step 5: Open the PR**

Title: `feat: Add a GeoKey-to-CRS conformance corpus and CT method table`. Body: the NOTE attribution line, a summary of the layout, how to regenerate, the two flagged rows and why, the four rows that depend on async-tiff#368, and the footer. Then report that it is ready for review; do not merge.
