from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

import numpy as np
from affine import Affine

from async_geotiff._array import Array
from async_geotiff._tile import Tile
from async_geotiff._transform import HasTransform

if TYPE_CHECKING:
    from collections.abc import Sequence

    from async_tiff import Array as AsyncTiffArray
    from async_tiff import ImageFileDirectory
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

    @property
    def nodata(self) -> int | float | None:
        """The nodata value for the image, if any."""
        ...

    @property
    def width(self) -> int:
        """The width of the image in pixels."""
        ...

    @property
    def height(self) -> int:
        """The height of the image in pixels."""
        ...


class FetchTileMixin:
    """Mixin for fetching tiles from a GeoTIFF.

    Classes using this mixin must implement HasTiffReference.
    """

    async def fetch_tile(
        self: HasTiffReference,
        x: int,
        y: int,
        *,
        boundless: bool = True,
    ) -> Tile:
        """Fetch a single tile from the GeoTIFF.

        Args:
            x: The x-coordinate of the tile.
            y: The y-coordinate of the tile.

        Keyword Args:
            boundless: If False, clip edge tiles to the image bounds. Defaults to True.

        Returns:
            A Tile object containing the fetched tile data.

        """
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

        array = Array._create(  # noqa: SLF001
            data=tile_data,
            mask=mask_data,
            planar_configuration=self._ifd.planar_configuration,
            crs=self.crs,
            transform=tile_transform,
            nodata=self.nodata,
        )

        if not boundless:
            array = _clip_to_image_bounds(self, x, y, array)

        return Tile(
            x=x,
            y=y,
            array=array,
        )

    async def fetch_tiles(
        self: HasTiffReference,
        xy: Sequence[tuple[int, int]],
        *,
        boundless: bool = True,
    ) -> list[Tile]:
        """Fetch multiple tiles from this overview.

        Args:
            xy: The (x, y) coordinates of the tiles.

        Keyword Args:
            boundless: If False, clip edge tiles to the image bounds.

        """
        tiles_fut = self._ifd.fetch_tiles(xy)

        decoded_masks: list[AsyncTiffArray | None] = [None] * len(xy)
        if self._mask_ifd is not None:
            masks_fut = self._mask_ifd.fetch_tiles(xy)
            tiles, masks = await asyncio.gather(tiles_fut, masks_fut)

            decoded_tile_futs = [tile.decode() for tile in tiles]
            decoded_mask_futs = [mask.decode() for mask in masks]
            decoded_tiles = await asyncio.gather(*decoded_tile_futs)
            decoded_masks = await asyncio.gather(*decoded_mask_futs)
        else:
            tiles = await tiles_fut
            decoded_tiles = await asyncio.gather(*[tile.decode() for tile in tiles])

        final_tiles: list[Tile] = []
        for (x, y), tile_data, mask_data in zip(
            xy,
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
                nodata=self.nodata,
            )

            if not boundless:
                array = _clip_to_image_bounds(self, x, y, array)

            tile = Tile(
                x=x,
                y=y,
                array=array,
            )
            final_tiles.append(tile)

        return final_tiles


def _clip_to_image_bounds(
    self: HasTiffReference,
    x: int,
    y: int,
    array: Array,
) -> Array:
    """Clip a decoded tile array to the valid image bounds.

    Edge tiles in a COG are always encoded at the full tile size, with the
    out-of-bounds region zero-padded. When ``boundless=False`` is requested,
    this function copies only the valid pixel sub-rectangle into a new array,
    returning an Array whose width/height match the actual image content.

    Interior tiles (where the tile fits entirely within the image) are
    returned unchanged.
    """
    clipped_width = min((x + 1) * self.tile_width, self.width) - x * self.tile_width
    clipped_height = min((y + 1) * self.tile_height, self.height) - y * self.tile_height

    if clipped_width == self.tile_width and clipped_height == self.tile_height:
        return array

    # data shape is (bands, height, width)
    clipped_data = np.ascontiguousarray(array.data[:, :clipped_height, :clipped_width])
    clipped_mask = (
        np.ascontiguousarray(array.mask[:clipped_height, :clipped_width])
        if array.mask is not None
        else None
    )

    return Array(
        data=clipped_data,
        mask=clipped_mask,
        width=clipped_width,
        height=clipped_height,
        count=array.count,
        transform=array.transform,
        crs=array.crs,
        nodata=array.nodata,
    )
