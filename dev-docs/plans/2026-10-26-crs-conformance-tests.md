# CRS Conformance Tests Implementation Plan (stage 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make async-geotiff's test suite run the geotiff-test-data CRS corpus against the current `_crs.py`, green from day one through a known-failures list that can only shrink.

**Architecture:** The submodule moves to the commit that merged the corpus. The CT table is vendored into the package (`src/async_geotiff/data/`) with a test that it equals the submodule copy. A parametrized test opens every manifest row's fixture, compares the built CRS to GDAL's PROJJSON with `pyproj.CRS.equals`, then checks the test point; rows in `KNOWN_FAILURES` are `xfail(strict=True)`, flagged rows are skipped.

**Tech Stack:** pytest, pytest-asyncio, pyproj 3.7, async-geotiff test fixtures (`fixture_store`), uv.

**Spec:** `dev-docs/specs/2026-10-26-geokey-crs-conformance-design.md`, sections 6.2 (vendoring) and 7 (tests).

## Global Constraints

- Branch `kyle/crs-conformance-tests` in the `.claude/worktrees/crs-conformance-spec` worktree; never commit on `main`.
- No changes to `src/async_geotiff/_crs.py` in this stage; the known-failures list records what fails today.
- `tests/test_crs.py` over `ALL_TEST_IMAGES` stays green.
- Ruff `select = ["ALL"]` with the repo's ignores; tests directory has its own per-file ignores.
- PR text with the Claude attribution note and footer; never merge.

## Review Focus

1. A listed known failure that starts passing must fail the run (`xfail(strict=True)`), pinned by `test_known_failures_are_listed_cases`.
2. A flagged row (`gdal.projjson` or `gdal.proj4` null) must be skipped, not failed, pinned by the skip marks in `_params()`.
3. The vendored table must not drift from the submodule, pinned by `test_vendored_table_matches_submodule`.
4. The point check must use the manifest's degree/Greenwich base, not `geodetic_crs`, or grads and Paris rows fail for the wrong reason (`_ellipsoid_longlat`).
5. The vendored JSON must ship in the wheel; verified once by listing the built wheel.

---

### Task 1: Submodule bump

**Files:** Modify: `fixtures/geotiff-test-data` (gitlink)

- [ ] Point the submodule at geotiff-test-data `main` after #84 merged (`35da663`); `git -C fixtures/geotiff-test-data checkout origin/main`.
- [ ] Run: `uv run pytest -q` → Expected: existing suite still passes.
- [ ] Commit: `chore: Bump geotiff-test-data for the CRS conformance corpus`.

### Task 2: Vendor the CT table

**Files:** Create: `src/async_geotiff/data/geotiff-ct-methods.json` (verbatim copy), `src/async_geotiff/data/__init__.py` (docstring only); Test: `tests/test_crs_table.py`.

- [ ] Write `tests/test_crs_table.py`: `test_vendored_table_matches_submodule` (json-equal to `fixtures/geotiff-test-data/crs/geotiff-ct-methods.json`) and `test_table_methods_have_proj_names` (every non-`unsupported` variant with a `method` has a non-empty `proj`).
- [ ] Run: `uv run pytest tests/test_crs_table.py -q` → Expected: FAIL, vendored file missing.
- [ ] Copy the JSON; add `data/__init__.py`.
- [ ] Run again → Expected: 2 passed. Then `uv build --wheel` and `unzip -l dist/*.whl | grep geotiff-ct-methods` → Expected: one line.
- [ ] Commit: `test: Vendor the GeoTIFF CT method table with a drift test`.

### Task 3: Conformance test with seeded known failures

**Files:** Create: `tests/test_crs_conformance.py`.

**Interfaces:**
- `MANIFEST` loaded at import from `tests/../fixtures/geotiff-test-data/crs/manifest.json`.
- `KNOWN_FAILURES: dict[str, str]` name → reason.
- `_params() -> list[pytest.param]`: one per row, id = name; `pytest.mark.skip(reason=note)` when `gdal.projjson` or `gdal.proj4` is null; `pytest.mark.xfail(strict=True, reason=...)` when listed.
- `test_crs_matches_gdal(fixture_store, row)`: open `geotiff-test-data/crs/<file>`, `expected = CRS.from_json_dict(row["gdal"]["projjson"])`, `assert expected.equals(geotiff.crs)`, then project `(lon, lat)` from a `+proj=longlat` CRS on `geotiff.crs`'s ellipsoid (`+a +rf`, or `+R` for a sphere) with `always_xy=True` and compare to `(x, y)` with `pytest.approx(abs=2e-3)` (the manifest rounds to millimetres).
- `test_known_failures_are_listed_cases()`: every key of `KNOWN_FAILURES` is a manifest name that is not flagged.

- [ ] Write the test with `KNOWN_FAILURES = {}`.
- [ ] Run: `uv run pytest tests/test_crs_conformance.py -q` → Expected: a mix of passes and failures, 2 skipped (`eqearth`, `stere_polar_scaled_wkt`).
- [ ] Seed `KNOWN_FAILURES` from the failing ids, one reason each, grouped by the failure class from spec section 1 (rejected CT code, wrong variant, units, origin keys, datum, async-tiff keys, GDAL PM-in-grads).
- [ ] Run: `uv run pytest -q` → Expected: whole suite green, with `N xfailed, 2 skipped`.
- [ ] Commit: `test: Add the GeoKey-to-CRS conformance test with a known-failures list`.
- [ ] Push `kyle/crs-conformance-tests`, open the PR (title `test: Add the CRS conformance suite from geotiff-test-data`), report ready.
