from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import AnyUrl

from async_geotiff.tms import generate_tms

if TYPE_CHECKING:
    from .conftest import LoadGeoTIFF


@pytest.mark.asyncio
async def test_tms(load_geotiff: LoadGeoTIFF) -> None:
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_geotiff(name)
    tms = generate_tms(geotiff)
    tms_dict = tms.model_dump(exclude_none=True)

    assert tms_dict["crs"] == {
        "uri": AnyUrl("http://www.opengis.net/def/crs/EPSG/0/4326"),
    }
    assert tms_dict["boundingBox"] == {
        "lowerLeft": (0.0, -1.28),
        "upperRight": (1.28, 0.0),
        "crs": {"uri": AnyUrl("http://www.opengis.net/def/crs/EPSG/0/4326")},
    }
    assert tms_dict["tileMatrices"] == [
        {
            "id": "0",
            "scaleDenominator": 3975696.099759771,
            "cellSize": 0.01,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": (0.0, 0.0),
            "tileWidth": 64,
            "tileHeight": 64,
            "matrixWidth": 2,
            "matrixHeight": 2,
        },
        {
            "id": "1",
            "scaleDenominator": 7951392.199519542,
            "cellSize": 0.02,
            "cornerOfOrigin": "topLeft",
            "pointOfOrigin": (0.0, 0.0),
            "tileWidth": 64,
            "tileHeight": 64,
            "matrixWidth": 1,
            "matrixHeight": 1,
        },
    ]
