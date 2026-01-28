from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import numpy as np
from affine import Affine

from async_geotiff import Array

if TYPE_CHECKING:
    from async_tiff import TIFF
    from async_tiff import Array as AsyncTiffArray
    from pyproj import CRS


async def fetch_tile(  # noqa: PLR0913
    *,
    x: int,
    y: int,
    tiff: TIFF,
    crs: CRS,
    ifd_index: int,
    mask_ifd_index: int | None,
    transform: Affine,
    tile_width: int,
    tile_height: int,
) -> Array:
    tile_fut = tiff.fetch_tile(x, y, ifd_index)

    mask_data: AsyncTiffArray | None = None
    if mask_ifd_index := mask_ifd_index:
        mask_fut = tiff.fetch_tile(x, y, mask_ifd_index)
        tile, mask = await asyncio.gather(tile_fut, mask_fut)
        tile_data, mask_data = await asyncio.gather(tile.decode(), mask.decode())
    else:
        tile = await tile_fut
        tile_data = await tile.decode()

    tile_transform = transform * Affine.translation(
        x * tile_width,
        y * tile_height,
    )

    return Array(
        data=np.asarray(tile_data),
        mask=np.asarray(mask_data) if mask_data else None,
        crs=crs,
        transform=tile_transform,
        width=tile_width,
        height=tile_height,
    )


async def fetch_tiles(  # noqa: PLR0913, D417
    *,
    xs: list[int],
    ys: list[int],
    tiff: TIFF,
    crs: CRS,
    ifd_index: int,
    mask_ifd_index: int | None,
    transform: Affine,
    tile_width: int,
    tile_height: int,
) -> list[Array]:
    """Fetch multiple tiles from this overview.

    Args:
        xs: The x coordinates of the tiles.
        ys: The y coordinates of the tiles.

    """
    tiles_fut = tiff.fetch_tiles(xs, ys, ifd_index)

    decoded_masks: list[AsyncTiffArray | None] = [None] * len(xs)
    if mask_ifd_index := mask_ifd_index:
        masks_fut = tiff.fetch_tiles(xs, ys, mask_ifd_index)
        tiles, masks = await asyncio.gather(tiles_fut, masks_fut)

        decoded_tile_futs = [tile.decode() for tile in tiles]
        decoded_mask_futs = [mask.decode() for mask in masks]
        decoded_tiles = await asyncio.gather(*decoded_tile_futs)
        decoded_masks = await asyncio.gather(*decoded_mask_futs)
    else:
        tiles = await tiles_fut
        decoded_tiles = await asyncio.gather(*[tile.decode() for tile in tiles])

    arrays: list[Array] = []
    for x, y, tile_data, mask_data in zip(
        xs,
        ys,
        decoded_tiles,
        decoded_masks,
        strict=True,
    ):
        tile_transform = transform * Affine.translation(
            x * tile_width,
            y * tile_height,
        )
        array = Array(
            data=np.asarray(tile_data),
            mask=np.asarray(mask_data) if mask_data else None,
            crs=crs,
            transform=tile_transform,
            width=tile_width,
            height=tile_height,
        )
        arrays.append(array)

    return arrays
