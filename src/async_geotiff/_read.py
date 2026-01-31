"""Higher-level read utilities for cross-tile operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import numpy as np
from affine import Affine

from async_geotiff import Array
from async_geotiff._fetch import HasTiffReference
from async_geotiff.windows import Window

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from async_geotiff._tile import Tile


# Window type: tuple of ((row_start, row_stop), (col_start, col_stop))
WindowLike = tuple[tuple[int, int], tuple[int, int]] | Window


class CanFetchTiles(HasTiffReference, Protocol):
    """Protocol for objects that can fetch tiles."""

    async def fetch_tiles(
        self,
        xs: list[int],
        ys: list[int],
    ) -> list[Tile]: ...


class ReadMixin:
    async def read(
        self: CanFetchTiles,
        *,
        window: WindowLike | None = None,
    ) -> Array:
        """Read pixel data for a window region.

        This method fetches all tiles that intersect the given window and
        stitches them together, returning only the pixels within the window.

        Args:
            window: A Window object or a tuple of ((row_start, row_stop),
                (col_start, col_stop)) defining the pixel region to read.
                The tuple format is compatible with rasterio's window tuple format,
                with the caveat that here we only support integer indices, not float
                indices. If None, the entire image is read.

        Returns:
            An Array containing the pixel data for the requested window.

        Raises:
            IndexError: If the window extends outside the image bounds.

        """
        return await read(self, window=window)


async def read(
    self: CanFetchTiles,
    *,
    window: WindowLike | None = None,
) -> Array:
    # Normalize window to Window object
    if window is None:
        win = Window(col_off=0, row_off=0, width=self.width, height=self.height)
    elif isinstance(window, Window):
        win = window
    else:
        win = Window.from_slices(rows=window[0], cols=window[1])

    # Most validation occurred in construction of Window; here we just check against
    # image size
    if win.col_off + win.width > self.width or win.row_off + win.height > self.height:
        raise IndexError(
            f"Window extends outside image bounds.\n"
            f"Window: cols={win.col_off}:{win.col_off + win.width}, "
            f"rows={win.row_off}:{win.row_off + win.height}.\n"
            f"Image size: {self.height}x{self.width}",
        )

    # Calculate which tiles we need to fetch
    tile_x_start = win.col_off // self.tile_width
    tile_x_stop = (win.col_off + win.width - 1) // self.tile_width + 1
    tile_y_start = win.row_off // self.tile_height
    tile_y_stop = (win.row_off + win.height - 1) // self.tile_height + 1

    # Build list of tile coordinates
    xs: list[int] = []
    ys: list[int] = []
    for tx in range(tile_x_start, tile_x_stop):
        for ty in range(tile_y_start, tile_y_stop):
            xs.append(tx)
            ys.append(ty)

    # Fetch all needed tiles
    tiles = await self.fetch_tiles(xs, ys)

    # Get number of bands from first tile
    num_bands = tiles[0].array.count
    dtype = tiles[0].array.data.dtype

    # Create output array
    output_data = np.empty((num_bands, win.height, win.width), dtype=dtype)

    # Check if any tiles have masks
    output_mask: NDArray[np.bool_] | None = None
    if self._mask_ifd is not None:
        output_mask = np.ones((win.height, win.width), dtype=np.bool_)

    # Assemble tiles into output arrays
    assemble_tiles(
        tiles=tiles,
        window=win,
        tile_width=self.tile_width,
        tile_height=self.tile_height,
        output_data=output_data,
        output_mask=output_mask,
    )

    # Calculate transform for the window
    window_transform = self.transform * Affine.translation(
        win.col_off,
        win.row_off,
    )

    return Array(
        data=output_data,
        mask=output_mask,
        width=win.width,
        height=win.height,
        count=num_bands,
        transform=window_transform,
        crs=self.crs,
    )


def assemble_tiles(  # noqa: PLR0913
    *,
    tiles: list[Tile],
    window: Window,
    tile_width: int,
    tile_height: int,
    output_data: NDArray[np.generic],
    output_mask: NDArray[np.bool_] | None,
) -> None:
    """Assemble multiple tiles into output arrays.

    This function copies data from tiles into the appropriate positions
    in the output arrays, handling partial tiles at window boundaries.

    Args:
        tiles: List of Tile objects, each carrying its grid position.
        window: The target window being read.
        tile_width: Width of each tile in pixels.
        tile_height: Height of each tile in pixels.
        output_data: Output array with shape (bands, height, width) to fill.
        output_mask: Output mask with shape (height, width) to fill, or None.

    """
    for tile in tiles:
        # Create a window for this tile's position in image coordinates
        tile_window = Window(
            col_off=tile.x * tile_width,
            row_off=tile.y * tile_height,
            width=tile.array.width,
            height=tile.array.height,
        )

        # Calculate the intersection between tile and target window
        overlap = window.intersection(tile_window)

        # Calculate source slice within the tile
        src_col_start = overlap.col_off - tile_window.col_off
        src_col_stop = src_col_start + overlap.width
        src_row_start = overlap.row_off - tile_window.row_off
        src_row_stop = src_row_start + overlap.height

        # Calculate destination slice within the output
        dst_col_start = overlap.col_off - window.col_off
        dst_col_stop = dst_col_start + overlap.width
        dst_row_start = overlap.row_off - window.row_off
        dst_row_stop = dst_row_start + overlap.height

        # Copy data
        output_data[
            :,
            dst_row_start:dst_row_stop,
            dst_col_start:dst_col_stop,
        ] = tile.array.data[:, src_row_start:src_row_stop, src_col_start:src_col_stop]

        # Copy mask if present
        if output_mask is not None and tile.array.mask is not None:
            output_mask[
                dst_row_start:dst_row_stop,
                dst_col_start:dst_col_stop,
            ] = tile.array.mask[src_row_start:src_row_stop, src_col_start:src_col_stop]
