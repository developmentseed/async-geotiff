from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Self

from affine import Affine
from async_tiff import TIFF
from async_tiff.enums import PhotometricInterpretation

from async_geotiff._crs import crs_from_geo_keys
from async_geotiff._fetch import FetchTileMixin
from async_geotiff._ifd import IFDReference
from async_geotiff._overview import Overview
from async_geotiff._transform import TransformMixin

if TYPE_CHECKING:
    from async_tiff import GeoKeyDirectory, ImageFileDirectory, ObspecInput
    from async_tiff.store import ObjectStore  # type: ignore # noqa: PGH003
    from pyproj.crs import CRS

    from async_geotiff.enums import Compression, Interleaving


@dataclass(frozen=True, init=False, kw_only=True, repr=False)
class GeoTIFF(FetchTileMixin, TransformMixin):
    """A class representing a GeoTIFF image."""

    _crs: CRS | None = None
    """A cached CRS instance.

    We don't use functools.cached_property on the `crs` attribute because of typing
    issues.
    """

    _tiff: TIFF
    """The underlying async-tiff TIFF instance that we wrap.
    """

    _primary_ifd: IFDReference = field(init=False)
    """The primary (first) IFD of the GeoTIFF.

    Some tags, like most geo tags, only exist on the primary IFD.
    """

    _mask_ifd: IFDReference | None = None
    """The mask IFD of the full-resolution GeoTIFF, if any.

    (positional index of the IFD in the TIFF file, IFD object)
    """

    _gkd: GeoKeyDirectory = field(init=False)
    """The GeoKeyDirectory of the primary IFD.
    """

    _overviews: list[Overview] = field(init=False)
    """A list of overviews for the GeoTIFF.
    """

    @property
    def _ifd(self) -> IFDReference:
        """An alias for the primary IFD to satisfy _fetch protocol."""
        return self._primary_ifd

    def __init__(self, tiff: TIFF) -> None:
        """Create a GeoTIFF from an existing TIFF instance."""
        first_ifd = tiff.ifds[0]
        gkd = first_ifd.geo_key_directory

        # Validate that this is indeed a GeoTIFF
        if gkd is None:
            raise ValueError("TIFF does not contain GeoTIFF keys")

        if len(tiff.ifds) == 0:
            raise ValueError("TIFF does not contain any IFDs")

        # We use object.__setattr__ because the dataclass is frozen
        object.__setattr__(self, "_tiff", tiff)
        object.__setattr__(self, "_primary_ifd", IFDReference(index=0, ifd=first_ifd))
        object.__setattr__(self, "_gkd", gkd)

        # Separate data IFDs and mask IFDs (skip the primary IFD at index 0)
        # Data IFDs are indexed by (width, height) for matching with masks
        data_ifds: dict[tuple[int, int], IFDReference] = {}
        mask_ifds: dict[tuple[int, int], IFDReference] = {}

        for idx, ifd in enumerate(tiff.ifds[1:], start=1):
            dims = (ifd.image_width, ifd.image_height)
            if is_mask_ifd(ifd):
                mask_ifds[dims] = IFDReference(index=idx, ifd=ifd)
            else:
                data_ifds[dims] = IFDReference(index=idx, ifd=ifd)

        # Find and set the mask for the primary IFD (matches primary dimensions)
        if primary_mask_ifd := mask_ifds.get(
            (first_ifd.image_width, first_ifd.image_height),
        ):
            object.__setattr__(self, "_mask_ifd", primary_mask_ifd)

        # Build overviews, sorted by resolution (highest to lowest, i.e., largest first)
        # Sort by width * height descending
        sorted_dims = sorted(data_ifds.keys(), key=lambda d: d[0] * d[1], reverse=True)

        overviews: list[Overview] = []
        for dims in sorted_dims:
            data_ifd = data_ifds[dims]
            mask_ifd = mask_ifds.get(dims)

            ovr = Overview._create(  # noqa: SLF001
                geotiff=self,
                gkd=gkd,
                ifd=data_ifd,
                mask_ifd=mask_ifd,
            )
            overviews.append(ovr)

        object.__setattr__(self, "_overviews", overviews)

    @classmethod
    async def open(
        cls,
        path: str,
        *,
        store: ObjectStore | ObspecInput,
        prefetch: int = 32768,
        multiplier: float = 2.0,
    ) -> Self:
        """Open a new GeoTIFF.

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
            path=path,
            store=store,
            prefetch=prefetch,
            multiplier=multiplier,
        )
        return cls(tiff)

    @property
    def block_shapes(self) -> list[tuple[int, int]]:
        """An ordered list of block shapes for each bands.

        Shapes are tuples and have the same ordering as the dataset's shape:

        - (count of image rows, count of image columns).
        """
        raise NotImplementedError

    def block_size(self, bidx: int, i: int, j: int) -> int:
        """Return the size in bytes of a particular block.

        Args:
            bidx: Band index, starting with 1.
            i: Row index of the block, starting with 0.
            j: Column index of the block, starting with 0.

        """
        raise NotImplementedError

    @cached_property
    def bounds(self) -> tuple[float, float, float, float]:
        """Return the bounds of the dataset in the units of its CRS.

        Returns:
            (lower left x, lower left y, upper right x, upper right y)

        """
        transform = self.transform

        # Hopefully types will be fixed with affine 3.0
        (left, top) = transform * (0, 0)  # type: ignore # noqa: PGH003
        (right, bottom) = transform * (self.width, self.height)  # type: ignore # noqa: PGH003

        return (left, bottom, right, top)

    @property
    def colorinterp(self) -> list[str]:
        """The color interpretation of each band in index order."""
        # TODO: we should return an enum here. The enum should match rasterio.
        # https://github.com/developmentseed/async-geotiff/issues/12
        raise NotImplementedError

    def colormap(self, bidx: int) -> dict[int, tuple[int, int, int]]:
        """Return a dict containing the colormap for a band.

        Args:
            bidx: The 1-based index of the band whose colormap will be returned.

        Returns:
            Mapping of color index value (starting at 0) to RGBA color as a
            4-element tuple.

        Raises:
            ValueError: If no colormap is found for the specified band (NULL color
                table).
            IndexError: If no band exists for the provided index.

        """
        raise NotImplementedError

    @property
    def compression(self) -> Compression:
        """The compression algorithm used for the dataset."""
        # TODO: should return an enum. The enum should match rasterio.
        # https://github.com/developmentseed/async-geotiff/issues/12
        # Also, is there ever a case where overviews have a different compression from
        # the base image?
        # Should we diverge from rasterio and not have this as a property returning a
        # single string?
        raise NotImplementedError

    @property
    def count(self) -> int:
        """The number of raster bands in the full image."""
        raise NotImplementedError

    @property
    def crs(self) -> CRS:
        """The dataset's coordinate reference system."""
        if self._crs is not None:
            return self._crs

        crs = crs_from_geo_keys(self._gkd)
        object.__setattr__(self, "_crs", crs)
        return crs

    @property
    def dtypes(self) -> list[str]:
        """The data types of each band in index order."""
        # TODO: not sure what the return type should be. Perhaps we should define a
        # `DataType` enum?
        # https://github.com/developmentseed/async-geotiff/issues/20
        raise NotImplementedError

    @property
    def height(self) -> int:
        """The height (number of rows) of the full image."""
        return self._primary_ifd.ifd.image_height

    def indexes(self) -> list[int]:
        """Return the 1-based indexes of each band in the dataset.

        For a 3-band dataset, this property will be [1, 2, 3].
        """
        return list(range(1, self._primary_ifd.ifd.samples_per_pixel + 1))

    @property
    def interleaving(self) -> Interleaving:
        """The interleaving scheme of the dataset."""
        # TODO: Should return an enum.
        # https://rasterio.readthedocs.io/en/stable/api/rasterio.enums.html#rasterio.enums.Interleaving
        raise NotImplementedError

    @property
    def is_tiled(self) -> bool:
        """Check if the dataset is tiled."""
        raise NotImplementedError

    @property
    def nodata(self) -> float | None:
        """The dataset's single nodata value."""
        nodata = self._primary_ifd.ifd.gdal_nodata
        if nodata is None:
            return None

        return float(nodata)

    @property
    def overviews(self) -> list[Overview]:
        """A list of overview levels for the dataset."""
        return self._overviews

    @property
    def photometric(self) -> PhotometricInterpretation | None:
        """The photometric interpretation of the dataset."""
        # TODO: should return enum
        # https://rasterio.readthedocs.io/en/stable/api/rasterio.enums.html#rasterio.enums.PhotometricInterp
        raise NotImplementedError

    @property
    def res(self) -> tuple[float, float]:
        """Return the (width, height) of pixels in the units of its CRS."""
        transform = self.transform
        return (transform.a, -transform.e)

    @property
    def shape(self) -> tuple[int, int]:
        """Get the shape (height, width) of the full image."""
        return (self.height, self.width)

    @property
    def tile_height(self) -> int:
        """The height in pixels per tile of the image."""
        return self._primary_ifd.ifd.tile_height or self.height

    @property
    def tile_width(self) -> int:
        """The width in pixels per tile of the image."""
        return self._primary_ifd.ifd.tile_width or self.width

    @property
    def transform(self) -> Affine:
        """Return the dataset's georeferencing transformation matrix.

        This transform maps pixel row/column coordinates to coordinates in the dataset's
        CRS.
        """
        if (tie_points := self._primary_ifd.ifd.model_tiepoint) and (
            model_scale := self._primary_ifd.ifd.model_pixel_scale
        ):
            x_origin = tie_points[3]
            y_origin = tie_points[4]
            x_resolution = model_scale[0]
            y_resolution = -model_scale[1]

            return Affine(x_resolution, 0, x_origin, 0, y_resolution, y_origin)

        if model_transformation := self._primary_ifd.ifd.model_transformation:
            # ModelTransformation is a 4x4 matrix in row-major order
            # [0  1  2  3 ]   [a  b  0  c]
            # [4  5  6  7 ] = [d  e  0  f]
            # [8  9  10 11]   [0  0  1  0]
            # [12 13 14 15]   [0  0  0  1]
            x_origin = model_transformation[3]
            y_origin = model_transformation[7]
            row_rotation = model_transformation[1]
            col_rotation = model_transformation[4]

            # TODO: confirm these are correct
            # Why does geotiff.js square and then square-root them?
            # https://github.com/developmentseed/async-geotiff/issues/7
            x_resolution = model_transformation[0]
            y_resolution = -model_transformation[5]

            return Affine(
                model_transformation[0],
                row_rotation,
                x_origin,
                col_rotation,
                model_transformation[5],
                y_origin,
            )

        raise ValueError("The image does not have an affine transformation.")

    @property
    def width(self) -> int:
        """The width (number of columns) of the full image."""
        return self._primary_ifd.ifd.image_width


def has_geokeys(ifd: ImageFileDirectory) -> bool:
    """Check if an IFD has GeoTIFF keys.

    Args:
        ifd: The IFD to check.

    """
    return ifd.geo_key_directory is not None


def is_mask_ifd(ifd: ImageFileDirectory) -> bool:
    """Check if an IFD is a mask IFD."""
    return (
        ifd.new_subfile_type is not None
        and ifd.new_subfile_type & 4 != 0
        and ifd.photometric_interpretation == PhotometricInterpretation.TransparencyMask
    )
