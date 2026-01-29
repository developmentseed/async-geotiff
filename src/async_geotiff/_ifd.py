from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from async_tiff import ImageFileDirectory


@dataclass(frozen=True, kw_only=True, repr=False)
class IFDReference:
    """A reference to an Image File Directory (IFD) in a TIFF file."""

    index: int
    """The positional index of the IFD in the TIFF file."""

    ifd: ImageFileDirectory
    """The IFD object itself."""
