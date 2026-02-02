---
draft: false
date: 2026-02-03
categories:
  - Release
authors:
  - kylebarron
---

# Introducing Async-GeoTIFF

We're introducing Async-GeoTIFF, a new high-level library for reading [GeoTIFF][geotiff] and [Cloud-Optimized GeoTIFF][cogeo] (COG) data. By leveraging [asynchronous I/O][async-io-wikipedia], we can speed up concurrent GeoTIFF data fetching.

According to the [2025 GDAL user survey][gdal_user_survey], almost 90% of respondents use GeoTIFFs and COGs as their primary raster data format. While [GDAL] and [Rasterio] are fantastic, rock-solid tools, they don't support asynchronous I/O and are missing some modern Python usability features, like type hinting.

We [previously found][pyasyncio-benchmark-results] concurrent GeoTIFF metadata parsing at scale to be **25x faster** with the underlying Rust-based [Async-TIFF] library than with Rasterio. We expect Async-GeoTIFF to bring similar performance improvements to concurrent server-side image downloading, such as in [Titiler].

[async-io-wikipedia]: https://en.wikipedia.org/wiki/Asynchronous_I/O
[async-tiff]: https://github.com/developmentseed/async-tiff
[cogeo]: https://cogeo.org/
[gdal_user_survey]: https://gdal.org/en/stable/community/user_survey_2025.html#raster-data-formats
[GDAL]: https://gdal.org/en/stable/index.html
[geotiff]: https://en.wikipedia.org/wiki/GeoTIFF
[pyasyncio-benchmark-results]: https://github.com/geospatial-jeff/pyasyncio-benchmark/blob/8809b62125ae75b3d216475e9964a6df4d96a91c/test_results/20250423_results/ec2_m5_300seconds/aggregated_results.csv
[rasterio]: https://rasterio.readthedocs.io/
[Titiler]: https://github.com/developmentseed/titiler

<!-- more -->

