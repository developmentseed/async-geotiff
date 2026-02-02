from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Self, cast

import numpy as np
from affine import Affine
from async_tiff import TIFF
from async_tiff.enums import Compression as AsyncTiffCompression
from async_tiff.enums import (
    PhotometricInterpretation as AsyncTiffPhotometricInterpretation,
)
from async_tiff.enums import (
    PlanarConfiguration,
    SampleFormat,
)

from async_geotiff._crs import crs_from_geo_keys
from async_geotiff._fetch import FetchTileMixin
from async_geotiff._overview import Overview
from async_geotiff._read import ReadMixin
from async_geotiff._transform import TransformMixin
from async_geotiff.colormap import Colormap
from async_geotiff.enums import Compression, Interleaving, PhotometricInterpretation

if TYPE_CHECKING:
    from async_tiff import GeoKeyDirectory, ImageFileDirectory, ObspecInput
    from async_tiff.store import ObjectStore  # type: ignore # noqa: PGH003
    from pyproj.crs import CRS


@dataclass(frozen=True, init=False, kw_only=True, repr=False)
class GeoTIFF(ReadMixin, FetchTileMixin, TransformMixin):
    """A class representing a GeoTIFF image."""

    _crs: CRS | None = None
    """A cached CRS instance.

    We don't use functools.cached_property on the `crs` attribute because of typing
    issues.
    """

    _tiff: TIFF
    """The underlying async-tiff TIFF instance that we wrap.
    """

    _primary_ifd: ImageFileDirectory = field(init=False)
    """The primary (first) IFD of the GeoTIFF.

    Some tags, like most geo tags, only exist on the primary IFD.
    """

    _mask_ifd: ImageFileDirectory | None = None
    """The mask IFD of the full-resolution GeoTIFF, if any.
    """

    _gkd: GeoKeyDirectory = field(init=False)
    """The GeoKeyDirectory of the primary IFD.
    """

    _overviews: list[Overview] = field(init=False)
    """A list of overviews for the GeoTIFF.
    """

    @property
    def _ifd(self) -> ImageFileDirectory:
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
        object.__setattr__(self, "_primary_ifd", first_ifd)
        object.__setattr__(self, "_gkd", gkd)

        # Separate data IFDs and mask IFDs (skip the primary IFD at index 0)
        # Data IFDs are indexed by (width, height) for matching with masks
        data_ifds: dict[tuple[int, int], ImageFileDirectory] = {}
        mask_ifds: dict[tuple[int, int], ImageFileDirectory] = {}

        for ifd in tiff.ifds[1:]:
            dims = (ifd.image_width, ifd.image_height)
            if is_mask_ifd(ifd):
                mask_ifds[dims] = ifd
            else:
                data_ifds[dims] = ifd

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

    @cached_property
    def bounds(self) -> tuple[float, float, float, float]:
        """Return the bounds of the dataset in the units of its CRS.

        Returns:
            (lower left x, lower left y, upper right x, upper right y)

        """
        transform = self.transform

        # TODO: Remove type casts once affine supports typing overloads for matmul
        # https://github.com/rasterio/affine/pull/137
        (left, top) = cast("tuple[float, float]", transform * (0, 0))
        (right, bottom) = cast(
            "tuple[float, float]",
            transform * (self.width, self.height),
        )

        return (left, bottom, right, top)

    # @property
    # def colorinterp(self) -> list[str]:
    #     """The color interpretation of each band in index order."""
    # TODO: we should return an enum here. The enum should match rasterio.
    # https://github.com/developmentseed/async-geotiff/issues/12
    # raise NotImplementedError

    @property
    def colormap(self) -> Colormap | None:
        """Return the Colormap stored in the file, if any.

        Returns:
            A Colormap instance if the dataset has a colormap, else None.

        """
        if upstream_colormap := self._primary_ifd.colormap:
            return Colormap(_cmap=upstream_colormap, _nodata=self.nodata)

        return None

    @property
    def compression(self) -> Compression | None:  # noqa: PLR0911
        """The compression algorithm used for the dataset.

        Returns None if the compression is not recognized.
        """
        match self._primary_ifd.compression:
            case AsyncTiffCompression.JPEG:
                return Compression.JPEG
            case AsyncTiffCompression.LZW:
                return Compression.LZW
            case AsyncTiffCompression.PackBits:
                return Compression.PACKBITS
            case AsyncTiffCompression.Deflate:
                return Compression.DEFLATE
            case AsyncTiffCompression.Uncompressed:
                return Compression.UNCOMPRESSED
            case AsyncTiffCompression.ZSTD:
                return Compression.ZSTD

        return None

    @property
    def count(self) -> int:
        """The number of raster bands in the full image."""
        return self._primary_ifd.samples_per_pixel

    @property
    def crs(self) -> CRS:
        """The dataset's coordinate reference system."""
        if self._crs is not None:
            return self._crs

        crs = crs_from_geo_keys(self._gkd)

        # We manually manage the cached property here because `@cached_property` messes
        # with type-checking
        object.__setattr__(self, "_crs", crs)

        return crs

    @property
    def dtype(self) -> np.dtype | None:  # noqa: PLR0911, C901
        """The numpy data type of the image.

        Returns None if the data type is unknown/not supported.
        """
        formats = set(self._primary_ifd.sample_format)
        bits_per_sample = set(self._primary_ifd.bits_per_sample)

        if len(formats) != 1:
            raise ValueError("Mixed sample formats are not supported.")
        if len(bits_per_sample) != 1:
            raise ValueError("Mixed bits per sample are not supported.")

        match formats.pop(), bits_per_sample.pop():
            case (SampleFormat.Uint, 8):
                return np.dtype(np.uint8)
            case (SampleFormat.Uint, 16):
                return np.dtype(np.uint16)
            case (SampleFormat.Uint, 32):
                return np.dtype(np.uint32)
            case (SampleFormat.Uint, 64):
                return np.dtype(np.uint64)
            case (SampleFormat.Float, 32):
                return np.dtype(np.float32)
            case (SampleFormat.Float, 64):
                return np.dtype(np.float64)
            case (SampleFormat.Int, 8):
                return np.dtype(np.int8)
            case (SampleFormat.Int, 16):
                return np.dtype(np.int16)
            case (SampleFormat.Int, 32):
                return np.dtype(np.int32)
            case (SampleFormat.Int, 64):
                return np.dtype(np.int64)

        return None

    @property
    def height(self) -> int:
        """The height (number of rows) of the full image."""
        return self._primary_ifd.image_height

    @property
    def interleaving(self) -> Interleaving:
        """The interleaving scheme of the dataset."""
        planar_configuration = self._primary_ifd.planar_configuration

        if planar_configuration == PlanarConfiguration.Planar:
            return Interleaving.BAND

        return Interleaving.PIXEL

    @property
    def is_tiled(self) -> bool:
        """Check if the dataset is tiled."""
        return (
            self._primary_ifd.tile_height is not None
            and self._primary_ifd.tile_width is not None
        )

    @property
    def nodata(self) -> float | None:
        """The dataset's single nodata value."""
        nodata = self._primary_ifd.gdal_nodata
        if nodata is None:
            return None

        return float(nodata)

    @property
    def overviews(self) -> list[Overview]:
        """A list of overview levels for the dataset.

        Overviews are reduced-resolution versions of the main image used for faster
        rendering at lower zoom levels.

        This list of overviews is ordered from finest to coarsest resolution. The first
        element of the list is the highest-resolution after the base image.
        """
        return self._overviews

    @property
    def photometric(self) -> PhotometricInterpretation | None:  # noqa: PLR0911
        """The photometric interpretation of the dataset.

        Returns None if the photometric interpretation is not recognized.
        """
        match self._primary_ifd.photometric_interpretation:
            case AsyncTiffPhotometricInterpretation.WhiteIsZero:
                return PhotometricInterpretation.WHITE_IS_ZERO
            case AsyncTiffPhotometricInterpretation.BlackIsZero:
                return PhotometricInterpretation.BLACK_IS_ZERO
            case AsyncTiffPhotometricInterpretation.RGB:
                return PhotometricInterpretation.RGB
            case AsyncTiffPhotometricInterpretation.RGBPalette:
                return PhotometricInterpretation.RGBPALETTE
            case AsyncTiffPhotometricInterpretation.TransparencyMask:
                return PhotometricInterpretation.TRANSPARENCY_MASK
            case AsyncTiffPhotometricInterpretation.CMYK:
                return PhotometricInterpretation.CMYK
            case AsyncTiffPhotometricInterpretation.YCbCr:
                return PhotometricInterpretation.YCBCR
            case AsyncTiffPhotometricInterpretation.CIELab:
                return PhotometricInterpretation.CIELAB

        return None

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
        if self._primary_ifd.tile_height is None:
            raise ValueError("The image is not tiled.")

        return self._primary_ifd.tile_height

    @property
    def tile_width(self) -> int:
        """The width in pixels per tile of the image."""
        if self._primary_ifd.tile_width is None:
            raise ValueError("The image is not tiled.")

        return self._primary_ifd.tile_width

    @property
    def transform(self) -> Affine:
        """Return the dataset's georeferencing transformation matrix.

        This transform maps pixel row/column coordinates to coordinates in the dataset's
        CRS.
        """
        if (tie_points := self._primary_ifd.model_tiepoint) and (
            model_scale := self._primary_ifd.model_pixel_scale
        ):
            x_origin = tie_points[3]
            y_origin = tie_points[4]
            x_resolution = model_scale[0]
            y_resolution = -model_scale[1]

            return Affine(x_resolution, 0, x_origin, 0, y_resolution, y_origin)

        if model_transformation := self._primary_ifd.model_transformation:
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
        return self._primary_ifd.image_width


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
        and ifd.photometric_interpretation
        == AsyncTiffPhotometricInterpretation.TransparencyMask
    )
