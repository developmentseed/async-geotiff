from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from affine import Affine

from async_geotiff._array import Array
from async_geotiff._tile import Tile
from async_geotiff._transform import HasTransform
from async_geotiff.enums import ColorInterp

if TYPE_CHECKING:
    from collections.abc import Sequence

    from async_tiff import Array as AsyncTiffArray
    from async_tiff import ImageFileDirectory

    from async_geotiff import GeoTIFF


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
    def _geotiff(self) -> GeoTIFF:
        """The parent GeoTIFF object."""
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

        # TODO: when we support fetching partial bands, we need to check if the alpha
        # band is included in the bands we've fetched.
        # https://github.com/developmentseed/async-geotiff/issues/113
        alpha_band_idxs = [
            i
            for i, colorinterp in enumerate(self._geotiff.colorinterp)
            if colorinterp == ColorInterp.ALPHA
        ]
        if len(alpha_band_idxs) > 1:
            raise ValueError("Multiple alpha bands are not supported")

        array = Array._create(  # noqa: SLF001
            data=tile_data,
            mask=mask_data,
            planar_configuration=self._ifd.planar_configuration,
            transform=tile_transform,
            geotiff=self._geotiff,
            alpha_band_idx=alpha_band_idxs[0] if alpha_band_idxs else None,
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

        # TODO: when we support fetching partial bands, we need to check if the alpha
        # band is included in the bands we've fetched.
        # https://github.com/developmentseed/async-geotiff/issues/113
        alpha_band_idxs = [
            i
            for i, colorinterp in enumerate(self._geotiff.colorinterp)
            if colorinterp == ColorInterp.ALPHA
        ]
        if len(alpha_band_idxs) > 1:
            raise ValueError("Multiple alpha bands are not supported")

        alpha_band_idx = alpha_band_idxs[0] if alpha_band_idxs else None

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
                transform=tile_transform,
                geotiff=self._geotiff,
                alpha_band_idx=alpha_band_idx,
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
    clipped_data = array.data[:, :clipped_height, :clipped_width]
    clipped_mask = (
        array.mask[:clipped_height, :clipped_width] if array.mask is not None else None
    )

    return Array(
        data=clipped_data,
        mask=clipped_mask,
        width=clipped_width,
        height=clipped_height,
        count=array.count,
        transform=array.transform,
        _geotiff=array._geotiff,  # noqa: SLF001
        _alpha_band_idx=array._alpha_band_idx,  # noqa: SLF001
    )
