"""Typed code-edit protocol helpers for proposal-stage patch outputs."""

from .normalization import (
    PatchEditProtocolError,
    normalize_patch_typed_edits,
)

__all__ = [
    "PatchEditProtocolError",
    "normalize_patch_typed_edits",
]
