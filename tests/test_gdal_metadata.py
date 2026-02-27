from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .image_list import ALL_TEST_IMAGES

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF, LoadRasterio


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("variant", "file_name"),
    ALL_TEST_IMAGES,
)
async def test_statistics(
    load_geotiff: LoadGeoTIFF,
    load_rasterio: LoadRasterio,
    variant: str,
    file_name: str,
) -> None:
    geotiff = await load_geotiff(file_name, variant=variant)
    stats = geotiff.stored_stats

    if stats is None:
        with load_rasterio(file_name, variant=variant) as rasterio_ds:
            # Assert that rasterio also does not have statistics for this dataset
            rasterio_ds.statistics(1)

        return

    # Accessing a non-existent band index should raise a KeyError
    # (ensures we've converted away from defaultdict)
    with pytest.raises(KeyError):
        stats[0]

    with load_rasterio(file_name, variant=variant) as rasterio_ds:
        band_idx = 1
        for band_idx in range(1, rasterio_ds.count + 1):
            our_stats = stats[band_idx]
            rio_stats = rasterio_ds.tags(band_idx)

            assert our_stats.min == float(rio_stats["STATISTICS_MINIMUM"])
            assert our_stats.max == float(rio_stats["STATISTICS_MAXIMUM"])
            assert our_stats.mean == float(rio_stats["STATISTICS_MEAN"])
            assert our_stats.std == float(rio_stats["STATISTICS_STDDEV"])
            assert our_stats.valid_percent == float(
                rio_stats["STATISTICS_VALID_PERCENT"],
            )
