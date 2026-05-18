# Changelog

## 0.5.1 - 2026-05-18

* feat: Add new `Store` protocol defined in this package by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/161
* docs: Don't document private base classes by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/162

**Full Changelog**: https://github.com/developmentseed/async-geotiff/compare/v0.5.0...v0.5.1

## 0.5.0 - 2026-05-08

### New Features

* feat!: Allow public access to underlying IFD by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/153
* feat: Add `shape` property to overview by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/154

### Other

* chore: allow uv up to 0.12.0 by @autra in https://github.com/developmentseed/async-geotiff/pull/136
* docs: Add `async_geotiff.utils` to docs website by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/140
* ci: add Dependabot for GitHub Actions version updates by @lhoupert in https://github.com/developmentseed/async-geotiff/pull/143
* ci: Use github app token for conventional commit labeling by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/150
* test: fix fixture dir discovery by @autra in https://github.com/developmentseed/async-geotiff/pull/137
* ci: Pin third party actions to SHA hashes by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/155
* docs: Improve docstring of GeoTIFF.open by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/157

### New Contributors

* @lhoupert made their first contribution in https://github.com/developmentseed/async-geotiff/pull/143
* @dependabot[bot] made their first contribution in https://github.com/developmentseed/async-geotiff/pull/145

**Full Changelog**: https://github.com/developmentseed/async-geotiff/compare/v0.4.0...v0.5.0

## 0.4.0 - 2026-03-30

### Breaking Changes

* refactor!: Rename `Array` to `RasterArray` by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/131

### Features

* feat: override color interpretation based on GDAL metadata by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/126
* feat: Add utils.reshape_as_image by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/132

### Fixes

* fix: Match rasterio behavior with a flipped y coordinate by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/124
* fix: Add new test with custom CRS by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/125


### Other

* ci: Set up trusted publishing by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/128
* chore: put types-defusedxml in dev dependencies by @autra in https://github.com/developmentseed/async-geotiff/pull/133

### New Contributors

* @autra made their first contribution in https://github.com/developmentseed/async-geotiff/pull/133

**Full Changelog**: https://github.com/developmentseed/async-geotiff/compare/v0.3.0...v0.4.0

## 0.3.0 - 2026-03-03

### What's Changed

* feat: Add `.res` property to Overview by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/90
* feat: Support for non-boundless tile reads by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/94
* feat: `tile_count` attribute by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/97
* feat: Add `GeoTIFF.colorinterp` by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/105
* fix: Support reading a single-tile image by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/106
* fix: Fix generated affine transform (by half pixel offset) when pixel is defined as `POINT` by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/107
* feat: Expose band statistics by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/108
* feat: Expose `scales` and `offsets` to match rasterio by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/110
* feat: add `block_shapes` property by @gakarak in https://github.com/developmentseed/async-geotiff/pull/111
* fix: Fix `Array.as_masked` for images with an internal mask by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/112
* fix: Check alpha band in `Array.as_masked` by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/114
* chore: Bump async-tiff dependency to 0.7 by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/117
* feat: Add `shape` attribute to our `Array` class by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/118
* docs: Update docs to describe request coalescing by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/119

### New Contributors

* @gakarak made their first contribution in https://github.com/developmentseed/async-geotiff/pull/111

**Full Changelog**: https://github.com/developmentseed/async-geotiff/compare/v0.2.0...v0.3.0

## 0.2.0 - 2026-02-05

### New Features

* feat: Support for band-interleaved data by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/80
* feat: Add LERC decompression support by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/79

### Fixes

* fix: Fix computation of `bounds` and `res` for rotated data by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/82

### Documentation

* docs: Add `Tile` to the API docs by @kylebarron in https://github.com/developmentseed/async-geotiff/pull/74

**Full Changelog**: https://github.com/developmentseed/async-geotiff/compare/v0.1.0...v0.2.0

## 0.1.0 - 2026-02-03

**Read the release post**: https://developmentseed.org/async-geotiff/latest/blog/2026/02/03/introducing-async-geotiff/

- Initial release of async-geotiff.
