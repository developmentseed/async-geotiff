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

According to the [2025 GDAL user survey][gdal_user_survey], almost 90% of respondents use GeoTIFFs and COGs as their primary raster data format. While [GDAL] and its Python bindings [Rasterio] are fantastic, rock-solid tools, they don't support asynchronous I/O and are missing some modern Python usability features, like type hinting.

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

## High-level and Easy-to-Use

We can open up a GeoTIFF using the [Obstore] integration:

```py
from async_geotiff import GeoTIFF
from obstore.store import S3Store

store = S3Store("sentinel-cogs", region="us-west-2", skip_signature=True)
path = "sentinel-s2-l2a-cogs/12/S/UF/2022/6/S2B_12SUF_20220609_0_L2A/TCI.tif"
geotiff = await GeoTIFF.open(path, store=store)
```
On the `GeoTIFF` instance you have metadata about the image, such as its affine transform, exposed as [Affine] objects, and Coordinate Reference System, exposed as [PyProj] [CRS objects][pyproj_CRS].

[Affine]: https://affine.readthedocs.io/en/latest/
[PyProj]: https://pyproj4.github.io/pyproj/stable/
[pyproj_CRS]: https://pyproj4.github.io/pyproj/stable/api/crs/crs.html

```py
geotiff.transform
# Affine(10.0, 0.0, 300000.0,
#        0.0, -10.0, 4100040.0)

geotiff.crs
# <Projected CRS: EPSG:32612>
# Name: WGS 84 / UTM zone 12N

geotiff.nodata
# 0.0
```

For a COG, you can access the overviews, or reduced resolution versions, of the image:

```py
# Overviews are ordered from finest to coarsest resolution
# In this case, access the second-coarsest resolution version of the image
overview = geotiff.overviews[-2]
```

Then we can read data from the image. This loads a 512-pixel square from the
upper-left corner of the selected overview.

```py
from async_geotiff import Window

window = Window(col_off=0, row_off=0, width=512, height=512)
array = await overview.read(window=window)
```

The `read` method returns an `Array` instance, which has fields including `data`, `shape`, `mask`, `transform`, and `crs`.

```py
# The affine transform of the loaded array
array.transform
# Affine(79.97086671522214, 0.0, 300000.0,
#        0.0, -79.97086671522214, 4100040.0)
```

The `.data` attribute is a 3D [NumPy] array, with rasterio axis ordering `(bands, height, width)`.

[NumPy]: https://numpy.org/

```py
array.data
# array([[[217, 245, 255, ...,   0,   0,   0],
#         [230, 244, 255, ...,   0,   0,   0],
#         [251, 254, 255, ...,   0,   0,   0],
#         ...,
#         [245, 239, 244, ...,   0,   0,   0],
#         [243, 236, 239, ...,   0,   0,   0],
#         [246, 245, 245, ...,   0,   0,   0]],

#        [[135, 170, 229, ...,   0,   0,   0],
#         [149, 180, 239, ...,   0,   0,   0],
#         [192, 234, 252, ...,   0,   0,   0],
#         ...,
#         [183, 174, 179, ...,   0,   0,   0],
#         [179, 171, 170, ...,   0,   0,   0],
#         [191, 182, 180, ...,   0,   0,   0]]],
#       shape=(3, 512, 512), dtype=uint8)
```

Or we can create a NumPy [MaskedArray][masked arrays] with the `as_masked` method:

[masked arrays]: https://numpy.org/doc/stable/reference/maskedarray.generic.html


```py
array.as_masked()
# masked_array(
#   data=[[[217, 245, 255, ..., --, --, --],
#          [230, 244, 255, ..., --, --, --],
#          [251, 254, 255, ..., --, --, --],
#          ...,
#          [245, 239, 244, ..., --, --, --],
#          [243, 236, 239, ..., --, --, --],
#          [246, 245, 245, ..., --, --, --]],

#         [[135, 170, 229, ..., --, --, --],
#          [149, 180, 239, ..., --, --, --],
#          [192, 234, 252, ..., --, --, --],
#          ...,
#          [183, 174, 179, ..., --, --, --],
#          [179, 171, 170, ..., --, --, --],
#          [191, 182, 180, ..., --, --, --]]],
#   mask=[[[False, False, False, ...,  True,  True,  True],
#          [False, False, False, ...,  True,  True,  True],
#          [False, False, False, ...,  True,  True,  True],
#          ...,
#          [False, False, False, ...,  True,  True,  True],
#          [False, False, False, ...,  True,  True,  True],
#          [False, False, False, ...,  True,  True,  True]]],
#   fill_value=0,
#   dtype=uint8)
```

