---
draft: false
date: 2026-02-03
categories:
  - Release
authors:
  - kylebarron
---

# Introducing Async-GeoTIFF

We're introducing Async-GeoTIFF, a new high-level library for reading [GeoTIFF][geotiff] and [Cloud-Optimized GeoTIFF][cogeo] (COG) data. By leveraging [asynchronous I/O][async-io-python], we can speed up concurrent GeoTIFF data fetching.

According to the [2025 GDAL user survey][gdal_user_survey], almost 90% of respondents use GeoTIFFs and COGs as their primary raster data format. While [GDAL] and [Rasterio] are fantastic, rock-solid tools, they don't support asynchronous I/O and are missing some modern Python usability features, like type hinting.

We [previously found][pyasyncio-benchmark-results] concurrent GeoTIFF metadata parsing at scale to be **25x faster** with the underlying Rust-based [Async-TIFF] library than with Rasterio. We expect Async-GeoTIFF to bring similar performance improvements to concurrent server-side image downloading, such as in [Titiler].

[async-io-python]: https://realpython.com/async-io-python/
[async-tiff]: https://github.com/developmentseed/async-tiff
[cogeo]: https://cogeo.org/
[gdal_user_survey]: https://gdal.org/en/stable/community/user_survey_2025.html#raster-data-formats
[GDAL]: https://gdal.org/en/stable/index.html
[geotiff]: https://en.wikipedia.org/wiki/GeoTIFF
[pyasyncio-benchmark-results]: https://github.com/geospatial-jeff/pyasyncio-benchmark/blob/8809b62125ae75b3d216475e9964a6df4d96a91c/test_results/20250423_results/ec2_m5_300seconds/aggregated_results.csv
[rasterio]: https://rasterio.readthedocs.io/
[Titiler]: https://github.com/developmentseed/titiler

<!-- more -->

## High-level, Easy-to-Use API


- Load from full-resolution or reduced-resolution overviews as 3D [NumPy] arrays.
- Simplify handling of nodata values and nodata masks with [NumPy] [masked arrays].
- Interpret Coordinate Reference Systems as [PyProj] CRS objects.
- Find pixels with geotransforms exposed as [Affine] matrices.
- Represent internal COG tile grids as [TileMatrixSets][TileMatrixSet] via [Morecantile] integration.

## Performance-focused

- Rust core ensures compiled performance.
- CPU-bound image decoding happens in a thread pool, without blocking the async executor.
- Buffer protocol integration for zero-copy data sharing between Rust and Python.

Until GDAL 3.11, GDAL TIFF parsing

## Obstore integration for remote data support

## More tractable data caching

GDAL providesa block cache, but it's very much a black box.

Obspec for data caching.

## Full type hinting

## Growing test suite

We recently created [geotiff-test-data], a repository to hold various sorts of GeoTIFF test files. This repo can then be used as a submodule to provide test fixtures for various repositories like Async-GeoTIFF and [deck.gl-raster] without growing the disk size of the primary Git repository.

The majority of these test files are [written using Rasterio](https://github.com/developmentseed/geotiff-test-data/blob/7d1cecbc91d909a3e2fa7d554b904831a5378d3c/rasterio_generated/write_utils.py#L19)

[geotiff-test-data]: https://github.com/developmentseed/geotiff-test-data
[deck.gl-raster]: https://github.com/developmentseed/deck.gl-raster

## Future work

More compression support.

- Better handling of GeoTIFF photometric interpretations like YCbCr
- JPEG XL
- LERC
-
