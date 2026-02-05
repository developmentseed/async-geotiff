from __future__ import annotations

ALL_DATA_IMAGES: list[tuple[str, str]] = [
    ("nlcd", "nlcd_landcover"),
    ("rasterio", "uint16_1band_lzw_block128_predictor2"),
    ("rasterio", "uint8_1band_deflate_block128_unaligned"),
    ("rasterio", "uint8_1band_lzma_block64"),
    ("rasterio", "uint8_rgb_deflate_block64_cog"),
    ("rasterio", "uint8_rgb_webp_block64_cog"),
    ("rasterio", "uint8_rgba_webp_block64_cog"),
    ("rasterio", "float32_1band_lerc_block32"),
    ("umbra", "sydney_airport_GEC"),
]
"""All fixtures where the data can be compared with rasterio."""


ALL_TEST_IMAGES: list[tuple[str, str]] = [
    *ALL_DATA_IMAGES,
    # YCbCr is auto-decompressed by rasterio
    ("vantor", "maxar_opendata_yellowstone_visual"),
]
"""All fixtures where we test metadata parsing."""

ALL_MASKED_IMAGES: list[tuple[str, str]] = [
    ("vantor", "maxar_opendata_yellowstone_visual"),
]
"""All fixtures that have a nodata mask."""
