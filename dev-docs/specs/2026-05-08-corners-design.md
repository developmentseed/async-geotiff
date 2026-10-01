# `corners` property — design

Resolves [issue #98](https://github.com/developmentseed/async-geotiff/issues/98).

## Motivation

`GeoTIFF`, `Overview`, and `RasterArray` expose a `bounds` property that returns the axis-aligned bounding box in CRS units. For images with rotated affine transforms (non-zero off-diagonal terms in the affine matrix), the axis-aligned bounding box is strictly larger than the true image footprint and loses the rotation information.

Users who need the actual four corners — for visualizations such as deck.gl-raster's `projectedCorners`, for emitting GeoJSON polygons, or simply for plotting an image's footprint — currently have to derive the corners themselves from `transform`, `width`, and `height`.

## API

A new `@property` named `corners` on `TransformMixin`, automatically inherited by `GeoTIFF`, `Overview`, and `RasterArray`.

### Signature

```python
@property
def corners(
    self: HasTransform,
) -> tuple[
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
]:
    ...
```

### Returned sequence

The four corners are derived by projecting these pixel-space coordinates through the affine transform, in this fixed order:

```
(0, 0) -> (0, height) -> (width, height) -> (width, 0)
```

For a canonical north-up GeoTIFF (top-left origin, negative y-resolution), this maps to (UL, LL, LR, UR) in geographic space, producing a counter-clockwise ring that is suitable for direct use as a GeoJSON polygon's exterior ring (RFC 7946).

For bottom-up rasters (positive y-resolution) the same pixel-space sequence produces clockwise geographic winding. This is documented in the docstring; the property does **not** adapt the order to enforce CCW.

### Naming rationale

The repo already uses `projected_*` privately in [_crs.py](../../src/async_geotiff/_crs.py) to refer to projected (vs geographic) coordinate reference systems (`_projected_projection`, `_projected_cs`, `gkd.projected_type`). Using `projected_corners` would overload that meaning. Since the existing `bounds` property already returns CRS-unit values without a prefix, `corners` is the consistent name.

## Implementation

The property lives in [src/async_geotiff/_transform.py](../../src/async_geotiff/_transform.py) alongside `bounds`, `index`, `res`, and `xy`. It uses the same `cast("tuple[float, float]", tr * (...))` pattern that `bounds` already uses for the affine v3 typing workaround tracked in [issue #123](https://github.com/developmentseed/async-geotiff/issues/123).

```python
@property
def corners(
    self: HasTransform,
) -> tuple[
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
]:
    tr = self.transform
    width = self.width
    height = self.height

    c0 = cast("tuple[float, float]", tr * (0, 0))
    c1 = cast("tuple[float, float]", tr * (0, height))
    c2 = cast("tuple[float, float]", tr * (width, height))
    c3 = cast("tuple[float, float]", tr * (width, 0))
    return (c0, c1, c2, c3)
```

`TransformMixin` is already used by `GeoTIFF` ([_geotiff.py:48](../../src/async_geotiff/_geotiff.py#L48)), `Overview` ([_overview.py:21](../../src/async_geotiff/_overview.py#L21)), and `RasterArray` ([_array.py:22](../../src/async_geotiff/_array.py#L22)). Adding the property to the mixin gives all three classes the new attribute with no per-class wiring.

### `PixelIsPoint` interaction

`create_transform` ([_transform.py:36-37](../../src/async_geotiff/_transform.py#L36-L37)) already pre-applies a half-pixel translation to the affine when `raster_type == RASTER_TYPE_PIXEL_IS_POINT`. Because `corners` derives from `self.transform`, the returned values reflect this offset and describe the full pixel-area extent of the image, consistent with how `bounds` is computed.

## Testing

Three tests cover correctness:

1. **Non-rotated parity (parametrized).** In [tests/test_geotiff.py](../../tests/test_geotiff.py) and [tests/test_overview.py](../../tests/test_overview.py), iterate over the existing `ALL_TEST_IMAGES` fixtures and assert the four corners equal those derived from `rasterio_ds.bounds`:
   - corner 0 = (left, top)
   - corner 1 = (left, bottom)
   - corner 2 = (right, bottom)
   - corner 3 = (right, top)

2. **Rotated transform (synthetic).** `RasterArray` is a frozen dataclass requiring a real `GeoTIFF` reference, and no existing fixture has a rotated transform, so the test exercises `TransformMixin` directly via a small in-test stub:

   ```python
   @dataclass
   class _Stub(TransformMixin):
       transform: Affine
       width: int
       height: int
   ```

   Build a stub with a rotated `Affine` (e.g., 30° rotation, finite size) and assert:
   - The four corners match the expected math.
   - The corners differ from the values implied by `bounds` (the axis-aligned bounding box, which will be strictly larger).

3. **`PixelIsPoint` half-pixel offset.** If any existing fixture has `raster_type=2`, assert the corners reflect the half-pixel shift. If no such fixture exists in `ALL_TEST_IMAGES`, this test is omitted; the synthetic test above plus the existing transform-construction tests already cover the relevant arithmetic.

## Documentation

- The new property gets a Google-style docstring covering: what it returns, the fixed pixel-space sequence, the canonical-vs-bottom-up winding caveat, and the relationship to `bounds`.
- Add a single line to `CHANGELOG.md` under the Unreleased → Added section: ``Added `corners` property on `GeoTIFF`, `Overview`, and `RasterArray` returning the four image corners in CRS units (#98).``
- No new mkdocs page is needed; the property surfaces automatically in the existing API references for the three classes.

## Out of scope

- **GeoJSON helper.** No `to_geojson()` or `to_polygon()` method. Users who need a GeoJSON ring can construct it from `corners` plus a closing copy of the first corner.
- **CRS reprojection.** Corners are emitted in the source CRS, identical to `bounds`.
- **Method form.** No `get_corners()`; property form matches the `bounds` precedent.
- **Adaptive winding.** The property does not branch on the transform's determinant to enforce CCW for unusual (bottom-up) transforms. Users with such rasters can reverse the sequence themselves.
