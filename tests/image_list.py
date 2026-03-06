from __future__ import annotations

ALL_COG_IMAGES: list[tuple[str, str]] = [
    ("nlcd", "nlcd_landcover"),
    ("rasterio", "cog_uint8_rgb_mask"),
    ("rasterio", "cog_uint8_rgb_nodata"),
    ("rasterio", "cog_uint8_rgba"),
    ("rasterio", "float32_1band_lerc_block32"),
    ("rasterio", "float32_1band_lerc_deflate_block32"),
    ("rasterio", "float32_1band_lerc_zstd_block32"),
    ("rasterio", "uint16_1band_lzw_block128_predictor2"),
    ("rasterio", "uint16_1band_scale_offset"),
    ("rasterio", "uint8_1band_deflate_block128_unaligned"),
    ("rasterio", "uint8_1band_lzma_block64"),
    ("rasterio", "uint8_1band_lzw_block64_predictor2"),
    ("rasterio", "uint8_rgb_deflate_block64_cog"),
    ("rasterio", "uint8_rgb_webp_block64_cog"),
    ("rasterio", "uint8_rgba_webp_block64_cog"),
    ("umbra", "sydney_airport_GEC"),
]
"""All fixtures that have overviews where the data can be compared with rasterio."""

ALL_DATA_IMAGES: list[tuple[str, str]] = [
    *ALL_COG_IMAGES,
    ("eox", "eox_cloudless"),
    ("rasterio", "antimeridian"),
    ("rasterio", "custom_crs"),
    ("rasterio", "pixel_as_point"),
]
"""All fixtures where the data can be compared with rasterio.

If images have overviews, they should be included in `ALL_COG_IMAGES` instead.
"""


ALL_TEST_IMAGES: list[tuple[str, str]] = [
    *ALL_DATA_IMAGES,
    # YCbCr is auto-decompressed by rasterio
    ("vantor", "maxar_opendata_yellowstone_visual"),
    ("source-coop-alpha-earth", "xjejfvrbm1fbu1ecw-0000000000-0000008192"),
]
"""All fixtures where we test metadata parsing."""

ALL_MASKED_IMAGES: list[tuple[str, str]] = [
    ("vantor", "maxar_opendata_yellowstone_visual"),
]
"""All fixtures that have a nodata mask."""
