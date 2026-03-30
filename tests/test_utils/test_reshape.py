from __future__ import annotations

import numpy as np

from async_geotiff.utils import reshape_as_image


def test_reshape_as_image() -> None:
    # Test with a regular NumPy array
    arr = np.ones((3, 4, 5))  # (bands, rows, columns)
    reshaped = reshape_as_image(arr)
    assert reshaped.shape == (4, 5, 3)  # (rows, columns, bands)

    # Test with a masked array
    masked_arr = np.ma.masked_array(arr)
    reshaped_masked = reshape_as_image(masked_arr)
    assert reshaped_masked.shape == (4, 5, 3)  # (rows, columns, bands)
    assert isinstance(reshaped_masked, np.ma.MaskedArray)
