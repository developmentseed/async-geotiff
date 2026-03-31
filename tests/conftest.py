from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import pytest
import rasterio
from async_tiff.store import LocalStore

from async_geotiff import GeoTIFF

if TYPE_CHECKING:
    from collections.abc import Generator

    from rasterio.io import DatasetReader


class LoadGeoTIFF(Protocol):
    async def __call__(
        self,
        name: str,
        *,
        variant: str = "rasterio",
    ) -> GeoTIFF: ...


class LoadRasterio(Protocol):
    @contextmanager
    def __call__(
        self,
        name: str,
        *,
        variant: str = "rasterio",
        OVERVIEW_LEVEL: int | None = None,  # noqa: N803
        **kwargs: Any,  # noqa: ANN401
    ) -> Generator[DatasetReader, None, None]: ...


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    root_dir = Path(__file__).parent.resolve()

    while root_dir != Path("/") and not (root_dir / "fixtures").exists():
        root_dir = root_dir.parent

    if not (root_dir / "fixtures").exists():
        raise RuntimeError("Couldn't find the fixtures dir")
    return root_dir / "fixtures"


@pytest.fixture(scope="session")
def fixture_store(fixtures_dir) -> LocalStore:
    return LocalStore(fixtures_dir)


@pytest.fixture
def load_geotiff(fixture_store):
    async def _load(name: str, *, variant: str = "rasterio") -> GeoTIFF:
        path = "geotiff-test-data/"

        if variant == "rasterio":
            path += "rasterio_generated/fixtures/"
        else:
            path += f"real_data/{variant}/"

        path = f"{path}{name}.tif"
        return await GeoTIFF.open(path=path, store=fixture_store)

    return _load


@pytest.fixture
def load_rasterio(fixtures_dir):
    @contextmanager
    def _load(
        name: str,
        *,
        variant: str = "rasterio",
        OVERVIEW_LEVEL: int | None = None,  # noqa: N803
        **kwargs: Any,  # noqa: ANN401
    ) -> Generator[DatasetReader, None, None]:
        path = f"{fixtures_dir}/geotiff-test-data/"
        if variant == "rasterio":
            path += "rasterio_generated/fixtures/"
        else:
            path += f"real_data/{variant}/"

        path = f"{path}{name}.tif"

        if OVERVIEW_LEVEL is not None and "OVERVIEW_LEVEL" not in kwargs:
            kwargs["OVERVIEW_LEVEL"] = OVERVIEW_LEVEL

        with rasterio.open(path, **kwargs) as ds:
            yield ds

    return _load
