from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from affine import Affine

from async_geotiff import Array
from async_geotiff._transform import HasTransform

if TYPE_CHECKING:
    from async_tiff import TIFF, ImageFileDirectory
    from async_tiff import Array as AsyncTiffArray
    from pyproj import CRS


class HasTiffReference(HasTransform, Protocol):
    """Protocol for objects that hold a TIFF reference and can request tiles."""

    @property
    def _ifd(self) -> ImageFileDirectory:
        """The data IFD for this image (index, IFD)."""
        ...

    @property
    def _mask_ifd(self) -> ImageFileDirectory | None:
        """The mask IFD for this image (index, IFD), if any."""
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
        tile_fut = self._ifd.fetch_tile(x, y)

        mask_data: AsyncTiffArray | None = None
        if self._mask_ifd is not None:
            mask_fut = self._mask_ifd.fetch_tile(x, y)
            tile, mask = await asyncio.gather(tile_fut, mask_fut)
            tile_data, mask_data = await asyncio.gather(tile.decode(), mask.decode())
        else:
            tile = await tile_fut
            tile_data = await tile.decode()

        tile_transform = self.transform * Affine.translation(
            x * self.tile_width,
            y * self.tile_height,
        )

        return Array._create(  # noqa: SLF001
            data=tile_data,
            mask=mask_data,
            planar_configuration=self._ifd.planar_configuration,
            crs=self.crs,
            transform=tile_transform,
            photometric_interpretation=self._ifd.photometric_interpretation,
            colormap=self.colormap,
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
        tiles_fut = self._ifd.fetch_tiles(xs, ys)

        decoded_masks: list[AsyncTiffArray | None] = [None] * len(xs)
        if self._mask_ifd is not None:
            masks_fut = self._mask_ifd.fetch_tiles(xs, ys)
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
            array = Array._create(  # noqa: SLF001
                data=tile_data,
                mask=mask_data,
                planar_configuration=self._ifd.planar_configuration,
                crs=self.crs,
                transform=tile_transform,
            )
            arrays.append(array)

        return arrays
