"""Transformations to RGB for GeoTIFF photometric interpretations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from async_tiff.enums import PhotometricInterpretation

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from async_geotiff.colormap import Colormap


def convert_to_rgb(  # noqa: PLR0911
    data: NDArray,
    *,
    photometric_interpretation: PhotometricInterpretation,
    colormap: Colormap | None = None,
) -> NDArray:
    """Convert GeoTIFF data to RGB format.

    Returns array with shape (3, height, width) containing RGB value.
    """
    if photometric_interpretation == PhotometricInterpretation.RGB:
        return data

    if photometric_interpretation == PhotometricInterpretation.RGBPalette:
        if colormap is None:
            raise ValueError(
                "Colormap should be present when photometric interpretation==Palette.",
            )

        cmap_array = colormap.as_array()
        return cmap_array[data[0]]

    if photometric_interpretation == PhotometricInterpretation.BlackIsZero:
        return np.repeat(data, 3, axis=0)

    if photometric_interpretation == PhotometricInterpretation.WhiteIsZero:
        # Invert grayscale to RGB conversion
        # TODO: configurable max value?
        inverted_data = 255 - data
        return np.repeat(inverted_data, 3, axis=0)

    if photometric_interpretation == PhotometricInterpretation.CMYK:
        return _from_cmyk(data)

    if photometric_interpretation == PhotometricInterpretation.YCbCr:
        return _from_ycbcr(data)

    if photometric_interpretation == PhotometricInterpretation.CIELab:
        return _from_cielab(data)

    raise NotImplementedError(
        f"Conversion for photometric interpretation "
        f"{photometric_interpretation} is not implemented.",
    )


# https://github.com/geotiffjs/geotiff.js/blob/903125bdf8ebe327c4a4353f1e0311302452b9e9/src/rgb.ts#L52-L66
def _from_cmyk(data: NDArray) -> NDArray:
    """Convert CMYK to RGB.

    Args:
        data: Array with shape (4, height, width) containing CMYK values.

    Returns:
        Array with shape (3, height, width) containing RGB values.

    """
    c = data[0].astype(np.float32)
    m = data[1].astype(np.float32)
    y = data[2].astype(np.float32)
    k = data[3].astype(np.float32)

    r = 255 * ((255 - c) / 256) * ((255 - k) / 256)
    g = 255 * ((255 - m) / 256) * ((255 - k) / 256)
    b = 255 * ((255 - y) / 256) * ((255 - k) / 256)

    return np.stack([r, g, b], axis=0).astype(np.uint8)


# https://github.com/geotiffjs/geotiff.js/blob/903125bdf8ebe327c4a4353f1e0311302452b9e9/src/rgb.ts#L68-L83
def _from_ycbcr(data: NDArray) -> NDArray:
    """Convert YCbCr to RGB.

    Args:
        data: Array with shape (3, height, width) containing YCbCr values.

    Returns:
        Array with shape (3, height, width) containing RGB values.

    """
    y = data[0].astype(np.float32)
    cb = data[1].astype(np.float32)
    cr = data[2].astype(np.float32)

    r = y + 1.402 * (cr - 128)
    g = y - 0.34414 * (cb - 128) - 0.71414 * (cr - 128)
    b = y + 1.772 * (cb - 128)

    return np.clip(np.stack([r, g, b], axis=0), 0, 255).astype(np.uint8)


# CIELab reference white point (D65 illuminant)
_XN = 0.95047
_YN = 1.0
_ZN = 1.08883


# CIELab conversion thresholds
_LAB_EPSILON = 0.008856
_LINEAR_RGB_THRESHOLD = 0.0031308


# https://github.com/geotiffjs/geotiff.js/blob/903125bdf8ebe327c4a4353f1e0311302452b9e9/src/rgb.ts#L91-L124
def _from_cielab(data: NDArray) -> NDArray:
    """Convert CIELab to RGB.

    Based on https://github.com/antimatter15/rgb-lab/blob/master/color.js

    Args:
        data: Array with shape (3, height, width) containing CIELab values.
              L is uint8 [0-255], a and b are int8 [-128, 127] stored as uint8.

    Returns:
        Array with shape (3, height, width) containing RGB values.

    """
    L = data[0].astype(np.float32)  # noqa: N806
    # Convert uint8 to signed int8 interpretation
    a_ = data[1].astype(np.int8).astype(np.float32)
    b_ = data[2].astype(np.int8).astype(np.float32)

    y = (L + 16) / 116
    x = a_ / 500 + y
    z = y - b_ / 200

    # Apply inverse f function
    x3 = x * x * x
    y3 = y * y * y
    z3 = z * z * z

    x = np.where(x3 > _LAB_EPSILON, x3, (x - 16 / 116) / 7.787)
    y = np.where(y3 > _LAB_EPSILON, y3, (y - 16 / 116) / 7.787)
    z = np.where(z3 > _LAB_EPSILON, z3, (z - 16 / 116) / 7.787)

    x = _XN * x
    y = _YN * y
    z = _ZN * z

    # XYZ to RGB (sRGB with D65 white point)
    r = x * 3.2406 + y * -1.5372 + z * -0.4986
    g = x * -0.9689 + y * 1.8758 + z * 0.0415
    b = x * 0.0557 + y * -0.204 + z * 1.057

    # Apply gamma correction
    r = np.where(
        r > _LINEAR_RGB_THRESHOLD,
        1.055 * np.power(r, 1 / 2.4) - 0.055,
        12.92 * r,
    )
    g = np.where(
        g > _LINEAR_RGB_THRESHOLD,
        1.055 * np.power(g, 1 / 2.4) - 0.055,
        12.92 * g,
    )
    b = np.where(
        b > _LINEAR_RGB_THRESHOLD,
        1.055 * np.power(b, 1 / 2.4) - 0.055,
        12.92 * b,
    )

    r = np.clip(r, 0, 1) * 255
    g = np.clip(g, 0, 1) * 255
    b = np.clip(b, 0, 1) * 255

    return np.stack([r, g, b], axis=0).astype(np.uint8)
