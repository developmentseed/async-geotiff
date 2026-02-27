from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import defusedxml.ElementTree as ET  # noqa: N817


@dataclass
class BandStatistics:
    """Statistics for a single band in a GeoTIFF."""

    max: float | None = None
    """The maximum pixel value in the band."""
    min: float | None = None
    """The minimum pixel value in the band."""
    mean: float | None = None
    """The mean pixel value in the band."""
    std: float | None = None
    """The standard deviation of the pixel values in the band."""
    valid_percent: float | None = None
    """The percentage of valid pixels in the band."""


@dataclass(frozen=True)
class GDALMetadata:
    """Metadata extracted from the GDALMetadata TIFF tag."""

    band_statistics: dict[int, BandStatistics] = field(default_factory=dict)
    """A mapping of band index to statistics for that band.

    This band index is **1-based**.
    """


def parse_gdal_metadata(gdal_metadata: str | None) -> GDALMetadata | None:
    if gdal_metadata is None:
        return None

    root = ET.fromstring(gdal_metadata)

    if root.tag != "GDALMetadata":
        raise ValueError("Not a GDALMetadata XML block")

    band_statistics: defaultdict[int, BandStatistics] = defaultdict(BandStatistics)

    for elem in root.findall("Item"):
        name = elem.attrib.get("name")
        sample = elem.attrib.get("sample")
        text = elem.text or ""
        match name:
            # Add 1 to get a 1-based band index to match GDAL.
            case "STATISTICS_MAXIMUM":
                assert sample is not None  # noqa: S101
                band_statistics[int(sample) + 1].max = float(text)
            case "STATISTICS_MEAN":
                assert sample is not None  # noqa: S101
                band_statistics[int(sample) + 1].mean = float(text)
            case "STATISTICS_MINIMUM":
                assert sample is not None  # noqa: S101
                band_statistics[int(sample) + 1].min = float(text)
            case "STATISTICS_STDDEV":
                assert sample is not None  # noqa: S101
                band_statistics[int(sample) + 1].std = float(text)
            case "STATISTICS_VALID_PERCENT":
                assert sample is not None  # noqa: S101
                band_statistics[int(sample) + 1].valid_percent = float(text)

    return GDALMetadata(band_statistics=dict(band_statistics))
