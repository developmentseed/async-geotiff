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
            if geotiff.count <= 2:
                raise NotImplementedError(
                    "RGB photometric interpretation with fewer than 3 bands "
                    "is not supported.",
                )

            if geotiff.count == 3:
                return (
                    ColorInterp.RED,
                    ColorInterp.GREEN,
                    ColorInterp.BLUE,
                )

            if geotiff.count >= 4:
                # Color interpretations for any extra samples
                # Sample = 2 means alpha, otherwise we mark it as undefined
                # https://web.archive.org/web/20240329145321/https://www.awaresystems.be/imaging/tiff/tifftags/extrasamples.html
                extra_colorinterps = [
                    ColorInterp.ALPHA if sample == 2 else ColorInterp.UNDEFINED
                    for sample in primary_ifd.extra_samples or []
                ]
                return (
                    ColorInterp.RED,
                    ColorInterp.GREEN,
                    ColorInterp.BLUE,
                    *extra_colorinterps,
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
