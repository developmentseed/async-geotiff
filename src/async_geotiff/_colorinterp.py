# ruff: noqa: PLR2004

from __future__ import annotations

from typing import TYPE_CHECKING

from .enums import ColorInterp, PhotometricInterpretation

if TYPE_CHECKING:
    from async_geotiff import GeoTIFF


def infer_color_interpretation(geotiff: GeoTIFF) -> tuple[ColorInterp, ...]:
    primary_ifd = geotiff._primary_ifd  # noqa: SLF001

    match geotiff.photometric:
        case PhotometricInterpretation.RGB:
            if len(primary_ifd.sample_format) == 3:
                return (
                    ColorInterp.RED,
                    ColorInterp.GREEN,
                    ColorInterp.BLUE,
                )

            if len(primary_ifd.sample_format) == 4:
                if primary_ifd.extra_samples == [2]:
                    return (
                        ColorInterp.RED,
                        ColorInterp.GREEN,
                        ColorInterp.BLUE,
                        ColorInterp.ALPHA,
                    )

                raise NotImplementedError(
                    "Only RGBA with associated alpha (extra_samples=2) "
                    "is supported for RGB photometric interpretation.",
                )

        case PhotometricInterpretation.RGBPALETTE:
            return (ColorInterp.PALETTE,)

    raise NotImplementedError
