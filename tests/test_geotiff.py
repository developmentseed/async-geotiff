import pytest


@pytest.mark.asyncio
async def test_read_uint8_rgb_deflate_block64_cog():
    name = "uint8_rgb_deflate_block64_cog"

    geotiff = await load_rasterio_geotiff(name)
