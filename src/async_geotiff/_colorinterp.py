# ruff: noqa: PLR2004

from __future__ import annotations

from typing import TYPE_CHECKING

from async_tiff.enums import ExtraSamples

from async_geotiff.enums import ColorInterp, PhotometricInterpretation

if TYPE_CHECKING:
    from collections.abc import Sequence


def infer_color_interpretation(  # noqa: PLR0911
    *,
    count: int,
    photometric: PhotometricInterpretation | None,
    extra_samples: Sequence[ExtraSamples],
) -> tuple[ColorInterp, ...]:
    """Infer colorinterp array based on GeoTIFF metadata."""
    match photometric:
        case None:
            return (ColorInterp.UNDEFINED,) * count
        case PhotometricInterpretation.BLACK_IS_ZERO:
            return (ColorInterp.GRAY,) + (ColorInterp.UNDEFINED,) * (count - 1)
        case PhotometricInterpretation.RGB:
            if count <= 2:
                raise NotImplementedError(
                    "RGB photometric interpretation with fewer than 3 bands "
                    "is not supported.",
                )

            if count == 3:
                return (
                    ColorInterp.RED,
                    ColorInterp.GREEN,
                    ColorInterp.BLUE,
                )

            if count >= 4:
                # Color interpretations for any extra samples
                # Sample = 2 means alpha, otherwise we mark it as undefined
                # https://web.archive.org/web/20240329145321/https://www.awaresystems.be/imaging/tiff/tifftags/extrasamples.html
                extra_colorinterps = [
                    ColorInterp.ALPHA
                    if sample == ExtraSamples.UnassociatedAlpha
                    else ColorInterp.UNDEFINED
                    for sample in extra_samples or []
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
