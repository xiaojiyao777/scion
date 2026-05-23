"""Compatibility facade for proposal schema models, schema dicts, and tools."""

from __future__ import annotations

from .hypothesis import (
    HYPOTHESIS_PROMPT_TEMPLATE,
    HYPOTHESIS_PROPOSAL_SCHEMA,
    HypothesisProposalInput,
)
from .normalization import (
    _compact_novelty_scalar,
    _normalize_novelty_signature,
    _normalize_novelty_signature_item,
    normalize_patch_output_with_repair_attribution,
)
from .patch import (
    CODE_PROMPT_TEMPLATE,
    FIX_PROMPT_TEMPLATE,
    PATCH_PROPOSAL_SCHEMA,
    PatchEditIntent,
    PatchFileChangeInput,
    PatchProposalInput,
    PremiseCheck,
)
from .shared import (
    MechanismChangeInput,
    MechanismChangeType,
    _EXPECTED_TELEMETRY_DESCRIPTION,
    _empty_mechanism_changes_to_list,
    _mechanism_changes_json_schema,
    _validate_unique_mechanism_change_ids,
)
from .tools import (
    FIX_TOOL,
    HYPOTHESIS_TOOL,
    PATCH_TOOL,
    TOOL_SELECTION_SCHEMA,
    TOOL_SELECTION_TOOL,
    ToolSelectionInput,
)

__all__ = [
    "CODE_PROMPT_TEMPLATE",
    "FIX_PROMPT_TEMPLATE",
    "FIX_TOOL",
    "HYPOTHESIS_PROMPT_TEMPLATE",
    "HYPOTHESIS_PROPOSAL_SCHEMA",
    "HYPOTHESIS_TOOL",
    "HypothesisProposalInput",
    "MechanismChangeInput",
    "MechanismChangeType",
    "PATCH_PROPOSAL_SCHEMA",
    "PATCH_TOOL",
    "PatchEditIntent",
    "PatchFileChangeInput",
    "PatchProposalInput",
    "PremiseCheck",
    "TOOL_SELECTION_SCHEMA",
    "TOOL_SELECTION_TOOL",
    "ToolSelectionInput",
    "_EXPECTED_TELEMETRY_DESCRIPTION",
    "_compact_novelty_scalar",
    "_empty_mechanism_changes_to_list",
    "_mechanism_changes_json_schema",
    "_normalize_novelty_signature",
    "_normalize_novelty_signature_item",
    "_validate_unique_mechanism_change_ids",
    "normalize_patch_output_with_repair_attribution",
]
