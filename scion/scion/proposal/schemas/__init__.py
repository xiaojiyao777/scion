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
    PatchSchemaPreflightError,
    PremiseCheck,
    preflight_patch_exact_replace_shape,
)
from .target_intent import (
    HYPOTHESIS_TARGET_INTENT_SCHEMA,
    HypothesisTargetIntentInput,
)
from .shared import (
    MECHANISM_DUPLICATE_ID_CONFLICT,
    MECHANISM_SCHEMA_QUALITY_BLOCK,
    MechanismChangeInput,
    MechanismChangeType,
    _EXPECTED_TELEMETRY_DESCRIPTION,
    _empty_mechanism_changes_to_list,
    _mechanism_changes_json_schema,
    _normalize_mechanism_changes_preflight,
    _validate_unique_mechanism_change_ids,
    normalize_mechanism_changes_with_repair_attribution,
)
from .tools import (
    FIX_TOOL,
    HYPOTHESIS_TOOL,
    HYPOTHESIS_TARGET_INTENT_TOOL,
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
    "HYPOTHESIS_TARGET_INTENT_SCHEMA",
    "HYPOTHESIS_TARGET_INTENT_TOOL",
    "HYPOTHESIS_TOOL",
    "HypothesisProposalInput",
    "HypothesisTargetIntentInput",
    "MechanismChangeInput",
    "MechanismChangeType",
    "MECHANISM_DUPLICATE_ID_CONFLICT",
    "MECHANISM_SCHEMA_QUALITY_BLOCK",
    "PATCH_PROPOSAL_SCHEMA",
    "PATCH_TOOL",
    "PatchEditIntent",
    "PatchFileChangeInput",
    "PatchProposalInput",
    "PatchSchemaPreflightError",
    "PremiseCheck",
    "TOOL_SELECTION_SCHEMA",
    "TOOL_SELECTION_TOOL",
    "ToolSelectionInput",
    "_EXPECTED_TELEMETRY_DESCRIPTION",
    "_compact_novelty_scalar",
    "_empty_mechanism_changes_to_list",
    "_mechanism_changes_json_schema",
    "_normalize_mechanism_changes_preflight",
    "_normalize_novelty_signature",
    "_normalize_novelty_signature_item",
    "_validate_unique_mechanism_change_ids",
    "normalize_mechanism_changes_with_repair_attribution",
    "normalize_patch_output_with_repair_attribution",
    "preflight_patch_exact_replace_shape",
]
