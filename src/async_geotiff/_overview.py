from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

import numpy as np
from affine import Affine

from async_geotiff import Array

if TYPE_CHECKING:
    from async_tiff import Array as AsyncTiffArray
    from async_tiff import GeoKeyDirectory, ImageFileDirectory

    from async_geotiff import GeoTIFF

# ruff: noqa: SLF001


@dataclass(init=False, frozen=True, kw_only=True, eq=False, repr=False)
class Overview:
    """An overview level of a Cloud-Optimized GeoTIFF image."""

    _geotiff: GeoTIFF
    """A reference to the parent GeoTIFF object.
    """

    _gkd: GeoKeyDirectory
    """The GeoKeyDirectory of the primary IFD.
    """

    _ifd: tuple[int, ImageFileDirectory]
    """The IFD for this overview level.

    (positional index of the IFD in the TIFF file, IFD object)
    """

    _mask_ifd: tuple[int, ImageFileDirectory] | None
    """The IFD for the mask associated with this overview level, if any.

    (positional index of the IFD in the TIFF file, IFD object)
    """

    @classmethod
    def _create(
        cls,
        *,
        geotiff: GeoTIFF,
        gkd: GeoKeyDirectory,
        ifd: tuple[int, ImageFileDirectory],
        mask_ifd: tuple[int, ImageFileDirectory] | None,
    ) -> Overview:
        instance = cls.__new__(cls)

        # We use object.__setattr__ because the dataclass is frozen
        object.__setattr__(instance, "_geotiff", geotiff)
        object.__setattr__(instance, "_gkd", gkd)
        object.__setattr__(instance, "_ifd", ifd)
        object.__setattr__(instance, "_mask_ifd", mask_ifd)

        return instance

    async def fetch_tile(
        self,
        x: int,
        y: int,
    ) -> Array:
        """Fetch a tile from this overview.

        Args:
            x: The x coordinate of the tile.
            y: The y coordinate of the tile.

        """
        tile_fut = self._geotiff._tiff.fetch_tile(x, y, self._ifd[0])

        mask_data: AsyncTiffArray | None = None
        if mask_ifd := self._mask_ifd:
            mask_fut = self._geotiff._tiff.fetch_tile(x, y, mask_ifd[0])
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
            crs=self._geotiff.crs,
            transform=tile_transform,
            width=self.width,
            height=self.height,
        )

    # TODO: relax type hints to Sequence[int]
    # upstream issue:
    # https://github.com/developmentseed/async-tiff/issues/198
    async def fetch_tiles(self, xs: list[int], ys: list[int]) -> list[Array]:
        """Fetch multiple tiles from this overview.

        Args:
            xs: The x coordinates of the tiles.
            ys: The y coordinates of the tiles.

        """
        tiles_fut = self._geotiff._tiff.fetch_tiles(xs, ys, self._ifd[0])

        decoded_masks: list[AsyncTiffArray | None] = [None] * len(xs)
        if mask_ifd := self._mask_ifd:
            masks_fut = self._geotiff._tiff.fetch_tiles(xs, ys, mask_ifd[0])
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
                crs=self._geotiff.crs,
                transform=tile_transform,
                width=self.width,
                height=self.height,
            )
            arrays.append(array)

        return arrays

    @property
    def height(self) -> int:
        """The height of the overview in pixels."""
        return self._ifd[1].image_height

    @property
    def tile_height(self) -> int:
        """The tile height of the overview in pixels."""
        return self._ifd[1].tile_height or self.height

    @property
    def tile_width(self) -> int:
        """The tile width of the overview in pixels."""
        return self._ifd[1].tile_width or self.width

    @cached_property
    def transform(self) -> Affine:
        """The affine transform mapping pixel coordinates to geographic coordinates.

        Returns:
            Affine: The affine transform.

        """
        full_transform = self._geotiff.transform

        overview_width = self._ifd[1].image_width
        full_width = self._geotiff.width
        overview_height = self._ifd[1].image_height
        full_height = self._geotiff.height

        scale_x = full_width / overview_width
        scale_y = full_height / overview_height

        return full_transform * Affine.scale(scale_x, scale_y)

    @property
    def width(self) -> int:
        """The width of the overview in pixels."""
        return self._ifd[1].image_width
