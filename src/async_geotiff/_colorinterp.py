# ruff: noqa: PLR2004

from __future__ import annotations

from typing import TYPE_CHECKING

from .enums import ColorInterp, PhotometricInterpretation

if TYPE_CHECKING:
    from async_geotiff import GeoTIFF


def infer_color_interpretation(geotiff: GeoTIFF) -> tuple[ColorInterp, ...]:
    primary_ifd = geotiff._primary_ifd  # noqa: SLF001

    match geotiff.photometric:
        case PhotometricInterpretation.BLACK_IS_ZERO:
            return (ColorInterp.GRAY,) * geotiff.count
        case PhotometricInterpretation.RGB:
            if geotiff.count == 3:
                return (
                    ColorInterp.RED,
                    ColorInterp.GREEN,
                    ColorInterp.BLUE,
                )

            if geotiff.count == 4:
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
        case PhotometricInterpretation.CMYK:
            return (
                ColorInterp.CYAN,
                ColorInterp.MAGENTA,
                ColorInterp.YELLOW,
                ColorInterp.BLACK,
            )
        case PhotometricInterpretation.YCBCR:
            return (
                ColorInterp.Y,
                ColorInterp.Cb,
                ColorInterp.Cr,
            )

    raise NotImplementedError
