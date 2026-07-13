"""Compatibility facade for proposal schema models, schema dicts, and tools."""

from __future__ import annotations

from .hypothesis import (
    HYPOTHESIS_PROMPT_TEMPLATE,
    HYPOTHESIS_PROPOSAL_SCHEMA,
    HypothesisProposalInput,
)
from .normalization import (
    normalize_patch_output_with_repair_attribution,
)
from .patch import (
    PATCH_PROPOSAL_SCHEMA,
    PatchEditIntent,
    PatchFileChangeInput,
    PatchProposalInput,
    PatchSchemaPreflightError,
    preflight_patch_exact_replace_shape,
)
from .tools import (
    HYPOTHESIS_TOOL,
    PATCH_TOOL,
)

__all__ = [
    "HYPOTHESIS_PROMPT_TEMPLATE",
    "HYPOTHESIS_PROPOSAL_SCHEMA",
    "HYPOTHESIS_TOOL",
    "HypothesisProposalInput",
    "PATCH_PROPOSAL_SCHEMA",
    "PATCH_TOOL",
    "PatchEditIntent",
    "PatchFileChangeInput",
    "PatchProposalInput",
    "PatchSchemaPreflightError",
    "normalize_patch_output_with_repair_attribution",
    "preflight_patch_exact_replace_shape",
]
