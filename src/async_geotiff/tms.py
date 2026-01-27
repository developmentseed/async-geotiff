"""Generate a Tile Matrix Set from a GeoTIFF file, using morecantile."""

from __future__ import annotations

import math
from uuid import uuid4

import morecantile.models
import pyproj
from morecantile.commons import BoundingBox
from morecantile.models import CRSWKT, CRSUri, TileMatrix, TileMatrixSet, TMSBoundingBox
from morecantile.utils import meters_per_unit

from async_geotiff import GeoTIFF

_SCREEN_PIXEL_SIZE = 0.28e-3

__all__ = ["generate_tms"]


def generate_tms(geotiff: GeoTIFF, *, id: str = str(uuid4())) -> TileMatrixSet:
    """Generate a Tile Matrix Set from a GeoTIFF file.

    Args:
        geotiff: The GeoTIFF file to generate the TMS from.

    Keyword Args:
        id: The ID to assign to the Tile Matrix Set.
    """
    bounds = geotiff.bounds
    crs = geotiff.crs
    tr = geotiff.transform
    blockxsize = geotiff._primary_ifd.tile_width
    blockysize = geotiff._primary_ifd.tile_height

    if blockxsize is None or blockysize is None:
        raise ValueError("GeoTIFF must be tiled to generate a TMS.")

    mpu = meters_per_unit(crs)

    if tr.e > 0:
        corner_of_origin = "bottomLeft"
    else:
        corner_of_origin = "topLeft"

    tile_matrices: list[TileMatrix] = [
        TileMatrix(
            **{
                "id": "0",
                "scaleDenominator": tr.a * mpu / _SCREEN_PIXEL_SIZE,
                "cellSize": tr.a,
                "cornerOfOrigin": corner_of_origin,
                "pointOfOrigin": [tr.c, tr.f],
                "tileWidth": blockxsize,
                "tileHeight": blockysize,
                "matrixWidth": math.ceil(geotiff.width / blockxsize),
                "matrixHeight": math.ceil(geotiff.height / blockysize),
            }
        )
    ]

    for idx, overview in enumerate(geotiff.overviews):
        overview_tr = overview.transform
        blockxsize = overview._ifd[1].tile_width
        blockysize = overview._ifd[1].tile_height

        if blockxsize is None or blockysize is None:
            raise ValueError("GeoTIFF overviews must be tiled to generate a TMS.")

        tile_matrices.append(
            TileMatrix(
                **{
                    "id": f"{idx + 1}",
                    "scaleDenominator": overview_tr.a * mpu / _SCREEN_PIXEL_SIZE,
                    "cellSize": overview_tr.a,
                    "cornerOfOrigin": corner_of_origin,
                    "pointOfOrigin": [overview_tr.c, overview_tr.f],
                    "tileWidth": blockxsize,
                    "tileHeight": blockysize,
                    "matrixWidth": math.ceil(overview.width / blockxsize),
                    "matrixHeight": math.ceil(overview.height / blockysize),
                }
            )
        )

    bbox = BoundingBox(*bounds)
    tms_crs = _parse_crs(crs)

    return TileMatrixSet(
        title="Generated TMS",
        id=id,
        crs=tms_crs,
        boundingBox=TMSBoundingBox(
            lowerLeft=[bbox.left, bbox.bottom],
            upperRight=[bbox.right, bbox.top],
            crs=tms_crs,
        ),
        tileMatrices=tile_matrices,
    )


def _parse_crs(
    crs: pyproj.CRS,
) -> morecantile.models.CRSUri | morecantile.models.CRSWKT:
    """Parse a pyproj CRS into a morecantile CRSUri or CRSWKT.

    Args:
        crs: The pyproj CRS to parse.
    """
    if authority_code := crs.to_authority(min_confidence=20):
        authority, code = authority_code
        version = "0"
        # if we have a version number in the authority, split it out
        if "_" in authority:
            authority, version = authority.split("_")

        return CRSUri(
            uri=f"http://www.opengis.net/def/crs/{authority}/{version}/{code}"
        )

    else:
        return CRSWKT(wkt=crs.to_json_dict())
