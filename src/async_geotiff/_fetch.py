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

    from async_geotiff._ifd import IFDReference

# Window type: tuple of ((row_start, row_stop), (col_start, col_stop))
WindowLike = tuple[tuple[int, int], tuple[int, int]]


class HasTiffReference(HasTransform, Protocol):
    """Protocol for objects that hold a TIFF reference and can request tiles."""

    @property
    def _ifd(self) -> IFDReference:
        """The data IFD for this image (index, IFD)."""
        ...

    @property
    def _mask_ifd(self) -> IFDReference | None:
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
    def height(self) -> int:
        """The height of the image in pixels."""
        ...

    @property
    def width(self) -> int:
        """The width of the image in pixels."""
        ...

    @property
    def tile_height(self) -> int:
        """The height of tiles in pixels."""
        ...

    @property
    def tile_width(self) -> int:
        """The width of tiles in pixels."""
        ...


class CanFetchTiles(HasTiffReference, Protocol):
    """Protocol for objects that can fetch tiles."""

    async def fetch_tiles(
        self,
        xs: list[int],
        ys: list[int],
    ) -> list[Array]:
        """Fetch multiple tiles."""
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
        tile_fut = self._tiff.fetch_tile(x, y, self._ifd.index)

        mask_data: AsyncTiffArray | None = None
        if self._mask_ifd is not None:
            mask_ifd_index = self._mask_ifd.index
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

        return Array._create(  # noqa: SLF001
            data=tile_data,
            mask=mask_data,
            planar_configuration=self._ifd.ifd.planar_configuration,
            crs=self.crs,
            transform=tile_transform,
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
        tiles_fut = self._tiff.fetch_tiles(xs, ys, self._ifd.index)

        decoded_masks: list[AsyncTiffArray | None] = [None] * len(xs)
        if self._mask_ifd is not None:
            mask_ifd_index = self._mask_ifd.index
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
            array = Array._create(  # noqa: SLF001
                data=tile_data,
                mask=mask_data,
                planar_configuration=self._ifd.ifd.planar_configuration,
                crs=self.crs,
                transform=tile_transform,
            )
            arrays.append(array)

        return arrays

    async def read(
        self: CanFetchTiles,
        window: WindowLike,
    ) -> Array:
        """Read pixel data for a window region.

        This method fetches all tiles that intersect the given window and
        stitches them together, returning only the pixels within the window.

        Args:
            window: A tuple of ((row_start, row_stop), (col_start, col_stop))
                defining the pixel region to read. This format is compatible
                with rasterio's window tuple format.

        Returns:
            An Array containing the pixel data for the requested window.

        Raises:
            IndexError: If the window extends outside the image bounds.

        """
        (row_start, row_stop), (col_start, col_stop) = window

        # Validate window bounds
        if row_start < 0 or col_start < 0:
            raise IndexError(
                f"Window start indices must be non-negative, "
                f"got row_start={row_start}, col_start={col_start}",
            )
        if row_stop > self.height or col_stop > self.width:
            raise IndexError(
                f"Window extends outside image bounds. "
                f"Window: rows={row_start}:{row_stop}, cols={col_start}:{col_stop}. "
                f"Image size: {self.height}x{self.width}",
            )
        if row_start >= row_stop or col_start >= col_stop:
            raise IndexError(
                f"Window must have positive dimensions, "
                f"got rows={row_start}:{row_stop}, cols={col_start}:{col_stop}",
            )

        # Calculate which tiles we need to fetch
        tile_x_start = col_start // self.tile_width
        tile_x_stop = (col_stop - 1) // self.tile_width + 1
        tile_y_start = row_start // self.tile_height
        tile_y_stop = (row_stop - 1) // self.tile_height + 1

        # Build list of tile coordinates
        xs: list[int] = []
        ys: list[int] = []
        for ty in range(tile_y_start, tile_y_stop):
            for tx in range(tile_x_start, tile_x_stop):
                xs.append(tx)
                ys.append(ty)

        # Fetch all needed tiles
        tiles = await self.fetch_tiles(xs, ys)

        # Calculate output dimensions
        window_height = row_stop - row_start
        window_width = col_stop - col_start

        # Get number of bands from first tile
        num_bands = tiles[0].count
        dtype = tiles[0].data.dtype

        # Create output array
        output_data = np.empty((num_bands, window_height, window_width), dtype=dtype)

        # Check if any tiles have masks
        has_mask = any(tile.mask is not None for tile in tiles)
        output_mask: np.ndarray | None = None
        if has_mask:
            output_mask = np.ones((window_height, window_width), dtype=np.bool_)

        # Place each tile's data into the output array
        num_tiles_x = tile_x_stop - tile_x_start
        for i, tile in enumerate(tiles):
            # Calculate tile position in the grid
            tile_grid_y = i // num_tiles_x
            tile_grid_x = i % num_tiles_x
            tx = tile_x_start + tile_grid_x
            ty = tile_y_start + tile_grid_y

            # Calculate the pixel bounds of this tile in image coordinates
            tile_pixel_col_start = tx * self.tile_width
            tile_pixel_row_start = ty * self.tile_height

            # Calculate overlap between tile and window (in image coordinates)
            overlap_col_start = max(col_start, tile_pixel_col_start)
            overlap_col_stop = min(col_stop, tile_pixel_col_start + tile.width)
            overlap_row_start = max(row_start, tile_pixel_row_start)
            overlap_row_stop = min(row_stop, tile_pixel_row_start + tile.height)

            # Calculate source slice within the tile
            src_col_start = overlap_col_start - tile_pixel_col_start
            src_col_stop = overlap_col_stop - tile_pixel_col_start
            src_row_start = overlap_row_start - tile_pixel_row_start
            src_row_stop = overlap_row_stop - tile_pixel_row_start

            # Calculate destination slice within the output
            dst_col_start = overlap_col_start - col_start
            dst_col_stop = overlap_col_stop - col_start
            dst_row_start = overlap_row_start - row_start
            dst_row_stop = overlap_row_stop - row_start

            # Copy data
            output_data[
                :,
                dst_row_start:dst_row_stop,
                dst_col_start:dst_col_stop,
            ] = tile.data[:, src_row_start:src_row_stop, src_col_start:src_col_stop]

            # Copy mask if present
            if output_mask is not None and tile.mask is not None:
                output_mask[
                    dst_row_start:dst_row_stop,
                    dst_col_start:dst_col_stop,
                ] = tile.mask[src_row_start:src_row_stop, src_col_start:src_col_stop]
            # If tile has no mask but others do, the default True values remain

        # Calculate transform for the window
        window_transform = self.transform * Affine.translation(col_start, row_start)

        return Array(
            data=output_data,
            mask=output_mask,
            width=window_width,
            height=window_height,
            count=num_bands,
            transform=window_transform,
            crs=self.crs,
        )
