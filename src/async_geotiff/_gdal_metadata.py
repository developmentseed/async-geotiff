from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import defusedxml.ElementTree as ET  # noqa: N817


@dataclass
class BandStatistics:
    maximum: float | None = None
    minimum: float | None = None
    mean: float | None = None
    stddev: float | None = None
    valid_percent: float | None = None


@dataclass
class GDALMetadata:
    overview_resampling_alg: str | None = None
    band_statistics: dict[int, BandStatistics] = field(default_factory=dict)


def parse_gdal_metadata(gdal_metadata: str | None) -> GDALMetadata | None:
    if gdal_metadata is None:
        return None

    root = ET.fromstring(gdal_metadata)

    if root.tag != "GDALMetadata":
        raise ValueError("Not a GDALMetadata XML block")

    overview_resampling_alg = None
    band_statistics: dict[int, BandStatistics] = defaultdict(BandStatistics)

    for elem in root.findall("Item"):
        name = elem.attrib.get("name")
        sample = elem.attrib.get("sample")
        text = elem.text or ""
        match name:
            case "OVR_RESAMPLING_ALG":
                overview_resampling_alg = text
            case "STATISTICS_MAXIMUM":
                assert sample is not None  # noqa: S101
                band_statistics[int(sample)].maximum = float(text)
            case "STATISTICS_MEAN":
                assert sample is not None  # noqa: S101
                band_statistics[int(sample)].mean = float(text)
            case "STATISTICS_MINIMUM":
                assert sample is not None  # noqa: S101
                band_statistics[int(sample)].minimum = float(text)
            case "STATISTICS_STDDEV":
                assert sample is not None  # noqa: S101
                band_statistics[int(sample)].stddev = float(text)
            case "STATISTICS_VALID_PERCENT":
                assert sample is not None  # noqa: S101
                band_statistics[int(sample)].valid_percent = float(text)

    return GDALMetadata(
        band_statistics=band_statistics,
        overview_resampling_alg=overview_resampling_alg,
    )
