"""Tool-selection schema and proposal tool definitions."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hypothesis import HYPOTHESIS_PROPOSAL_SCHEMA
from .patch import PATCH_PROPOSAL_SCHEMA


class ToolSelectionInput(BaseModel):
    """Model-side plan for the next proposal tool call.

    This is a planning contract only. The model returns the intended tool name
    and JSON arguments; APS remains the only component allowed to execute tools.
    """

    model_config = ConfigDict(extra="forbid")

    intent: Literal["call_tool", "stop", "final"] = "call_tool"
    tool_name: Optional[str] = None
    args: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def call_tool_requires_name(self) -> "ToolSelectionInput":
        if self.intent == "call_tool" and not (self.tool_name or "").strip():
            raise ValueError("tool_name is required when intent is call_tool")
        return self


TOOL_SELECTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["call_tool", "stop", "final"],
            "description": (
                "call_tool to request exactly one allowed proposal tool; "
                "stop/final when no more tool context is needed."
            ),
        },
        "tool_name": {
            "type": ["string", "null"],
            "description": "Name of one tool from allowed_tools when intent is call_tool.",
        },
        "args": {
            "type": "object",
            "description": "JSON arguments matching the selected tool input schema.",
            "additionalProperties": True,
        },
    },
    "additionalProperties": False,
}


HYPOTHESIS_TOOL: Dict[str, Any] = {
    "name": "generate_hypothesis",
    "description": (
        "Propose ONE novel hypothesis for improving a declared solver research surface.\n\n"
        "Usage:\n"
        "- Study ALL existing champion research-surface files before proposing — avoid duplicating existing logic or policy choices.\n"
        "- Check experiment history for approaches that already failed — do NOT repeat them.\n"
        "- Check sibling branches to avoid redundant exploration.\n\n"
        "Quality criteria:\n"
        "- Target a specific, named weakness in the current pool (not vague 'improvements').\n"
        "- The mechanism of improvement must be concrete and testable.\n"
        "- State target objective(s), protected objective(s), tradeoff policy, and no-op condition.\n"
        "- `target_objectives` and `protected_objectives` must contain only declared problem objective ids; hard constraints or feasibility conditions go in risk/no-op text.\n"
        "- State expected runtime effect, complexity/candidate bounds, and runtime budget strategy.\n"
        "- When the selected surface declares mechanism telemetry, include mechanism_changes with the specific mechanism id(s) and generic change_type values: add, modify, replace, remove, or integrate.\n"
        "- Declare expected_telemetry probes using runtime keys exposed by the "
        "selected surface evidence contract. Top-level expected_telemetry keys "
        "must be only activity, activation, effect, or budget; do not use "
        "runtime metric names or suffixes such as best_delta, "
        "improvement_counts, phase_runtime, or runtime_ms as categories. "
        "Activation must be mechanism-specific activity evidence, not "
        "objective/outcome fields. Aggregate outcome/activity fields show "
        "effect or activity, not activation. For mapping telemetry, use a "
        "mechanism-specific path containing the declared mechanism id; the "
        "whole map field alone is not activation evidence. If changing an "
        "existing phase or component, declare a specific mechanism id for the "
        "changed lever and use that same id in every expected_telemetry path. "
        "Do not replace that declared mechanism id with a broad aggregate "
        "phase, family, or runtime bucket label. "
        "Declare best_delta/delta_sum effect fields only when the mechanism "
        "can emit a positive improvement delta through record_move; otherwise "
        "declare activity or activation telemetry instead.\n"
        "- If the selected surface declares novelty.strategy=semantic_signature, provide every declared novelty.signature_fields entry in novelty_signature; free-text rationale is not novelty identity, and scalar string values must be <=120 characters.\n"
        "- Consider the problem-specific solver execution model provided in context; "
        "do not assume a fixed invocation count, pool size, or selection rule.\n"
        "- Prefer surface changes that provide a capability the current solver currently lacks.\n\n"
        "Common mistakes to avoid:\n"
        "- Proposing random moves without a concrete objective mechanism.\n"
        "- Ignoring feasibility constraints (operator surfaces MUST produce feasible solutions).\n"
        "- Reinventing logic already present in an existing operator with different variable names."
    ),
    "input_schema": HYPOTHESIS_PROPOSAL_SCHEMA,
}

PATCH_TOOL: Dict[str, Any] = {
    "name": "generate_patch",
    "description": (
        "Generate a typed edit set implementing an approved hypothesis.\n\n"
        "Usage:\n"
        "- For existing action=modify files, default to edit_intent=exact_replace.\n"
        "- Use edit_intent=full_file only for creates or deletes; "
        "host-visible existing-file modifies with full_file/content_after are "
        "rejected by default, and full_file_reason is not authorization.\n"
        "- Existing files require action=modify exact_replace with source_digest; "
        "create/full content is only for genuinely new files.\n"
        "- For exact_replace provide source_digest, non-empty old_string, "
        "new_string, and replace_all. To delete text use new_string: \"\"; "
        "never omit new_string or set it to null.\n"
        "- Do not emit unified diffs; the host derives audit diffs from before/after content.\n"
        "- Study the champion research-surface files for style, data model usage, and import patterns.\n"
        "- Follow the problem-specific research-surface interface EXACTLY.\n\n"
        "- Echo the approved hypothesis mechanism_changes ids exactly when present.\n\n"
        "Code quality requirements:\n"
        "- Preserve every feasibility and consistency invariant described in the interface spec.\n"
        "- For operator surfaces, use the provided `rng` argument for ALL randomness.\n"
        "- NEVER use `list(set(...))` or iterate over set/dict in order-dependent ways — "
        "use `sorted()` for determinism.\n"
        "- Keep neighborhood enumeration bounded. Do NOT enumerate all 3/4-way "
        "problem-entity combinations; use top-k candidate caps, sampling, or pairwise "
        "moves with explicit limits.\n"
        "- When the approved hypothesis declares mechanism_changes or "
        "expected_telemetry, use the exact declared mechanism id in the runtime "
        "telemetry helpers exposed by the selected surface. Activation/effect "
        "telemetry failures are repaired by recording the declared mechanism, "
        "not by renaming the mechanism or changing expected_telemetry.\n"
        "- For delta-valued effect telemetry such as best_delta or delta_sum, "
        "the active improvement path must call "
        "`context.record_move('<mechanism>', attempted=1, accepted=1, "
        "delta=<positive_improvement_delta>, best_improved=True)`. If the "
        "approved mechanism only proves activity/activation, do not fabricate "
        "positive deltas; mark the premise contradicted and explain the "
        "expected_telemetry/mechanism declaration mismatch.\n"
        "- Return a valid solution/artifact according to the problem adapter contract when implementing an operator surface.\n\n"
        "Common rejection causes:\n"
        "- Feasibility or solution consistency violation.\n"
        "- Unbounded/high-order combinations such as `combinations(..., size)` "
        "or `combinations(..., 4)`.\n"
        "- Non-determinism: iterating over sets without sorting.\n"
        "- Import violation: using modules not in the whitelist.\n"
        "- Interface mismatch: wrong method signature, missing module-level policy function, or missing deep copy."
    ),
    "input_schema": PATCH_PROPOSAL_SCHEMA,
}

FIX_TOOL: Dict[str, Any] = {
    "name": "fix_patch",
    "description": (
        "Fix a code patch that failed verification using typed edits or full-file fallback.\n\n"
        "Usage:\n"
        "- Read the failure details carefully — fix the SPECIFIC issue reported.\n"
        "- Make MINIMAL changes to fix the failure. Do not refactor unrelated code.\n"
        "- Preserve the intended algorithmic logic — only fix the mechanical error.\n"
        "- Prefer exact_replace for repairs to existing files; use full_file "
        "only for creates or deletes. full_file_reason is not authorization "
        "for host-visible existing-file modifies. Existing files require "
        "action=modify exact_replace with source_digest; create/full content "
        "is only for genuinely new files. For exact_replace, new_string must "
        "be present as a string; use new_string: \"\" for deletion and never "
        "omit it or set it to null.\n\n"
        "Common patterns:\n"
        "- V6_feasibility: output violates the problem-specific feasibility oracle.\n"
        "- V5_solution_consistency: output violates problem-specific solution consistency.\n"
        "- V8_nondeterminism: non-deterministic code (no uuid, use sorted(), use rng).\n"
        "- V1_syntax: indentation, parentheses, colons.\n"
        "- V2_interface: missing Operator base class or wrong execute() signature.\n"
        "- runtime_smoke.telemetry_guard: preserve the declared mechanism id and "
        "add the missing activation/effect runtime records through the selected "
        "surface telemetry helpers; do not change objectives, constraints, or "
        "the approved hypothesis to silence the guard. For delta-valued effect "
        "fields, use record_move with a positive improvement delta and "
        "best_improved=True only for true improvements; otherwise report the "
        "expected_telemetry/mechanism declaration mismatch."
    ),
    "input_schema": PATCH_PROPOSAL_SCHEMA,
}

TOOL_SELECTION_TOOL: Dict[str, Any] = {
    "name": "plan_proposal_tool_call",
    "description": (
        "Choose the next exposure-controlled proposal-context tool to call. "
        "Return only an intent, one allowed tool name, and JSON arguments. "
        "Do not execute tools or include private rationale."
    ),
    "input_schema": TOOL_SELECTION_SCHEMA,
}


__all__ = [
    "FIX_TOOL",
    "HYPOTHESIS_TOOL",
    "PATCH_TOOL",
    "TOOL_SELECTION_SCHEMA",
    "TOOL_SELECTION_TOOL",
    "ToolSelectionInput",
]
