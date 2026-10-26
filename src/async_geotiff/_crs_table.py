"""The GeoTIFF coordinate-transformation method table.

`data/geotiff-ct-methods.json` says, for every `ProjCoordTransGeoKey` code,
which PROJ/EPSG method it means and how each parameter is read from GeoKeys.
It is shared with other GeoTIFF readers through the geotiff-test-data
repository, which documents its schema in `crs/README.md`; this module only
loads it into typed records.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Literal

ParameterKind = Literal["angular", "linear", "scale", "azimuth"]

DEFAULT_AXES: tuple[str, str] = ("east", "north")


@dataclass(frozen=True)
class Parameter:
    """One projection parameter and the GeoKeys it is read from."""

    name: str
    """PROJ/EPSG parameter name."""
    epsg: int | None
    """EPSG parameter code, or None for PROJ-only methods."""
    proj: str
    """PROJ string key."""
    kind: ParameterKind
    """Unit class: angular and linear values are scaled by the file's units."""
    keys: tuple[str, ...]
    """GeoKey names to try in order (spec names without the `GeoKey` suffix)."""
    default: float


@dataclass(frozen=True)
class Variant:
    """One way a CT code maps to a method, chosen by its `when` rule."""

    when: dict | None
    """Rule selecting this variant; None for the default variant."""
    method_name: str | None
    method_epsg: int | None
    proj: str | None
    """PROJ projection name."""
    axes: tuple[str, str]
    """Projected axis directions."""
    parameters: tuple[Parameter, ...]
    unrepresentable: str | None
    """Set when PROJ has no operation for this case."""
    note: str | None


@dataclass(frozen=True)
class Method:
    """A `ProjCoordTransGeoKey` code and its variants."""

    code: int
    ct_name: str
    unsupported: str | None
    """Set when GDAL cannot read this code either."""
    variants: tuple[Variant, ...]

    @property
    def all_parameters(self) -> tuple[Parameter, ...]:
        """Every parameter any variant reads, first occurrence by name."""
        seen: dict[str, Parameter] = {}
        for variant in self.variants:
            for parameter in variant.parameters:
                seen.setdefault(parameter.name, parameter)
        return tuple(seen.values())


def _parameter(raw: dict) -> Parameter:
    return Parameter(
        name=raw["name"],
        epsg=raw["epsg"],
        proj=raw["proj"],
        kind=raw["kind"],
        keys=tuple(raw["keys"]),
        default=float(raw["default"]),
    )


def _variant(raw: dict) -> Variant:
    method = raw.get("method")
    return Variant(
        when=raw.get("when"),
        method_name=method["name"] if method else None,
        method_epsg=method["epsg"] if method else None,
        proj=method["proj"] if method else None,
        axes=tuple(raw.get("axes", DEFAULT_AXES)),  # type: ignore[arg-type]
        parameters=tuple(_parameter(p) for p in raw.get("parameters", [])),
        unrepresentable=raw.get("unrepresentable"),
        note=raw.get("note"),
    )


def _method(code: str, raw: dict) -> Method:
    return Method(
        code=int(code),
        ct_name=raw["ct_name"],
        unsupported=raw.get("unsupported"),
        variants=tuple(_variant(v) for v in raw.get("variants", [])),
    )


@lru_cache(maxsize=1)
def load_table() -> dict[int, Method]:
    """Load the vendored table, keyed by CT code."""
    text = files("async_geotiff.data").joinpath("geotiff-ct-methods.json").read_text()
    raw = json.loads(text)
    return {int(code): _method(code, method) for code, method in raw["methods"].items()}
