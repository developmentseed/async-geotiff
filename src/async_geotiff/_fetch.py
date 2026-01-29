from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

import numpy as np
from affine import Affine

from async_geotiff import Array
from async_geotiff._transform import HasTransform

if TYPE_CHECKING:
    from async_tiff import TIFF
    from async_tiff import Array as AsyncTiffArray
    from pyproj import CRS


class HasTiffReference(HasTransform, Protocol):
    """Protocol for objects that hold a TIFF reference and can request tiles."""

    @property
    def _ifd_index(self) -> int:
        """The index of the data IFD in the TIFF file."""
        ...

    @property
    def _mask_ifd_index(self) -> int | None:
        """The index of the mask IFD in the TIFF file, if any."""
        ...

    @property
    def _tiff(self) -> TIFF:
        """A reference to the underlying TIFF object."""
        ...

    @property
    def crs(self) -> CRS:
        """The coordinate reference system."""
        ...

    @property
    def tile_height(self) -> int:
        """The height of tiles in pixels."""
        ...

    @property
    def tile_width(self) -> int:
        """The width of tiles in pixels."""
        ...


class FetchTileMixin:
    """Mixin for fetching tiles from a GeoTIFF.

    Classes using this mixin must implement HasTiffReference.
    """

    async def fetch_tile(
        self: HasTiffReference,
        x: int,
        y: int,
    ) -> Array:
        tile_fut = self._tiff.fetch_tile(x, y, self._ifd_index)

        mask_data: AsyncTiffArray | None = None
        if mask_ifd_index := self._mask_ifd_index:
            mask_fut = self._tiff.fetch_tile(x, y, mask_ifd_index)
            tile, mask = await asyncio.gather(tile_fut, mask_fut)
            tile_data, mask_data = await asyncio.gather(tile.decode(), mask.decode())
        else:
            tile = await tile_fut
            tile_data = await tile.decode()

        tile_transform = self.transform * Affine.translation(
            x * self.tile_width,
            y * self.tile_height,
        )

        return Array(
            data=np.asarray(tile_data),
            mask=np.asarray(mask_data) if mask_data else None,
            crs=self.crs,
            transform=tile_transform,
            width=self.tile_width,
            height=self.tile_height,
        )

    async def fetch_tiles(
        self: HasTiffReference,
        xs: list[int],
        ys: list[int],
    ) -> list[Array]:
        """Fetch multiple tiles from this overview.

        Args:
            xs: The x coordinates of the tiles.
            ys: The y coordinates of the tiles.

        """
        tiles_fut = self._tiff.fetch_tiles(xs, ys, self._ifd_index)

        decoded_masks: list[AsyncTiffArray | None] = [None] * len(xs)
        if mask_ifd_index := self._mask_ifd_index:
            masks_fut = self._tiff.fetch_tiles(xs, ys, mask_ifd_index)
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
            tile_transform = self.transform * Affine.translation(
                x * self.tile_width,
                y * self.tile_height,
            )
            array = Array(
                data=np.asarray(tile_data),
                mask=np.asarray(mask_data) if mask_data else None,
                crs=self.crs,
                transform=tile_transform,
                width=self.tile_width,
                height=self.tile_height,
            )
            arrays.append(array)

        return arrays
