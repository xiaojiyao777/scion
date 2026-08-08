"""Typed code-edit protocol helpers for proposal-stage patch outputs."""

from .normalization import (
    PatchEditProtocolError,
    normalize_patch_typed_edits,
    source_digest_for_content,
)

__all__ = [
    "PatchEditProtocolError",
    "normalize_patch_typed_edits",
    "source_digest_for_content",
]
