"""Generate a Tile Matrix Set from a GeoTIFF file, using [Morecantile].

[Morecantile]: https://developmentseed.org/morecantile/
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from morecantile.commons import BoundingBox
from morecantile.models import (
    CRS,
    CRSWKT,
    CRSUri,
    TileMatrix,
    TileMatrixSet,
    TMSBoundingBox,
)
from morecantile.utils import meters_per_unit
from pydantic import AnyUrl

if TYPE_CHECKING:
    import pyproj

    from async_geotiff import GeoTIFF

_SCREEN_PIXEL_SIZE = 0.28e-3

__all__ = ["generate_tms"]


def generate_tms(
    geotiff: GeoTIFF,
    *,
    id: str = str(uuid4()),  # noqa: A002
) -> TileMatrixSet:
    """Generate a [Tile Matrix Set] from a GeoTIFF file.

    [Tile Matrix Set]: https://docs.ogc.org/is/17-083r4/17-083r4.html

    Args:
        geotiff: The GeoTIFF file to generate the TMS from.

    Keyword Args:
        id: The ID to assign to the Tile Matrix Set.

    """
    mpu = meters_per_unit(geotiff.crs)

    tile_matrices: list[TileMatrix] = []
    for idx, overview in enumerate(reversed(geotiff.overviews)):
        ovr_tr = overview.transform
        ovr_matrix_width, ovr_matrix_height = overview.tile_count

        tile_matrices.append(
            TileMatrix(
                id=str(idx),
                scaleDenominator=ovr_tr.a * mpu / _SCREEN_PIXEL_SIZE,
                cellSize=ovr_tr.a,
                cornerOfOrigin="bottomLeft" if ovr_tr.e > 0 else "topLeft",
                pointOfOrigin=(ovr_tr.c, ovr_tr.f),
                tileWidth=overview.tile_width,
                tileHeight=overview.tile_height,
                matrixWidth=ovr_matrix_width,
                matrixHeight=ovr_matrix_height,
            ),
        )

    matrix_width, matrix_height = geotiff.tile_count
    tr = geotiff.transform

    # Add the full-resolution level last
    tile_matrices.append(
        TileMatrix(
            id=str(len(geotiff.overviews)),
            scaleDenominator=tr.a * mpu / _SCREEN_PIXEL_SIZE,
            cellSize=tr.a,
            cornerOfOrigin="bottomLeft" if tr.e > 0 else "topLeft",
            pointOfOrigin=(tr.c, tr.f),
            tileWidth=geotiff.tile_width,
            tileHeight=geotiff.tile_height,
            matrixWidth=matrix_width,
            matrixHeight=matrix_height,
        ),
    )

    bbox = BoundingBox(*geotiff.bounds)
    tms_crs = _parse_crs(geotiff.crs)

    return TileMatrixSet(
        title="Generated TMS",
        id=id,
        crs=tms_crs,
        boundingBox=TMSBoundingBox(
            lowerLeft=(bbox.left, bbox.bottom),
            upperRight=(bbox.right, bbox.top),
            crs=tms_crs,
        ),
        tileMatrices=tile_matrices,
    )


def _parse_crs(
    crs: pyproj.CRS,
) -> CRS:
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

        return CRS(
            CRSUri(
                uri=AnyUrl(
                    f"http://www.opengis.net/def/crs/{authority}/{version}/{code}",
                ),
            ),
        )

    return CRS(CRSWKT(wkt=crs.to_json_dict()))
