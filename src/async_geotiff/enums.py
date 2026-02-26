"""Enums used by async_geotiff."""

from enum import Enum, IntEnum

# ruff: noqa: D101


# https://github.com/rasterio/rasterio/blob/2d79e5f3a00e919ecaa9573adba34a78274ce48c/rasterio/enums.py#L153-L174
class Compression(Enum):
    """Available compression algorithms for GeoTIFFs."""

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
    """GeoTIFF band interleaving options."""

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


# https://github.com/rasterio/rasterio/blob/04a8620f710814459f2a8dfa2d3d302b66a5408e/rasterio/enums.py#L30-L72
class ColorInterp(IntEnum):
    """Raster band color interpretation."""

    UNDEFINED = 0
    GRAY = 1
    GREY = 1
    PALETTE = 2
    RED = 3
    GREEN = 4
    BLUE = 5
    ALPHA = 6
    HUE = 7
    SATURATION = 8
    LIGHTNESS = 9
    CYAN = 10
    MAGENTA = 11
    YELLOW = 12
    BLACK = 13
    Y = 14
    Cb = 15
    Cr = 16
