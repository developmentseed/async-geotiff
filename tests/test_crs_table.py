"""The vendored GeoTIFF CT method table must match the geotiff-test-data copy."""

from __future__ import annotations

import json
from pathlib import Path

from async_geotiff._crs_table import load_table

REPO_ROOT = Path(__file__).parent.parent
VENDORED = REPO_ROOT / "src/async_geotiff/data/geotiff-ct-methods.json"
SUBMODULE = REPO_ROOT / "fixtures/geotiff-test-data/crs/geotiff-ct-methods.json"


def test_vendored_table_matches_submodule():
    assert json.loads(VENDORED.read_text()) == json.loads(SUBMODULE.read_text())


def test_table_methods_have_proj_names():
    table = json.loads(VENDORED.read_text())
    for method in table["methods"].values():
        if "unsupported" in method:
            continue
        for variant in method["variants"]:
            if "method" in variant:
                assert variant["method"]["proj"]


def test_load_table_has_every_ct_code():
    assert set(load_table()) == set(range(1, 29)) | {9815}


def test_unsupported_method():
    method = load_table()[2]
    assert method.unsupported
    assert method.variants == ()


def test_mercator_variants():
    variants = load_table()[7].variants
    assert len(variants) == 2
    assert variants[0].when == {"present": "ProjStdParallel1"}
    assert variants[0].method_epsg == 9805
    assert variants[1].when is None
    assert variants[1].method_epsg == 9804


def test_polar_unrepresentable():
    variants = load_table()[15].variants
    assert variants[2].unrepresentable
    assert variants[2].method_name is None


def test_all_parameters_union():
    names = {p.name for p in load_table()[15].all_parameters}
    assert {"Scale factor at natural origin", "Latitude of standard parallel"} <= names


def test_axes():
    assert load_table()[27].variants[0].axes == ("west", "south")
    assert load_table()[1].variants[0].axes == ("east", "north")


def test_parameter_fields():
    lat = load_table()[1].variants[0].parameters[0]
    assert lat.name == "Latitude of natural origin"
    assert lat.epsg == 8801
    assert lat.proj == "lat_0"
    assert lat.kind == "angular"
    assert lat.keys == ("ProjNatOriginLat", "ProjFalseOriginLat", "ProjCenterLat")
    assert lat.default == 0.0
