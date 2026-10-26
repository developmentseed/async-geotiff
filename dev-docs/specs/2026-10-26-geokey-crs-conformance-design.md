# GeoKey to CRS conformance: corpus, CT table, and table-driven builder

- **Date:** 2026-10-26
- **Status:** Approved 2026-10-26 (answers to section 9 recorded there)
- **Repos:** `developmentseed/geotiff-test-data` (corpus + table), `developmentseed/async-geotiff` (builder + tests)
- **Out of scope:** `developmentseed/deck.gl-raster` (consumes the corpus and table later), anything upstream (pyproj, PROJ, GDAL, async-tiff) without explicit OK
- **Oracle:** whatever GDAL/PROJ reads from a file's GeoKeys, as seen through `rasterio`
- **Reference sources:** libgeotiff `geo_normalize.c` at commit `75cfca539667c6483e796b24b78ecef72e311a1a`; GDAL `frmts/gtiff/gt_wkt_srs.cpp` at tag `v3.12.1`; PROJ `src/iso19111/io.cpp` at tag `9.7.1`
- **Environment facts used here:** async-geotiff `.venv` has pyproj 3.7.2 on PROJ 9.5.1, rasterio 1.5.0 on GDAL 3.12.1 / PROJ 9.7.1, async-tiff 0.7.0. geotiff-test-data pixi env pins gdal 3.12.x, rasterio 1.5.x.

## 1. Intent

`src/async_geotiff/_crs.py` hand-builds PROJJSON from GeoKeys. Measured against GDAL on 36
GDAL-written files, 21 are wrong (see the task brief for the failure classes: rejected CT codes,
wrong Mercator and Polar Stereographic variants, units ignored, origin-key fallbacks missing, `a or
b` zero bugs, HOM variant and grid-angle mistakes, EPSG-coded datum dropped).

This work replaces guesswork with two shared, language-neutral artifacts and a small interpreter:

1. A **conformance corpus** in `geotiff-test-data`: GDAL-written GeoTIFFs plus a manifest recording
   the GeoKeys GDAL wrote and the CRS GDAL reads back.
2. A **CT table** (`crs/geotiff-ct-methods.json`): how each `ProjCoordTransGeoKey` code maps to a
   PROJ/EPSG method and how each parameter is read from GeoKeys, transcribed from libgeotiff and
   GDAL with line citations.
3. A rewrite of `_crs.py` that interprets the table and builds the CRS with pyproj's typed
   constructors, validated by a parametrized test over the corpus.

The TypeScript twin in deck.gl-raster will consume (1) and (2) unchanged.

## 2. Goals, non-goals, anti-goals

**Goals**

- Every GeoKey arrangement GDAL 3.12 can write for a user-defined projected or geographic CRS is in
  the corpus, and `async_geotiff` reads each one to a CRS that PROJ considers equal to GDAL's.
- The corpus and table are consumable offline by a TS test suite with no PROJ database (hence the
  cached `epsg.io` JSON and the normalized core in the manifest).
- The conformance suite is green from the first PR via a known-failures list that can only shrink.

**Non-goals**

- Writing GeoKeys. Vertical CRSs, geocentric model type, coordinate epoch. Non-GDAL writers'
  quirks (ESRI/Erdas state-plane citations) beyond what already works.
- Matching GDAL's CRS *names* beyond what equality requires (section 5).
- Changing deck.gl-raster in this effort.

**Anti-goals** (would make this a failure even if tests pass)

- A table transcribed from memory instead of from `GTIFFetchProjParms` / `GTIFGetOGISDefn`.
- A builder that constructs the conversion as a dict (silent parameter drops, see 6.3).
- A known-failures list that masks regressions: a listed case that starts passing must fail the run.

## 3. Facts established by probing (shape the design)

All verified in the async-geotiff `.venv` against GDAL-written files. The implementer can rerun the
probes from the prior session's `gen.py`/`py_probe.py` (copied to the session scratchpad).

- **Datum names are semantic, with one wildcard.** `pyproj.CRS.equals` and `rasterio.crs.CRS.__eq__`
  both return False when only the datum name differs, except that a datum named exactly `unknown`
  compares equal to any datum with the same ellipsoid and prime meridian (both PROJ and GDAL).
  Ellipsoid names, CRS names and conversion names do not affect equality. pyproj's default datum
  name `undefined` is *not* a wildcard.
- **Prime meridian names are semantic.** A PM named `Paris` at 2.33722917° equals GDAL's reading;
  the same longitude named `unknown` does not.
- **Parameter units:** `pyproj.CRS.equals` converts parameter units (46.8° vs 52 grad compare
  equal); GDAL's `IsSame` does not. The *coordinate system* unit is strict in both (a base
  geographic CRS in grads is not equal to one in degrees). Projected CS in US survey feet with
  conversion parameters given in metres compares equal to GDAL's reading (which keeps the
  parameters in feet).
