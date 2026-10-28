"""Tests for raster array metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from async_geotiff import Window

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (
            "uint8_rgb_deflate_block64_cog",
            "async_geotiff.RasterArray(shape=(3, 3, 4), dtype='uint8', has_mask=False)",
        ),
        (
            "cog_uint8_rgb_mask",
            "async_geotiff.RasterArray(shape=(3, 3, 4), dtype='uint8', has_mask=True)",
        ),
        (
            "float32_1band_lerc_block32",
            (
                "async_geotiff.RasterArray(shape=(1, 3, 4), dtype='float32', "
                "has_mask=False)"
            ),
        ),
    ],
)
async def test_repr_summarizes_array_metadata(
    load_geotiff: LoadGeoTIFF,
    name: str,
    expected: str,
) -> None:
    image = await load_geotiff(name)
    array = await image.read(
        window=Window(col_off=0, row_off=0, width=4, height=3),
    )

    # Array contents and private parent objects must not enter the summary,
    # even when NumPy is configured to print every value.
    with np.printoptions(threshold=np.inf):
        assert repr(array) == expected
