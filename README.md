# async-geotiff

Async GeoTIFF and [Cloud-Optimized GeoTIFF][cogeo] (COG) reader for Python, wrapping [`async-tiff`][async-tiff].

[async-tiff]: https://github.com/developmentseed/async-tiff
[cogeo]: https://cogeo.org/

## Project Goals:

- Support only for GeoTIFF and Cloud-Optimized GeoTIFF (COG) formats
- Support for reading only, no writing support
- Full type hinting.
- API similar to rasterio where possible.
    - We won't support the full rasterio API, but we'll try to when it's possible to implement rasterio APIs with straightforward maintenance requirements.
    - For methods where we do intentionally try to match with rasterio, the tests should match against rasterio.
- Initially, we'll try to support a core set of GeoTIFF formats. Obscure GeoTIFF files may not be supported.

## References

- aiocogeo: https://github.com/geospatial-jeff/aiocogeo