This should integrate cleanly into existing tools. For example, we can plot using [`rasterio.plot.show`](https://rasterio.readthedocs.io/en/stable/api/rasterio.plot.html#rasterio.plot.show) (requires `matplotlib`):

```py
import rasterio.plot

rasterio.plot.show(array.data)
```

![](../../assets/sentinel_2_plot.jpg)

### TileMatrixSet integration with Morecantile

With the [Morecantile] integration, we can create a [TileMatrixSet] representation of the internal COG tiles.

[Morecantile]: https://github.com/developmentseed/morecantile
[TileMatrixSet]: https://docs.ogc.org/is/17-083r4/17-083r4.html

```py
from async_geotiff.tms import generate_tms

generate_tms(geotiff)
```

```json
{
  "crs": {"uri": "http://www.opengis.net/def/crs/EPSG/0/32612"},
  "boundingBox": {
    "lowerLeft": [300000.0, 3990240.0],
    "upperRight": [409800.0, 4100040.0],
    "crs": {"uri": "http://www.opengis.net/def/crs/EPSG/0/32612"}
  },
  "tileMatrices": [
    {
      "id": "0",
      "scaleDenominator": 570804.741110418,
      "cellSize": 159.82532751091702,
      "cornerOfOrigin": "topLeft",
      "pointOfOrigin": [300000.0, 4100040.0],
      "tileWidth": 1024,
      "tileHeight": 1024,
      "matrixWidth": 1,
      "matrixHeight": 1
    },
    {
      "id": "1",
      "scaleDenominator": 285610.23826865054,
      "cellSize": 79.97086671522214,
      "cornerOfOrigin": "topLeft",
      "pointOfOrigin": [300000.0, 4100040.0],
      "tileWidth": 1024,
      "tileHeight": 1024,
      "matrixWidth": 2,
      "matrixHeight": 2
    },
    ...
  ]
}
```

## Performance-focused

### Rust core

The underlying [Async-TIFF] library is written in [Rust], a fast, low-level language that compiles to native machine code, meaning it can be just as fast as any C or C++ library. Rust is memory efficient and its compiler automatically catches many memory bugs.

[Rust]: https://rust-lang.org/

### Multithreaded image decoding by default

With asynchronous I/O, it's important to ensure that no blocking tasks happen on the primary executor, because it means no other tasks can be responded to during that time.

Async-GeoTIFF splits up data fetching over the network and image decoding, ensuring any decoding is done in a Rust-based thread pool, leaving the executor responsive.

Async-GeoTIFF is thread-safe, though you shouldn't usually need to use it with a Python thread pool, as it's already using a Rust thread pool under the hood.

### Efficient memory usage

The underlying [Async-TIFF] library implements the Python [Buffer Protocol], ensuring that we can share array data between Rust and NumPy without copies.

[Buffer Protocol]: https://docs.python.org/3/c-api/buffer.html

## Read GeoTIFFs / COGs from any source

### Fast cloud storage access with Obstore

[Obstore] is a high-throughput Python interface to Amazon S3, Google Cloud Storage, Azure Storage, & other S3-compliant APIs, powered by a Rust core.

Async-GeoTIFF supports Obstore instances out of the box. Just create a store and pass it to [`GeoTIFF.open`][async_geotiff.GeoTIFF.open].

```py
from async_geotiff import GeoTIFF
from obstore.store import S3Store

store = S3Store("sentinel-cogs", region="us-west-2", skip_signature=True)
path = "sentinel-s2-l2a-cogs/12/S/UF/2022/6/S2B_12SUF_20220609_0_L2A/TCI.tif"
geotiff = await GeoTIFF.open(path, store=store)
```

### Generic backend support with obspec

Async-GeoTIFF supports reading from arbitrary [Obspec] backends. [Obspec] defines a set of Python [protocols][Protocol] for generically accessing data from object storage-like resources.

This means you can easily read GeoTIFF data from **any source**, as long as you define two simple methods:

```py
class MyBackend:
    async def get_range_async(
        self,
        path: str,
        *,
        start: int,
        end: int | None = None,
        length: int | None = None,
    ) -> Buffer:
        """Return the bytes in the given byte range."""
        ...

    async def get_ranges_async(
        self,
        path: str,
        *,
        starts: Sequence[int],
        ends: Sequence[int] | None = None,
        lengths: Sequence[int] | None = None,
    ) -> Sequence[Buffer]:
        """Return the bytes in the given byte ranges."""
        ...
```

Then just pass an instance of your backend into [`GeoTIFF.open`][async_geotiff.GeoTIFF.open].

```py
from async_geotiff import GeoTIFF
from obstore.store import S3Store

backend = MyBackend()
geotiff = await GeoTIFF.open("path/in/backend.tif", store=backend)
```

Read the [obspec release post] for more information.

[obspec release post]: https://developmentseed.org/obspec/latest/blog/2025/06/25/introducing-obspec-a-python-protocol-for-interfacing-with-object-storage/

### More tractable data caching

GDAL [provides a block cache](https://gdal.org/en/stable/development/rfc/rfc26_blockcache.html) per file handle opened. The block cache persists chunks of bytes in memory that have already been read over the network, so that if a later request requires some of those same bytes, a smaller network request to the source is required.

However GDAL's block cache is entirely a black box at the Python level. Rasterio is unable to access it, and the end user is unable to see how much data the cache is using. Similarly, the Python user can't change core cache behavior, aside from a few [configuration settings][gdal_config_settings].

[gdal_config_settings]: https://gdal.org/en/stable/user/configoptions.html

Through Async-GeoTIFF's [Obspec] integration, we expect to have composable caching layers available to any tool relying on Obspec, including Async-GeoTIFF. We're currently experimenting with ideas in the [`obspec-utils`][obspec-utils] repository, but the basic idea is


```py
from __future__ import annotations
from typing_extensions import Buffer
from typing import Protocol
from obspec import GetRangeAsync, GetRangesAsync

class FetchClientProtocol(GetRange, GetRangesAsync, Protocol):
    """A new type wrapper for classes that implement both `GetRange` and
    `GetRangesAsync`.
    """
    ...

class SimpleCache(GetRange, GetRangesAsync):
    """A simple cache for range requests that never evicts data."""

    def __init__(self, client: GetRange):
        self.client = client
        self.cache: dict[tuple[str, int, int | None, int | None], Buffer] = {}

    async def get_range_async(
        self,
        path: str,
        *,
        start: int,
        end: int | None = None,
        length: int | None = None,
    ) -> Buffer:
        cache_key = (path, start, end, length)
        if cache_key in self.cache:
            return self.cache[cache_key]

        response = await self.client.get_range_async(
            path,
            start=start,
            end=end,
            length=length,
        )
        self.cache[cache_key] = response
        return response

    async def get_ranges_async(
        self,
        path: str,
        *,
        starts: Sequence[int],
        ends: Sequence[int] | None = None,
        lengths: Sequence[int] | None = None,
    ) -> Sequence[Buffer]:
        # This is meant as pseudocode; a real implementation would check each
        # range against the cache and merge ranges if possible, so as few
        # requests as possible are made to the actual source
        results = []
        for (start, end) in zip(starts, ends):
            results.append(self.get_range_async(path=path, start=start, end=end))
        return results
```

Now a user could easily choose to add the caching layer as a middleware:

```py
from obstore.store import S3Store
from async_geotiff import GeoTIFF

store = S3Store("bucket")
caching_wrapper = SimpleCache(store)

geotiff = await GeoTIFF.open("path/to/image.tif", store=caching_wrapper)
```

The user has full access to the `caching_wrapper` instance as well, if they want to inspect how much memory it's using or log what requests are made.

Read the [obspec release post] for more information.

[Obstore]: https://developmentseed.org/obstore/latest/
[Obspec]: https://developmentseed.org/obspec/latest/
[obspec-utils]: https://github.com/virtual-zarr/obspec-utils
[Protocol]: https://typing.python.org/en/latest/spec/protocol.html

## Full type hinting

The entire Async-GeoTIFF API is type-hinted as well as possible, leading to effective IDE integration.

## Growing test suite

We recently created [geotiff-test-data], a repository to hold various sorts of GeoTIFF test files. This repo can then be used as a submodule to provide test fixtures for various repositories like Async-GeoTIFF and [deck.gl-raster] without growing the disk size of the primary Git repository.

The majority of these test files are [written using Rasterio](https://github.com/developmentseed/geotiff-test-data/blob/7d1cecbc91d909a3e2fa7d554b904831a5378d3c/rasterio_generated/write_utils.py#L19)

[geotiff-test-data]: https://github.com/developmentseed/geotiff-test-data
[deck.gl-raster]: https://github.com/developmentseed/deck.gl-raster

## Future work

### `rio-tiler` integration

[`rio-tiler`] is a foundational library for accessing raster data for tiled web maps. And [Titiler], a Development Seed project for dynamic server-side raster tile generation, is built largely on the backs of `rio-tiler`. The first step of integrating Async-GeoTIFF into the Titiler ecosystem will be adding support to `rio-tiler`.

[`rio-tiler`]: https://github.com/cogeotiff/rio-tiler

### Better API for handling photometric interpretations

Currently Async-GeoTIFF doesn't decode data out of RGB color spaces like YCbCr, which doesn't match Rasterio's handling. We may add an API like `Array.to_rgb` to offer explicit conversion to an RGB color space.

### More compression support

We should support additional compressions like [LERC](https://github.com/Esri/lerc) and JPEG XL.
