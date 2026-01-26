from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Self

from async_tiff import TIFF, ImageFileDirectory, ObspecInput

from async_geotiff.enums import Compression, Interleaving, PhotometricInterp

if TYPE_CHECKING:
    import pyproj
    from affine import Affine
    from async_tiff.store import ObjectStore


class GeoTIFF:
    """A class representing a GeoTIFF dataset."""

    _tiff: TIFF
    """The underlying async-tiff TIFF instance that we wrap.
    """

    _primary_ifd: ImageFileDirectory
    """The primary (first) IFD of the GeoTIFF.

    Some tags, like most geo tags, only exist on the primary IFD.
    """

    def __init__(self, tiff: TIFF) -> None:
        """Create a GeoTIFF from an existing TIFF instance."""
        # Validate that this is indeed a GeoTIFF
        if not has_geokeys(tiff.ifds[0]):
            raise ValueError("TIFF does not contain GeoTIFF keys")

        if len(tiff.ifds) == 0:
            raise ValueError("TIFF does not contain any IFDs")

        self._tiff = tiff
        self._primary_ifd = tiff.ifds[0]

    @classmethod
    async def open(
        cls,
        path: str,
        *,
        store: ObjectStore | ObspecInput,
        prefetch: int = 32768,
        multiplier: int | float = 2.0,
    ) -> Self:
        """Open a new TIFF.

        Args:
            path: The path within the store to read from.
            store: The backend to use for data fetching.
            prefetch: The number of initial bytes to read up front.
            multiplier: The multiplier to use for readahead size growth. Must be
                greater than 1.0. For example, for a value of `2.0`, the first metadata
                read will be of size `prefetch`, and then the next read will be of size
                `prefetch * 2`.

        Returns:
            A TIFF instance.
        """
        tiff = await TIFF.open(
            path=path, store=store, prefetch=prefetch, multiplier=multiplier
        )
        return cls(tiff)

    @property
    def block_shapes(self) -> list[tuple[int, int]]:
        """An ordered list of block shapes for each bands

        Shapes are tuples and have the same ordering as the dataset's shape:

        - (count of image rows, count of image columns).
        """
        raise NotImplementedError()

    def block_size(self, bidx: int, i: int, j: int) -> int:
        """Returns the size in bytes of a particular block.

        Args:
            bidx: Band index, starting with 1.
            i: Row index of the block, starting with 0.
            j: Column index of the block, starting with 0.
        """
        raise NotImplementedError()

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Returns the bounds of the dataset in the units of its coordinate reference system.

        Returns:
            (lower left x, lower left y, upper right x, upper right y)
        """
        raise NotImplementedError()

    @property
    def colorinterp(self) -> list[str]:
        """The color interpretation of each band in index order."""
        # TODO: we should return an enum here. The enum should match rasterio.
        raise NotImplementedError()

    def colormap(self, bidx: int) -> dict[int, tuple[int, int, int]]:
        """Returns a dict containing the colormap for a band.

        Args:
            bidx: The 1-based index of the band whose colormap will be returned.

        Returns:
            Mapping of color index value (starting at 0) to RGBA color as a
            4-element tuple.

        Raises:
            ValueError
                If no colormap is found for the specified band (NULL color table).
            IndexError
                If no band exists for the provided index.

        """
        raise NotImplementedError()

    @property
    def compression(self) -> Compression:
        """The compression algorithm used for the dataset."""
        # TODO: should return an enum. The enum should match rasterio.
        # Also, is there ever a case where overviews have a different compression from
        # the base image?
        # Should we diverge from rasterio and not have this as a property returning a
        # single string?
        raise NotImplementedError()

    @property
    def count(self) -> int:
        """The number of raster bands in the dataset."""
        raise NotImplementedError()

    @property
    def crs(self) -> pyproj.CRS:
        """The dataset's coordinate reference system."""
        raise NotImplementedError()

    @property
    def dtypes(self) -> list[str]:
        """The data types of each band in index order."""
        # TODO: not sure what the return type should be. Perhaps we should define a
        # `DataType` enum?
        raise NotImplementedError()

    @property
    def height(self) -> int:
        """The height (number of rows) of the dataset."""
        raise NotImplementedError()

    def index(
        self,
        x: float,
        y: float,
        op=None,
    ) -> tuple[int, int]:
        """Get the (row, col) index of the pixel containing (x, y).

        Args:
            x: x value in coordinate reference system
            y: y value in coordinate reference system
            op: function, optional (default: numpy.floor)
                Function to convert fractional pixels to whole numbers
                (floor, ceiling, round)

        Returns:
            (row index, col index)
        """
        raise NotImplementedError()

    def indexes(self) -> list[int]:
        """The 1-based indexes of each band in the dataset

        For a 3-band dataset, this property will be [1, 2, 3].
        """
        raise NotImplementedError()

    @property
    def interleaving(self) -> Interleaving:
        """The interleaving scheme of the dataset."""
        # TODO: Should return an enum.
        # https://rasterio.readthedocs.io/en/stable/api/rasterio.enums.html#rasterio.enums.Interleaving
        raise NotImplementedError()

    @property
    def is_tiled(self) -> bool:
        """Check if the dataset is tiled."""
        raise NotImplementedError()

    @property
    def nodata(self) -> float | int | None:
        """The dataset's single nodata value."""
        raise NotImplementedError()

    @property
    def photometric(self) -> PhotometricInterp | None:
        """The photometric interpretation of the dataset."""
        # TODO: should return enum
        # https://rasterio.readthedocs.io/en/stable/api/rasterio.enums.html#rasterio.enums.PhotometricInterp
        raise NotImplementedError()

    @property
    def res(self) -> tuple[float, float]:
        """Returns the (width, height) of pixels in the units of its coordinate reference system."""
        raise NotImplementedError()

    @property
    def shape(self) -> tuple[int, int]:
        """Get the shape (height, width) of the full image."""
        raise NotImplementedError()

    @property
    def transform(self) -> Affine:
        """The dataset's georeferencing transformation matrix

        This transform maps pixel row/column coordinates to coordinates in the dataset's coordinate reference system.
        """
        raise NotImplementedError()

    @property
    def width(self) -> int:
        """The width (number of columns) of the dataset."""
        raise NotImplementedError()

    def xy(
        self,
        row: int,
        col: int,
        offset: Literal["center", "ul", "ur", "ll", "lr"] = "center",
    ) -> tuple[float, float]:
        """Get the coordinates x, y of a pixel at row, col.

        The pixel's center is returned by default, but a corner can be returned
        by setting `offset` to one of `ul, ur, ll, lr`.

        Parameters:
            row: Pixel row.
            col: Pixel column.
            offset: Determines if the returned coordinates are for the center of the
                pixel or for a corner.

        """
        raise NotImplementedError()


def has_geokeys(ifd: ImageFileDirectory) -> bool:
    """Check if an IFD has GeoTIFF keys.

    Args:
        ifd: The IFD to check.

    """
    return ifd.geo_key_directory is not None
