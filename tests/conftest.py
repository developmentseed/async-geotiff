from functools import lru_cache
from pathlib import Path

from async_tiff.store import LocalStore

from async_geotiff import GeoTIFF


@lru_cache
def find_root_dir():
    root_dir = Path(__file__).parent.resolve()

    if root_dir.name != "async-geotiff":
        root_dir = root_dir.parent

    return root_dir


@lru_cache
def fixture_store():
    return LocalStore(find_root_dir() / "fixtures")


async def load_rasterio_geotiff(name: str) -> GeoTIFF:
    store = fixture_store()
    path = f"geotiff-test-data/rasterio_generated/fixtures/{name}.tif"
    return await GeoTIFF.open(path=path, store=store)
