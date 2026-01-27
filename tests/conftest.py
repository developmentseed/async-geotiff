from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Generator

import pytest
import rasterio
from async_tiff.store import LocalStore

from async_geotiff import GeoTIFF

if TYPE_CHECKING:
    from rasterio.io import DatasetReader


@pytest.fixture(scope="session")
def root_dir() -> Path:
    root_dir = Path(__file__).parent.resolve()

    if root_dir.name != "async-geotiff":
        root_dir = root_dir.parent

    return root_dir


@pytest.fixture(scope="session")
def fixture_store(root_dir) -> LocalStore:
    return LocalStore(root_dir / "fixtures")


@pytest.fixture
def load_geotiff(fixture_store):
    async def _load(name: str) -> GeoTIFF:
        path = f"geotiff-test-data/rasterio_generated/fixtures/{name}.tif"
        return await GeoTIFF.open(path=path, store=fixture_store)

    return _load


@pytest.fixture
def load_rasterio(root_dir):
    @contextmanager
    def _load(name: str) -> Generator[DatasetReader, None, None]:
        path = f"{root_dir}/fixtures/geotiff-test-data/rasterio_generated/fixtures/{name}.tif"
        with rasterio.open(path) as ds:
            yield ds

    return _load
