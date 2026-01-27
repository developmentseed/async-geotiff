"""Enums used by async_geotiff."""

from enum import Enum, IntEnum

# ruff: noqa: D101


# https://github.com/rasterio/rasterio/blob/2d79e5f3a00e919ecaa9573adba34a78274ce48c/rasterio/enums.py#L153-L174
class Compression(Enum):
    """Available compression algorithms for GeoTIFFs.

    Note that compression options for EXR, MRF, etc are not included
    in this enum.
    """

    jpeg = "JPEG"
    lzw = "LZW"
    packbits = "PACKBITS"
    deflate = "DEFLATE"
    ccittrle = "CCITTRLE"
    ccittfax3 = "CCITTFAX3"
    ccittfax4 = "CCITTFAX4"
    lzma = "LZMA"
    none = "NONE"
    zstd = "ZSTD"
    lerc = "LERC"
    lerc_deflate = "LERC_DEFLATE"
    lerc_zstd = "LERC_ZSTD"
    webp = "WEBP"
    jpeg2000 = "JPEG2000"


# https://github.com/rasterio/rasterio/blob/2d79e5f3a00e919ecaa9573adba34a78274ce48c/rasterio/enums.py#L177-L182
class Interleaving(Enum):
    pixel = "PIXEL"
    line = "LINE"
    band = "BAND"
    #: tile requires GDAL 3.11+
    tile = "TILE"


# https://github.com/rasterio/rasterio/blob/2d79e5f3a00e919ecaa9573adba34a78274ce48c/rasterio/enums.py#L185-L189
class MaskFlags(IntEnum):
    all_valid = 1
    per_dataset = 2
    alpha = 4
    nodata = 8


# https://github.com/rasterio/rasterio/blob/2d79e5f3a00e919ecaa9573adba34a78274ce48c/rasterio/enums.py#L192-L200
class PhotometricInterp(Enum):
    black = "MINISBLACK"
    white = "MINISWHITE"
    rgb = "RGB"
    cmyk = "CMYK"
    ycbcr = "YCbCr"
    cielab = "CIELAB"
    icclab = "ICCLAB"
    itulab = "ITULAB"
