"""Typed code-edit protocol helpers for proposal-stage patch outputs."""

from .normalization import (
    PatchEditProtocolError,
    build_patch_edit_source_manifest,
    normalize_patch_typed_edits,
    source_digest_for_content,
)

__all__ = [
    "PatchEditProtocolError",
    "build_patch_edit_source_manifest",
    "normalize_patch_typed_edits",
    "source_digest_for_content",
]