- **`CoordinateOperation.from_string("+proj=sterea ...")` is unusable:** it yields a "PROJ-based
  operation method" with zero parameters. `CRS.from_proj4("+proj=sterea ... +ellps=WGS84")
  .coordinate_operation` yields a proper `Oblique Stereographic` (EPSG 9809) conversion with EPSG
  parameter ids, and that conversion can be attached to a different geodetic CRS via
  `ProjectedCRS(conversion=..., geodetic_crs=...)`. This is the fallback for methods without a
  typed class (6.3).
- **PROJJSON validation:** a misspelled parameter name without an `id` is silently dropped
  (value becomes 0). With a correct EPSG `id` alongside the misspelled name, PROJ 9.5 honours the
  id. The typed-constructor decision stands; the post-build check in 6.3 guards both paths.
- **`Datum.from_epsg(6326)`** returns the WGS 84 ensemble and compares equal to GDAL's reading of
  `GeogGeodeticDatumGeoKey = 6326`; `Datum.from_epsg(6267)` matches NAD27. `Ellipsoid.from_epsg`,
  `PrimeMeridian.from_epsg` and `CoordinateOperation.from_epsg(16033)` (UTM via
  `ProjectionGeoKey`) all produce equal CRSs.
- **Sphere:** `CustomEllipsoid(radius=...)` matches GDAL's reading of equal semi-major and
  semi-minor axes.
- **Axes:** GDAL reads CT 27 (TM South Orientated) with axes `Easting/west, Northing/south`;
  `Cartesian2DCS(axis="WESTING_SOUTHING")` reproduces that exactly. pyproj also has
  `EASTING_NORTHING_FT` and `EASTING_NORTHING_US_FT` presets for the two common foot units.
- **async-tiff (0.7.0, 0.7.2 and current `main`) exposes neither `GeogTOWGS84GeoKey` (2062)
  nor `ProjRectifiedGridAngleGeoKey` (3096)**, has no raw access by key id, and
  `ifd.other_tags` does not carry the GeoKey tags (34735-34737). GDAL writes 2062 for
  `+towgs84=` (read back as a `BoundCRS`) and 3096 for both Hotine Oblique Mercator variants and
  `somerc`. Until async-tiff exposes them, the `tmerc_towgs84`, `omerc_variant_a`,
  `omerc_variant_b` and `somerc` rows are known failures (open question Q2).
- **GDAL never writes `GeogPrimeMeridianGeoKey` codes**, even from WKT carrying
  `AUTHORITY["EPSG","8903"]`; it writes `GeogPrimeMeridianLongGeoKey` plus `Primem = Paris` in the
  citation. libgeotiff does read PM codes, so the builder supports them, and one fixture is written
  with tifffile to cover it (4.3).
- **GDAL's handling of a prime meridian in grads is internally inconsistent.** For
  `+pm=paris` input GDAL writes `GeogAngularUnitsGeoKey = 9105` and a PM longitude key of
  `0.0367131` (the degree value multiplied by the grad-to-radian factor), then reads it back as
  `0.0267639°` (three successive 0.9 factors). libgeotiff's own `GTIFAngleToDD` applies one factor.
  We follow libgeotiff, so this row is a documented permanent known failure (Q3); a grads fixture
  with Greenwich PM tests the angular-unit path cleanly.
- **GDAL writes no GeoKeys for methods it cannot encode** (Equal Earth) and instead writes a
  `.aux.xml` sidecar. The generator must disable PAM so the manifest records what the TIFF alone
  carries. Mollweide and Krovak get an `ESRI PE String` citation under `GTModelTypeGeoKey = 32767`
  (already handled by `_esri_pe_string`).
- **GDAL identifies conversions:** TM with `lon_0=129, k=0.9996, x_0=500000` is written as
  `ProjectionGeoKey = 16052` (UTM 52N) with no CT key. The corpus keeps such a case deliberately
  and otherwise avoids parameters that collapse to EPSG codes.
- **Polar Stereographic variant** is decided by *values*, not by key presence: GDAL always writes
  `ProjScaleAtNatOriginGeoKey` for polar files (1.0 when unused) and never `ProjStdParallel1`.
  `lat_0 = 71, k = 1` reads back as variant B; `lat_0 = 90, k = 0.994` as variant A. PROJ 9.7.1
  `io.cpp` L4231-L4279 is the deciding code: scale exactly 1 → variant B, else latitude at a pole
  → variant A, else a non-EPSG `Polar_Stereographic` method. The brief's stated rule is therefore
  replaced by the one in 5.2 (see Q1).

## 4. Corpus (geotiff-test-data)

### 4.1 Layout

```
crs/
  README.md                 # what this is, how to regenerate, schema of manifest + table
  cases.py                  # the case list (data only)
  generate_crs.py           # writes fixtures/, manifest.json, fetches missing epsg/ files
  geotiff-ct-methods.json   # the CT table (section 5)
  manifest.json             # one row per fixture
  fixtures/<name>.tif       # 8x8 uint8, uncompressed, plain GTiff (no overviews, no COG)
  epsg/<code>.json          # cached https://epsg.io/<code>.json, one per EPSG case
