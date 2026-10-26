"""The vendored GeoTIFF CT method table must match the geotiff-test-data copy."""

from __future__ import annotations

import json
from pathlib import Path

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
