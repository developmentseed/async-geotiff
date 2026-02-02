"""Enums used by async_geotiff."""

from enum import Enum

# ruff: noqa: D101


# https://github.com/rasterio/rasterio/blob/2d79e5f3a00e919ecaa9573adba34a78274ce48c/rasterio/enums.py#L153-L174
class Compression(Enum):
    """Available compression algorithms for GeoTIFFs.

    Note that compression options for EXR, MRF, etc are not included
    in this enum.
    """

    JPEG = "JPEG"
    LZW = "LZW"
    PACKBITS = "PACKBITS"
    DEFLATE = "DEFLATE"
    CCITTRLE = "CCITTRLE"
    CCITTFAX3 = "CCITTFAX3"
    CCITTFAX4 = "CCITTFAX4"
    LZMA = "LZMA"
    NONE = "NONE"
    ZSTD = "ZSTD"
    LERC = "LERC"
    LERC_DEFLATE = "LERC_DEFLATE"
    LERC_ZSTD = "LERC_ZSTD"
    WEBP = "WEBP"
    JPEG2000 = "JPEG2000"
    UNCOMPRESSED = "UNCOMPRESSED"


# https://github.com/rasterio/rasterio/blob/2d79e5f3a00e919ecaa9573adba34a78274ce48c/rasterio/enums.py#L177-L182
class Interleaving(Enum):
    PIXEL = "PIXEL"
    BAND = "BAND"
    # TODO: Support GDAL's new TILE interleaving option
    # https://gdal.org/en/stable/drivers/raster/cog.html#general-creation-options


# https://github.com/rasterio/rasterio/blob/2d79e5f3a00e919ecaa9573adba34a78274ce48c/rasterio/enums.py#L192-L200
class PhotometricInterpretation(Enum):
    WHITE_IS_ZERO = "MINISWHITE"
    BLACK_IS_ZERO = "MINISBLACK"
    RGB = "RGB"
    RGBPALETTE = "PALETTE"
    TRANSPARENCY_MASK = "MASK"
    CMYK = "CMYK"
    YCBCR = "YCbCr"
    CIELAB = "CIELAB"