```

My calls, deviating from the repo's one-script-per-fixture convention:

- One table-driven generator instead of ~90 fixture scripts, because the cases are data.
- `pixi run generate-crs` task; `scripts/check.sh` runs it after `generate` so CI verifies the
  corpus is reproducible from `cases.py` with the pinned GDAL.
- `scripts/info.sh` skips `crs/` (the manifest documents these files; 90 `_info.md` files add
  nothing).
- Fixtures are plain GTiff via `rasterio.open(..., driver="GTiff")`, not `write_cog`, written
  inside `rasterio.Env(GDAL_PAM_ENABLED="NO")`.
- The `epsg/` fetch happens only when the file is missing (offline regeneration works);
  `--refresh-epsg` refetches.

### 4.2 Case forms

Each case in `cases.py` is a dataclass `Case(name, kind, value, note="", tags=())` with
`kind in {"proj", "epsg", "wkt"}`:

- `proj`: a PROJ string. GDAL converts it to user-defined GeoKeys. The code path under test.
- `epsg`: an EPSG code. GDAL writes coded keys. The generator also caches `epsg/<code>.json`.
- `wkt`: a WKT1 string (ESRI or OGC). Used where a PROJ string cannot express the input (prime
  meridian in degrees with a name, grads with Greenwich, Polar Stereographic with
  `latitude_of_origin != 90` and `scale != 1`, ESRI-named CRSs).

### 4.3 Case list

Seeded from the prior session's `gen.py`, then made systematic. Names are the fixture stems.

**One per CT code GDAL can write** (write side of `gt_wkt_srs.cpp`, `GTIFSetFromOGISDefnEx`;
CT codes 2, 5 and 6 have no GDAL write or read case and get no fixture):

| CT | name | input |
|---|---|---|
| 1 | `tmerc` | `+proj=tmerc +lat_0=0 +lon_0=-3.5 +k=0.9996 +x_0=500000 +y_0=0 +ellps=WGS84` |
| 3 | `omerc_variant_a` | `+proj=omerc ... +no_uoff +ellps=WGS84` (prior `omerc_nouoff`) |
| 4 | `labrd` | `+proj=labrd +lat_0=-18.9 +lon_0=46.43722917 +azi=18.9 +k=0.9995 +x_0=400000 +y_0=800000 +ellps=intl` |
| 7 | `merc_1sp` | `+proj=merc +lon_0=10 +k=0.98 +ellps=WGS84` |
| 7 | `merc_2sp` | `+proj=merc +lat_ts=30 +lon_0=10 +ellps=WGS84` |
| 8 | `lcc_2sp` | `+proj=lcc +lat_1=33 +lat_2=45 +lat_0=23 +lon_0=-96 +ellps=WGS84` |
| 9 | `lcc_1sp` | `+proj=lcc +lat_1=46.8 +lat_0=46.8 +lon_0=2.3 +k_0=0.99987742 +x_0=600000 +y_0=2200000 +ellps=clrk80ign` |
| 10 | `laea` | `+proj=laea +lat_0=52 +lon_0=10 +x_0=4321000 +y_0=3210000 +ellps=GRS80` |
| 11 | `aea` | `+proj=aea +lat_1=29.5 +lat_2=45.5 +lat_0=23 +lon_0=-96 +ellps=WGS84` |
| 12 | `aeqd` | `+proj=aeqd +lat_0=40 +lon_0=-100 +ellps=WGS84` |
| 13 | `eqdc` | `+proj=eqdc +lat_1=33 +lat_2=45 +lat_0=23 +lon_0=-96 +ellps=WGS84` |
| 14 | `stere_oblique` | `+proj=stere +lat_0=46.5 +lon_0=-66.5 +k=0.999912 +ellps=WGS84` |
| 15 | `stere_polar_a` | `+proj=stere +lat_0=90 +k=0.994 +lon_0=0 +ellps=WGS84` |
| 15 | `stere_polar_b` | `+proj=stere +lat_0=90 +lat_ts=71 +lon_0=-45 +ellps=WGS84` |
| 15 | `stere_south_a` | `+proj=stere +lat_0=-90 +k=0.994 +lon_0=0 +ellps=WGS84` |
| 15 | `stere_south_b` | `+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +ellps=WGS84` |
| 15 | `stere_polar_scaled_wkt` | WKT1 `Polar_Stereographic` with `latitude_of_origin=71`, `scale_factor=0.9` (pins PROJ's fall-through case in 5.2; flagged, `gdal.proj4` null) |
| 15 | `stere_polar_k1_wkt` | WKT1 `Polar_Stereographic` with `latitude_of_origin=90`, `scale_factor=1` (pins that scale 1 wins over the pole: variant B with `lat_ts = 90`) |
| 16 | `sterea` | `+proj=sterea +lat_0=52.15616055555555 +lon_0=5.38763888888889 +k=0.9999079 +x_0=155000 +y_0=463000 +ellps=bessel` |
| 17 | `eqc` | `+proj=eqc +lat_ts=30 +lon_0=10 +ellps=WGS84` |
| 18 | `cass` | `+proj=cass +lat_0=10 +lon_0=-61 +ellps=WGS84` |
| 19 | `gnom` | `+proj=gnom +lat_0=40 +lon_0=-100 +ellps=WGS84` |
| 20 | `mill` | `+proj=mill +lon_0=0 +ellps=WGS84` |
| 21 | `ortho` | `+proj=ortho +lat_0=40 +lon_0=-100 +ellps=WGS84` |
| 22 | `poly` | `+proj=poly +lat_0=0 +lon_0=-54 +ellps=WGS84` |
| 23 | `robin` | `+proj=robin +lon_0=0 +ellps=WGS84` |
| 24 | `sinu_sphere` | `+proj=sinu +lon_0=0 +x_0=0 +y_0=0 +R=6371007.181` |
| 25 | `vandg` | `+proj=vandg +lon_0=0 +ellps=WGS84` |
| 26 | `nzmg` | `+proj=nzmg +lat_0=-41 +lon_0=173 +x_0=2510000 +y_0=6023150 +ellps=intl` |
| 27 | `tmso` | `+proj=tmerc +lat_0=0 +lon_0=19 +k=1 +x_0=0 +y_0=0 +axis=wsu +ellps=WGS84` |
| 28 | `cea` | `+proj=cea +lat_ts=31 +lon_0=0 +ellps=WGS84` |
| 9815 | `omerc_variant_b` | `+proj=omerc +lat_0=4 +lonc=102.25 +alpha=323.0257964666666 +gamma=323.1301023611111 +k=0.99984 +x_0=804671 +y_0=0 +ellps=WGS84` |
| 9815 | `somerc` | `+proj=somerc +lat_0=46.95240555555556 +lon_0=7.439583333333333 +k_0=1 +x_0=600000 +y_0=200000 +ellps=bessel` (GDAL writes azimuth 90, reads back `+proj=somerc`) |

**Units** (linear parameters are written in the projected unit; angular in `GeogAngularUnits`):

| name | input |
|---|---|
| `lcc_2sp_usft` | `+proj=lcc +lat_1=41.03333 +lat_2=40.66667 +lat_0=40.16667 +lon_0=-74 +x_0=300000 +y_0=0 +ellps=GRS80 +units=us-ft` (prior `tmerc_usft`) |
| `tmerc_ft` | `tmerc` with `+units=ft` (international foot, 9002) |
| `lcc_1sp_grad_wkt` | WKT1 LCC 1SP, `UNIT["grad",0.01570796326794897]`, Greenwich PM |
| `geog_grad_wkt` | WKT1 GEOGCS in grads, Greenwich PM |
| `lcc_1sp_paris_grad` | `lcc_1sp` with `+lon_0=0 +pm=paris` (GDAL writes grads; see Q3) |

**Datum, ellipsoid, prime meridian variants:**

| name | input | exercises |
|---|---|---|
| `aea_nad27` | `+proj=aea ... +datum=NAD27` | `GeogGeodeticDatumGeoKey = 6267`, axes present, no ellipsoid key |
| `tmerc_datum_wgs84` | `tmerc` with `+datum=WGS84` | `GeogGeodeticDatumGeoKey = 6326` |
| `tmerc` (above) | | `GeogEllipsoidGeoKey = 7030` plus axes, user-defined datum |
| `sterea`, `nzmg`, `lcc_1sp` | | ellipsoid 32767 with explicit axes (no EPSG match) |
| `sinu_sphere`, `geog_sphere` | `+R=` | semi-minor = semi-major, no inverse flattening |
| `tmerc_towgs84` | `+proj=tmerc +lat_0=0 +lon_0=9 +k=1 +x_0=3500000 +y_0=0 +ellps=bessel +towgs84=598.1,73.7,418.2,0.202,0.045,-2.455,6.7` | `GeogTOWGS84GeoKey` (Q2) |
| `lcc_1sp_paris_deg_wkt` | WKT1 with `PRIMEM["Paris",2.33722917]`, degrees | PM longitude key + `Primem = Paris` citation |
| `lcc_1sp_pm_user` | `lcc_1sp` with `+lon_0=0 +pm=2.5` | PM longitude key, `Primem = unknown` |
| `lcc_1sp_pm_epsg_tifffile` | written with tifffile: same keys as `lcc_1sp` but `GeogPrimeMeridianGeoKey = 8903`, no PM longitude key | EPSG-coded PM (GDAL never writes one) |
| `longlat_grs80` | `+proj=longlat +ellps=GRS80` | user-defined geographic CRS |
| `utm_bessel` | `+proj=utm +zone=33 +ellps=bessel` | `ProjectionGeoKey = 16033`, no CT key, user-defined datum |

**Coded and citation forms:**

| name | input |
|---|---|
| `epsg_<code>` for each of 2039, 2046, 2056, 2057, 2065, 2100, 2154, 21781, 2193, 2263, 26917, 27572, 27700, 28992, 2953, 3031, 3035, 3067, 3088, 31370, 32633, 32661, 32761, 3301, 3310, 3338, 3347, 3375, 3395, 3408, 3410, 3413, 3857, 3975, 3978, 3993, 4087, 4326, 4267, 5070, 5514, 5880, 6318, 6933, 7845, 9377 | `EPSG:<code>` (the prior session's set, which covers one EPSG method each, plus 4267) |
| `moll` | `+proj=moll +lon_0=0 +ellps=WGS84` (ESRI PE String path) |
| `krovak` | `+proj=krovak +lat_0=49.5 +lon_0=24.83333333333333 +alpha=30.28813972222222 +k=0.9999 +x_0=0 +y_0=0 +ellps=bessel` (PE String) |
| `esri_54009` | `ESRI:54009` (PE String with `GeogGeodeticDatumGeoKey = 6326`) |
| `eqearth` | `+proj=eqearth +lon_0=0 +ellps=WGS84` (GDAL writes no keys; `gdal.projjson` is null; row flagged, not tested) |

The implementer may add cases; each must document which key arrangement it adds. Before adding a
PROJ-string case, confirm GDAL writes user-defined keys for it (not an EPSG code) by inspecting
the manifest row.

### 4.4 Manifest schema (`crs/manifest.json`)

```jsonc
{
  "schema_version": 1,
  "generator": {"gdal": "3.12.1", "proj": "9.7.1", "rasterio": "1.5.0", "pyproj": "3.7.2"},
  "cases": [
    {
      "name": "lcc_2sp_usft",
      "file": "fixtures/lcc_2sp_usft.tif",
      "input": {"kind": "proj", "value": "+proj=lcc ... +units=us-ft"},
      "note": "",                                  // free text, e.g. why a row is lossy
      "tags": ["ct:8", "linear:9003"],             // free-form, for filtering
      "geokeys": {                                 // exactly what GDAL wrote, by GeoTIFF key name (no "GeoKey" suffix)
        "GTModelType": 1, "GTRasterType": 1,
        "GeographicType": 32767, "GeogCitation": "GCS Name = unknown|...",
        "ProjCoordTrans": 8, "ProjLinearUnits": 9003,
        "ProjFalseOriginEasting": 984250.0, ...
      },
      "gdal": {
        "projjson": { ... },                       // rasterio read-back, pyproj.CRS.to_json_dict(); null if none
        "proj4": "+proj=lcc ... +units=us-ft +no_defs +type=crs",
        "roundtrip": true                          // CRS.from_user_input(input).equals(read-back)
      },
      "core": {                                    // normalized, name-free, for implementations without proj.db
        "type": "ProjectedCRS",                    // or GeographicCRS, BoundCRS
        "method": {"name": "Lambert Conic Conformal (2SP)", "epsg": 9802},
        "parameters": [                            // in degrees / metres / unity, keyed by EPSG parameter code
          {"epsg": 8821, "name": "Latitude of false origin", "value": 40.16667},
          {"epsg": 8826, "name": "Easting at false origin", "value": 300000.0}, ...
        ],
        "ellipsoid": {"a": 6378137.0, "rf": 298.257222101, "b": null},   // b only when rf is null (sphere)
        "prime_meridian_deg": 0.0,
        "angular_unit_deg": 1.0,                   // size of the geographic CS unit in degrees
        "linear_unit_m": 0.3048006096012192,       // size of the projected CS unit in metres (null for geographic)
        "axes": ["east", "north"],                 // axis directions in order; ["west", "south"] for CT 27
        "towgs84": null                            // 3 or 7 numbers for BoundCRS rows
      },
      "point": {"lon": -71.0, "lat": 48.16667, "x": 1722466.6689, "y": 2936519.5336},
      "epsg_json": null                            // "epsg/2953.json" for kind == "epsg"
    }
  ]
}
```

Rules:

- `geokeys` is decoded from the raw `GeoKeyDirectoryTag` (34735), `GeoDoubleParamsTag` (34736)
  and `GeoAsciiParamsTag` (34737) with tifffile, mapping key id to the GeoTIFF spec name. Reading
  raw keys rather than through async-tiff is deliberate: it records keys async-tiff does not yet
  expose (TOWGS84) and is independent of either implementation.
- `gdal.projjson` is `pyproj.CRS.from_user_input(rasterio_dataset.crs).to_json_dict()`; `null`
  when rasterio reports no CRS. `gdal.proj4` is `null` when PROJ cannot export the CRS (the
  off-pole scaled Polar Stereographic case). Rows with either `null` are excluded from equality
  tests by both implementations (that is what "flagged rather than tested" means); `note` says
  why.
- `core` is derived from `gdal.projjson`, not from the input. Parameter values are converted to
  degrees, metres or unity using the unit in the PROJJSON. Method name is PROJ's; `epsg` is null
  for non-EPSG methods (`Stereographic`).
- `point` is a lon/lat in degrees from Greenwich near the projection origin (reuse `gen.py`'s
  `point_for`), projected with `Transformer.from_crs(base, read_back_crs, always_xy=True)` where
  `base` is `+proj=longlat` on the read-back CRS's ellipsoid axes (degrees, Greenwich), so no
  datum shift is involved. For geographic rows the transform is still applied, so `(x, y)` is in
  the row's own angular unit and prime meridian. Null when `gdal.projjson` is null.
- The manifest is written with `indent=1`, sorted keys, and `cases` sorted by name, so diffs are
  reviewable and `check.sh` is stable.

### 4.5 Tests in geotiff-test-data

Add `tests/test_crs_corpus.py`:

- every manifest row's `file` exists and its raw GeoKeys equal the row's `geokeys` (guards against
  GDAL upgrades silently changing arrangements, like `test_real_data.py` does);
- every `ProjCoordTransGeoKey` value seen in the manifest has a row in `geotiff-ct-methods.json`;
- every table row that is not `unsupported` has at least one fixture;
- the table validates against the schema in 5.1 (a small hand-written check, no jsonschema dep).

## 5. CT table (`crs/geotiff-ct-methods.json`)

### 5.1 Schema

```jsonc
{
  "schema_version": 1,
  "sources": {
    "libgeotiff": "https://github.com/OSGeo/libgeotiff/blob/75cfca539667c6483e796b24b78ecef72e311a1a/libgeotiff/geo_normalize.c",
    "gdal": "https://github.com/OSGeo/gdal/blob/v3.12.1/frmts/gtiff/gt_wkt_srs.cpp",
    "proj": "https://github.com/OSGeo/PROJ/blob/9.7.1/src/iso19111/io.cpp"
  },
  "units": {                                   // applied once, outside the table (5.4)
    "linear": "ProjLinearUnits / ProjLinearUnitSize -> metres",
    "angular": "GeogAngularUnits / GeogAngularUnitSize -> degrees",
    "angular_keys": ["ProjStdParallel1", "ProjStdParallel2", "ProjNatOriginLong", "ProjNatOriginLat",
                     "ProjFalseOriginLong", "ProjFalseOriginLat", "ProjCenterLong", "ProjCenterLat",
                     "ProjStraightVertPoleLong", "ProjRectifiedGridAngle"],
    "linear_keys": ["ProjFalseEasting", "ProjFalseNorthing", "ProjFalseOriginEasting",
                    "ProjFalseOriginNorthing", "ProjCenterEasting", "ProjCenterNorthing"],
    "source": "geo_normalize.c#L2227-L2277"
  },
  "methods": {
    "<ct code as string>": {
      "ct_name": "CT_TransverseMercator",         // from geo_ctrans.inc
      "unsupported": "reason"                    // present only for 2, 5, 6; no other fields then
      "variants": [                              // one or more; first whose `when` matches wins; last has no `when`
        {
          "when": { ... },                       // see 5.2; omitted on the default variant
          "method": {"name": "Transverse Mercator", "epsg": 9807, "proj": "tmerc"},
          "axes": ["east", "north"],              // optional; default ["east", "north"]; CT 27 uses ["west", "south"]
          "parameters": [
            {
              "name": "Latitude of natural origin",   // EPSG/PROJ parameter name
              "epsg": 8801,                            // EPSG parameter code; null for non-EPSG methods
              "proj": "lat_0",                         // PROJ string key (for implementations building proj strings)
              "kind": "angular",                       // angular | linear | scale | azimuth
              "keys": ["ProjNatOriginLat", "ProjFalseOriginLat", "ProjCenterLat"],  // first present wins
              "default": 0.0
            }
          ],
          "gdal": "gt_wkt_srs.cpp#L1440-L1443"   // the `case CT_...:` in GTIFGetOGISDefn (or PROJ io.cpp for value rules)
        }
      ],
      "libgeotiff": "geo_normalize.c#L1774-L1816"  // the `case CT_...:` in GTIFFetchProjParms
    }
  }
}
```

Kinds: `angular` values are scaled by the angular unit factor; `linear` by the linear unit factor;
`scale` and `azimuth` are never scaled (`ProjAzimuthAngleGeoKey` is absent from libgeotiff's
normalization list at L2257-L2266, and GDAL's writer does not convert it either).

Key names are GeoTIFF spec names without the `GeoKey` suffix. Each implementation maps them to its
own accessors (async-tiff: `proj_nat_origin_lat`, etc.).

### 5.2 Variant rules (`when`)

Three rules exist. The grammar is deliberately tiny:

```jsonc
{"present": "ProjStdParallel1"}                       // key present in the directory
{"abs_value": {"param": "Latitude of natural origin", "equals": 90}}   // after unit normalization
{"value": {"param": "Scale factor at natural origin", "equals": 1}}
{"any": [ ... ]}  /  {"all": [ ... ]}
```

`param` refers to a parameter already resolved by the variant's own `keys`/`default` (rules are
evaluated after parameter resolution; both variants of a method resolve the same raw inputs).

- **CT 7 Mercator** (gt_wkt_srs.cpp L1450-L1465): `{"present": "ProjStdParallel1"}` selects
  `Mercator (variant B)` (EPSG 9805) with `Latitude of 1st standard parallel` from
  `ProjStdParallel1`; otherwise `Mercator (variant A)` (9804) with the scale factor. libgeotiff
  defaults the scale to 1 only when neither key is present (L1743-L1747); GDAL ignores the scale
  when the parallel is present.
- **CT 15 Polar Stereographic**: libgeotiff always yields lat, lon (from
  `ProjStraightVertPoleLong` first), scale (default 1), FE, FN (L2064-L2104); GDAL calls `SetPS`
  (L1559-L1562) which emits WKT1 `Polar_Stereographic`; PROJ's WKT1 importer picks the EPSG
  variant from values (PROJ 9.7.1 `io.cpp` L4231-L4279, verified):
  1. `{"value": {"param": "Scale factor at natural origin", "equals": 1}}` selects
     `Polar Stereographic (variant B)` (9829) with `Latitude of standard parallel` = the resolved
     latitude and `Longitude of origin` = the resolved longitude. This holds even when the
     latitude is ±90 (then `lat_ts = 90`).
  2. Otherwise `{"abs_value": {"param": "Latitude of natural origin", "equals": 90}}` selects
     `variant A` (9810) with the scale factor.
  3. Otherwise (scale ≠ 1 and latitude not at a pole) PROJ keeps a non-EPSG WKT1 method named
     `Polar_Stereographic` with WKT1 parameter names, and `to_proj4()` raises "CRS cannot be
     converted to a PROJ string" (verified with the `stere_polar_scaled_wkt` fixture). The table's
     third variant is `{"unrepresentable": "PROJ has no operation for Polar_Stereographic off the
     pole with scale != 1"}`; the builder raises `ValueError`; the manifest row has
     `gdal.proj4 == null` and is skipped (4.4).
  The `equals` form of `value` is added to the grammar above for this rule.
- **CT 3 vs 9815 vs 4** are separate CT codes, not variants: 3 is `Hotine Oblique Mercator
  (variant A)` (9812, GDAL `SetHOM`, L1489-L1492), 9815 is `variant B` (9815, `SetHOMAC`,
  L1494-L1498), 4 is `Laborde Oblique Mercator` (9813, `SetLOM`, L1500-L1503). All three read the
  same keys (libgeotiff L1819-L1870, L1873-L1917); variant B names its false origin parameters
  `Easting/Northing at projection centre` (8816/8817), variant A `False easting/northing`
  (8806/8807); Laborde has no rectified grid angle.

### 5.3 Rows to transcribe

Every row's `keys` order comes from `GTIFFetchProjParms`; every method from the `switch` in
`GTIFGetOGISDefn` (L1438-L1596). Common fallbacks (cite once in the README, repeat in each row):

- False easting: `ProjFalseEasting`, `ProjCenterEasting`, `ProjFalseOriginEasting` (L1655-L1661);
  northing likewise (L1663-L1669). Default 0.
- Longitude: `ProjNatOriginLong`, `ProjFalseOriginLong`, `ProjCenterLong`; latitude:
  `ProjNatOriginLat`, `ProjFalseOriginLat`, `ProjCenterLat`. Default 0. Used by every method with
  an origin (including HOM, which GDAL writes with `ProjCenter*`).
- Polar Stereographic longitude: `ProjStraightVertPoleLong` first, then the three above (L2066-L2074).
- Scale: `ProjScaleAtNatOrigin`, `ProjScaleAtCenter`, default 1 (L1795-L1800, L1846-L1850,
  L1939-L1943, L2084-L2088), except CT 14 Stereographic (L1696-L1698) and CT 7 Mercator
  (L1739-L1741), which read `ProjScaleAtNatOrigin` only. (Corrected 2026-10-26 after the corpus
  review; the first draft gave CT 7 the fallback.)
- Standard parallels: `ProjStdParallel1` / `ProjStdParallel2` only, default 0.
- Azimuth: `ProjAzimuthAngle`, default 0, kind `azimuth`. Rectified grid angle:
  `ProjRectifiedGridAngle`, default 90 (L1842-L1844), kind `angular`.

| CT | method (EPSG) | parameters (in GDAL `Set*` argument order) | libgeotiff | gdal |
|---|---|---|---|---|
| 1 | Transverse Mercator (9807), `tmerc` | lat_0, lon_0, k, FE, FN | L1774-L1816 | L1440 |
| 2 | unsupported: no GDAL read case (falls to `SetLocalCS`) | | | L1587 |
| 3 | Hotine Oblique Mercator (variant A) (9812), `omerc +no_uoff` | lat_c, lon_c, azimuth, rectified grid angle, k_c, FE, FN | L1819-L1870 | L1489 |
| 4 | Laborde Oblique Mercator (9813), `labrd` | lat_c, lon_c, azimuth, k_c, FE, FN | L1873-L1917 | L1500 |
| 5 | unsupported (no GDAL read case) | | | L1587 |
| 6 | unsupported (no GDAL read case) | | | L1587 |
| 7 | Mercator A (9804) / B (9805), `merc` | see 5.2 | L1717-L1771 | L1450 |
| 8 | Lambert Conic Conformal (2SP) (9802), `lcc` | lat_1, lat_2, lat_0 (false origin), lon_0, FE, FN | L2107-L2149 | L1564 |
| 9 | Lambert Conic Conformal (1SP) (9801), `lcc` | lat_0, lon_0, k, FE, FN | L1774-L1816 | L1569 |
| 10 | Lambert Azimuthal Equal Area (9820), `laea` | lat_0, lon_0, FE, FN | L1962-L1997 | L1537 |
| 11 | Albers Equal Area (9822), `aea` | lat_1, lat_2, lat_0, lon_0, FE, FN | L2152-L2195 | L1574 |
| 12 | Azimuthal Equidistant (1125 / PROJ name), `aeqd` | lat_0, lon_0, FE, FN | L1962-L1997 | L1519 |
| 13 | Equidistant Conic (1119 / PROJ name), `eqdc` | lat_1, lat_2, lat_0, lon_0, FE, FN | L2152-L2195 | L1505 |
| 14 | Stereographic (PROJ, no EPSG code), `stere` | lat_0, lon_0, k, FE, FN | L1678-L1714 | L1484 |
| 15 | Polar Stereographic A (9810) / B (9829), `stere` | see 5.2 | L2064-L2104 | L1559 |
| 16 | Oblique Stereographic (9809), `sterea` | lat_0, lon_0, k, FE, FN | L1774-L1816 | L1479 |
| 17 | Equidistant Cylindrical (1028), `eqc` | lat_0, lon_0, lat_1 (`ProjStdParallel1`), FE, FN | L2000-L2036 | L1527 |
| 18 | Cassini-Soldner (9806), `cass` | lat_0, lon_0, FE, FN (libgeotiff also reads a scale; GDAL ignores it) | L1920-L1959 | L1510 |
| 19 | Gnomonic (PROJ), `gnom` | lat_0, lon_0, FE, FN | L1962-L1997 | L1532 |
| 20 | Miller Cylindrical (PROJ), `mill` | lat_0, lon_0, FE, FN | L1962-L1997 | L1523 |
| 21 | Orthographic (9840), `ortho` | lat_0, lon_0, FE, FN | L1962-L1997 | L1542 |
| 22 | American Polyconic (9818), `poly` | lat_0, lon_0, FE, FN (scale read, ignored) | L1920-L1959 | L1514 |
| 23 | Robinson (PROJ), `robin` | lon_0, FE, FN | L2039-L2061 | L1547 |
| 24 | Sinusoidal (PROJ), `sinu` | lon_0, FE, FN | L2039-L2061 | L1551 |
| 25 | Van Der Grinten (PROJ), `vandg` | lon_0, FE, FN | L2039-L2061 | L1555 |
| 26 | New Zealand Map Grid (9811), `nzmg` | lat_0, lon_0, FE, FN | L1962-L1997 | L1579 |
| 27 | Transverse Mercator (South Orientated) (9808), `tmerc +axis=wsu`; `axes: ["west", "south"]` | lat_0, lon_0, k, FE, FN | L1774-L1816 | L1445 |
| 28 | Lambert Cylindrical Equal Area (9835), `cea` | lat_1 (`ProjStdParallel1`), lon_0, FE, FN | L2198-L2224 | L1584 |
| 9815 | Hotine Oblique Mercator (variant B) (9815), `omerc` | lat_c, lon_c, azimuth, rectified grid angle, k_c, E_c, N_c | L1819-L1870 | L1494 |

Method names and EPSG codes in the table must be what PROJ 9.7 emits in `gdal.projjson` for the
corresponding fixture (the generator output is the authority; where this spec and the manifest
disagree, fix the table to the manifest and note it in the PR).

### 5.4 What the table does not contain

- Unit normalization (one pass over resolved parameters, keyed by `kind`).
- The geographic CRS (datum, ellipsoid, prime meridian, angular unit), the projected CS unit, the
  `ProjectionGeoKey` EPSG path, the ESRI PE String path. These are described in section 6 and are
  the same for every method. The only per-method CS facts are axis directions: CT 27's axes
  point west/south (`axes` field), and CT 15's point both south for a positive latitude and both
  north for a negative one (a sign rule the table states in a note and the README spells out; the
  corpus pins it). The manifest `core` records `axes` for every row. (Corrected 2026-10-26: the
  first draft said CT 27 was the only exception.) In the builder, use pyproj's
  `Cartesian2DCS(axis="NORTH_POLE_EASTING_SOUTH_NORTHING_SOUTH")` and
  `SOUTH_POLE_EASTING_NORTH_NORTHING_NORTH` presets for CT 15.

## 6. Equality and builder design (async-geotiff)

### 6.1 Equality definition

The conformance assertion is

```python
expected = pyproj.CRS.from_json_dict(row["gdal"]["projjson"])
assert expected.equals(geotiff.crs)        # ignore_axis_order=False
```

This is PROJ's `EQUIVALENT` comparison: unit-converting on parameters, strict on datum and prime
meridian names (with the `unknown` wildcard), strict on coordinate-system units, indifferent to
CRS/conversion/ellipsoid names and ids. It is stronger than the normalized core and is what the
Python side uses. The `core` object in the manifest is the TS side's comparison target and the
documented meaning of "equal" for implementations without PROJ.

Consequences for the builder (all verified in section 3):

- Datum name: `Datum = ...` from `GeogCitationGeoKey` when present, else the proj.db name for an
  EPSG-coded datum, else `unknown`. Never `undefined`.
- Prime meridian name: `Primem = ...` from the citation when present, else proj.db for a coded PM,
  else `Greenwich` when longitude is 0, else `unknown`.
- Base geographic CS must carry the file's angular unit (grads files). Projected CS must carry the
  file's linear unit.

### 6.2 Module structure

`_crs.py` keeps its public surface (`crs_from_geo_keys`, `projjson_from_geo_keys`) and is split
internally:

```
_crs.py              crs_from_geo_keys / projjson_from_geo_keys; dispatch on model type;
                     EPSG-coded PCS/GCS; ESRI PE String (unchanged)
_crs_geographic.py   geographic CRS from keys: units, ellipsoid, datum, prime meridian, citation parsing
_crs_conversion.py   the table interpreter: resolve parameters, pick variant, normalize units,
                     build the pyproj conversion, post-build validation
_crs_table.py        the table, loaded from a JSON file vendored into the package
                     (src/async_geotiff/data/geotiff-ct-methods.json, copied verbatim from the
                     submodule by a script and checked for equality in a test)
```

My call on vendoring: the installed package cannot read from `fixtures/`, so the JSON is copied
into the package; `tests/test_crs_table.py` asserts the vendored copy equals the submodule copy
so they cannot drift.

### 6.3 Conversion builder

Inputs: the `GeoKeyDirectory`, the resolved linear unit factor (metres) and angular unit factor
(degrees) from 6.4.

1. If `ProjCoordTransGeoKey` is absent and `ProjectionGeoKey` is a code, return
   `CoordinateOperation.from_epsg(code)` (existing behaviour; `utm_bessel` covers it).
2. Look up the CT row. `unsupported` raises `ValueError` naming the CT code and reason.
3. For each parameter of the first variant (all variants of a method share raw inputs): take the
   first present key in `keys`, else `default`. "Present" means the accessor returns not-None;
   `0.0` is present. No `a or b`. The key-name-to-accessor mapping is an explicit dict; a table
   key with no accessor (today: `ProjRectifiedGridAngle`) raises `ValueError` naming the key
   rather than being treated as absent, because silently defaulting it (to 90) produces a wrong
   CRS with no signal. This is what makes the HOM rows known failures until async-tiff exposes
   key 3096 (Q2).
4. Scale `angular` by the angular factor and `linear` by the linear factor. `scale` and `azimuth`
   untouched.
5. Evaluate `when` rules in order; pick the variant.
6. Build the conversion:
   - Methods with a typed class in `pyproj.crs.coordinate_operation` (TM, Mercator A/B, LCC
     1SP/2SP, Albers, LAEA, AEQD, Polar Stereographic A/B, Stereographic, Orthographic,
     Equidistant Cylindrical, Sinusoidal, Lambert Cylindrical Equal Area, HOM variant B): call the
     class with keyword arguments. A per-class dict maps EPSG parameter code to keyword name, so a
     typo is a `TypeError` at import time of the test suite, not a silent drop.
   - Everything else (Oblique Stereographic, Cassini-Soldner, Polyconic, NZMG, HOM variant A,
     Laborde, TM South Orientated, Equidistant Conic, Gnomonic, Miller, Robinson, Van der
     Grinten): build `+proj=<proj> +<key>=<value> ... +ellps=WGS84` from the row's `proj` names,
     `CRS.from_proj4(...)`, take `.coordinate_operation`. The ellipsoid is a placeholder; the
     conversion is re-attached to the real geodetic CRS in 6.5.
7. **Post-build validation** (guards both paths against silent drops): for every table parameter,
   find it in `conversion.params` by EPSG code when the row has one, else by name, and assert the
   value matches after unit conversion to degrees/metres (`math.isclose`, rel 1e-12). Any missing
   or mismatched parameter raises `ValueError`. This is cheap and turns the PROJJSON/proj-string
   hazard into an error.

### 6.4 Geographic CRS builder

Follows `GTIFGetDefn` (geo_normalize.c L2394-L2660) and the GeogCS block of `GTIFGetOGISDefn`
(gt_wkt_srs.cpp L917-L1100):

- **EPSG-coded GCS** (`GeographicTypeGeoKey` not 32767): `CRS.from_epsg`. Unchanged.
- **Angular unit**: `GeogAngularUnitsGeoKey` code (9101 radian, 9102 degree, 9105 grad, others via
  `pyproj` unit lookup) or 32767 with `GeogAngularUnitSizeGeoKey` in radians. Factor in degrees
  `UOMAngleInDegrees`. The ellipsoidal CS is built with that unit; for degrees use
  `Ellipsoidal2DCS()`, otherwise `CoordinateSystem.from_json_dict` with the unit's name and
  conversion factor (the one place a dict is acceptable: it carries no parameters to drop).
- **Linear unit and axes** (projected only): `ProjLinearUnitsGeoKey` code or 32767 with
  `ProjLinearUnitSizeGeoKey`. Factor in metres `UOMLengthInMeters`. Use the `Cartesian2DCS`
  presets where one exists (`EASTING_NORTHING`, `EASTING_NORTHING_FT` for 9002,
  `EASTING_NORTHING_US_FT` for 9003, `WESTING_SOUTHING` for a table row with
  `axes: ["west", "south"]`), and `CoordinateSystem.from_json_dict` only for other units (name and
  factor from proj.db via pyproj for a code, the raw size for 32767). Do not hardcode unit factors.
- **Ellipsoid**: if `GeogEllipsoidGeoKey` is a code and no axis keys: `Ellipsoid.from_epsg`.
  Otherwise `CustomEllipsoid(name, semi_major_axis, inverse_flattening | semi_minor_axis)`;
  `radius` when semi-minor equals semi-major and no inverse flattening (sphere). Name from
  `Ellipsoid = ...` in the citation, else proj.db name for a code, else `unknown` (names don't
  affect equality but keep GDAL's for readability). Axis keys override code-derived values (L2590-L2600).
- **Datum**: `GeogGeodeticDatumGeoKey` code → `Datum.from_epsg`; else `CustomDatum(name,
  ellipsoid, prime_meridian)` with the name rule from 6.1.
- **Prime meridian**: `GeogPrimeMeridianGeoKey` code → `PrimeMeridian.from_epsg`; else
  `CustomPrimeMeridian(longitude=GeogPrimeMeridianLongGeoKey × UOMAngleInDegrees)` (libgeotiff
  `GTIFAngleToDD`, L2616-L2620) with the name rule from 6.1.
- **TOWGS84**: not readable with async-tiff 0.7 (Q2). When it becomes readable, wrap the result in
  a `BoundCRS` via `pyproj.crs.CRS.from_json_dict` of the built CRS plus a `ToWGS84Transformation`
  (pyproj has a typed class for it).
- Citation parsing: keep `_parse_geog_citation`; also read `AUnits = ...` so a citation-only grads
  file (GDAL writes both the code and the citation entry) is consistent.

### 6.5 Assembly

```python
geog = GeographicCRS(name=gcs_name, datum=datum, ellipsoidal_cs=ellipsoidal_cs)
if projected:
    crs = ProjectedCRS(name=proj_name, conversion=conversion, geodetic_crs=geog, cartesian_cs=cartesian_cs)
```

`projjson_from_geo_keys` returns `crs.to_json_dict()`. The PROJJSON-schema test in
`tests/test_crs.py` keeps passing because pyproj emits valid PROJJSON.

## 7. Tests in async-geotiff

### 7.1 Conformance test (`tests/test_crs_conformance.py`)

- Load `fixtures/geotiff-test-data/crs/manifest.json` once (session fixture).
- Parametrize over case names. Rows with `gdal.projjson == null` or `gdal.proj4 == null` are
  `pytest.skip`ped with the row's note.
- For each case: `GeoTIFF.open` the fixture, `expected.equals(geotiff.crs)` (6.1), then the point
  check, built exactly as the generator builds it (4.4): a degree, Greenwich-PM longlat CRS on
  `geotiff.crs.ellipsoid`'s axes (`+proj=longlat +a=... +rf=...` or `+b=...`), then
  `Transformer.from_crs(that, geotiff.crs, always_xy=True)` on `(lon, lat)`, compared to `(x, y)`
  with `pytest.approx(abs=1e-3)`. Using `geotiff.crs.geodetic_crs` instead would move the point
  for grads and non-Greenwich rows. For geographic rows the manifest's `(x, y)` is `(lon, lat)`
  and the test transforms the same way (identity for degree/Greenwich bases, a real conversion
  otherwise). Both assertions in the same test so a known-failure row covers both.
- **Known failures**: `KNOWN_FAILURES: dict[str, str]` mapping case name to reason, applied as
  `pytest.param(name, marks=pytest.mark.xfail(strict=True, reason=...))`. `strict=True` makes an
  unexpected pass fail the run, so the list can only shrink. Stage 3 seeds the list with every
  row that fails against the current `_crs.py`; stage 4 removes rows as they pass. Rows that
  cannot pass without upstream changes (Q2, Q3) stay with a reason that names the blocker.
- Keep `test_crs` over `ALL_TEST_IMAGES` untouched and green throughout.

### 7.2 Unit tests for the interpreter (`tests/test_crs_conversion.py`)

Small, synthetic, no fixtures: parameter fallback order (first present wins, `0.0` counts as
present), unit scaling by kind, each `when` rule, `unsupported` raises, post-build validation
raises on a deliberately broken proj-string mapping. These are the red tests to write first in
stage 4.

### 7.3 Table/vendoring test (`tests/test_crs_table.py`)

The vendored JSON equals the submodule's; every CT code in the table either is `unsupported` or
has a typed-class mapping or a `proj` name.

## 8. Staging and PRs

One PR per stage; stop for review after each. PR text carries the `> [!NOTE]` Claude attribution
at the top and the "Written by Claude Code" footer; `Closes #N` where applicable; never merge.

1. **geotiff-test-data, corpus**: `crs/` layout, `cases.py`, `generate_crs.py`, fixtures,
   `manifest.json`, `epsg/*.json`, pixi task, `check.sh`/`info.sh` changes, `tests/test_crs_corpus.py`
   (minus the table checks). Work in a worktree under its existing `.worktrees/`.
2. **geotiff-test-data, CT table**: `geotiff-ct-methods.json`, `README.md` schema docs, the table
   checks in `tests/test_crs_corpus.py`. Combined with 1 if review prefers.
3. **async-geotiff, conformance test**: submodule bump, vendored table + test, conformance test with
   the seeded known-failures list. No builder changes. Suite green.
4. **async-geotiff, builder**: `_crs_conversion.py`, `_crs_geographic.py`, interpreter unit tests
   first (red), then the rewrite; known-failures shrinks to the Q2 rows (`tmerc_towgs84`,
   `omerc_variant_a`, `omerc_variant_b`, `somerc`) and the Q3 row. Changelog entry.
5. **async-tiff** (done 2026-10-26): issue developmentseed/async-tiff#367 and PR
   developmentseed/async-tiff#368 expose keys 2062 and 3096. Once released, async-geotiff bumps
   its `async-tiff>=` floor, reads them in stage 4, and the four rows leave the known-failures
   list.

Before stage 4, write an implementation plan via the writing-plans skill into `dev-docs/plans/`.

## 9. Open questions for Kyle (answered 2026-10-26)

- Q1: approved, proceed with the PROJ-derived rule.
- Q2: make an issue and a minimal PR in async-tiff (stage 5 above).
- Q3: approved, follow libgeotiff's single conversion; the row stays a known failure.
- Q4: keep all 46 (my call; they are cheap and document the coded-key form for the TS port).

- **Q1. Polar Stereographic rule.** The brief's rule (`ProjScaleAtNatOrigin` present or
  `ProjStdParallel1` absent → variant A) does not match what GDAL writes and reads (section 3).
  I replaced it with PROJ's own value-based rule in 5.2 (read from `io.cpp`) and added two WKT
  fixtures to pin it. Flagging because it contradicts a "do not relitigate" decision; OK to
  proceed?
- **Q2. Keys async-tiff cannot read.** async-tiff has no accessor for `GeogTOWGS84GeoKey` (2062)
  or `ProjRectifiedGridAngleGeoKey` (3096) and no raw-tag fallback, so four corpus rows (TOWGS84
  and the three Hotine Oblique Mercator files) cannot pass from async-geotiff alone, and the
  "grid-angle" failure class in the brief cannot be fixed here. Options: (a) an async-tiff PR
  adding both keys (your call, it is another repo), then stage 5; (b) leave the four rows listed
  as known failures with the reason naming async-tiff. The spec assumes (b) until you say (a).
- **Q3. Prime meridian in grads.** GDAL's write/read of `+pm=paris` is internally inconsistent
  (three 0.9 factors on read, one on write). Proposal: follow libgeotiff's single conversion and
  keep `lcc_1sp_paris_grad` as a permanent known failure with that reason, rather than replicate
  GDAL's chain. Also worth a GDAL issue, but not without your OK.
- **Q4. EPSG case count.** 46 coded cases from the prior session's list. They are cheap (a few KB
  each plus the cached JSON) but mostly test pyproj's `from_epsg`. Keep all, or trim to a dozen
  spanning the methods?

## 10. Calls I made (check these while reading)

- Corpus lives in a top-level `crs/` directory with a single table-driven generator, plain GTiff
  fixtures, `check.sh` coverage, and `info.sh` exclusion (4.1).
- Raw GeoKeys in the manifest are decoded with tifffile by key id, not via async-tiff (4.4).
- `pyproj.CRS.equals` is the Python assertion; the manifest's `core` is the TS assertion (6.1).
- Datum naming reproduces GDAL's citation naming with `unknown` as the fallback (6.1).
- Untyped methods use a proj-string CRS's `coordinate_operation`, not
  `CoordinateOperation.from_string`, plus post-build parameter validation for all paths (6.3).
- The table JSON is vendored into the package with a drift test (6.2).
- Known failures use `xfail(strict=True)` (7.1).
- A table key with no async-tiff accessor raises instead of defaulting (6.3).
- Axis direction is a per-variant table field (`axes`), present only because CT 27 needs it
  (5.1, 5.4); the point check in the test mirrors the generator's degree/Greenwich base (7.1).
- Rows GDAL cannot read back (`gdal.projjson == null`) are skipped, not failed (4.4, 7.1).
- One tifffile-written fixture for an EPSG-coded prime meridian, since GDAL never writes one (4.3).
