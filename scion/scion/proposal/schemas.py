"""JSON schemas and prompt templates for hypothesis and patch proposals."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_MECHANISM_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MECHANISM_CHANGE_TYPES = ("add", "modify", "replace", "remove", "integrate")
_NOVELTY_SIGNATURE_SCALAR_MAX_CHARS = 120
_EXPECTED_TELEMETRY_CATEGORIES = ("activity", "activation", "effect", "budget")
_EXPECTED_TELEMETRY_CATEGORY_TEXT = ", ".join(_EXPECTED_TELEMETRY_CATEGORIES)
_EXPECTED_TELEMETRY_DESCRIPTION = (
    "Structured runtime telemetry probes expected to show candidate activity, "
    "activation, effect, or budget allocation. Top-level keys must be telemetry "
    f"categories only: {_EXPECTED_TELEMETRY_CATEGORY_TEXT}. Values must be "
    "exact runtime telemetry field strings declared by the selected research "
    "surface evidence contract; do not put explanatory prose in these values. "
    "Use JSON arrays of field strings, or mechanism-keyed maps whose values "
    "are still field strings/arrays. Do not use runtime field names, suffixes, "
    "or metrics such as best_delta, improvement_counts, phase_runtime, or "
    "runtime_ms as top-level categories; put those declared runtime fields "
    "under the matching category instead. Activation must be mechanism "
    "activity evidence, not objective/outcome fields such as "
    "solver_algorithm_fleet_violation or solver_algorithm_total_distance."
)
MechanismChangeType = Literal["add", "modify", "replace", "remove", "integrate"]


# ---------------------------------------------------------------------------
# Pydantic v2 validation models (T19)
# ---------------------------------------------------------------------------

class MechanismChangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    change_type: MechanismChangeType

    @field_validator("id")
    @classmethod
    def valid_mechanism_id(cls, value: str) -> str:
        mechanism_id = str(value or "").strip()
        if not _MECHANISM_ID_RE.fullmatch(mechanism_id):
            raise ValueError(
                "mechanism id must match ^[a-z][a-z0-9_]{0,63}$"
            )
        return mechanism_id


def _mechanism_changes_json_schema() -> Dict[str, Any]:
    return {
        "type": "array",
        "description": (
            "Problem-neutral mechanism bindings touched by this proposal. "
            "Use stable lowercase ids matching ^[a-z][a-z0-9_]{0,63}$ and "
            "generic change_type values."
        ),
        "items": {
            "type": "object",
            "required": ["id", "change_type"],
            "properties": {
                "id": {
                    "type": "string",
                    "pattern": r"^[a-z][a-z0-9_]{0,63}$",
                },
                "change_type": {
                    "type": "string",
                    "enum": list(_MECHANISM_CHANGE_TYPES),
                },
            },
            "additionalProperties": False,
        },
    }


def _empty_mechanism_changes_to_list(value: Any) -> Any:
    return [] if value in (None, "") else value


def _validate_unique_mechanism_change_ids(
    changes: list[MechanismChangeInput],
) -> None:
    ids = [change.id for change in changes]
    duplicates = sorted(
        {mechanism_id for mechanism_id in ids if ids.count(mechanism_id) > 1}
    )
    if duplicates:
        raise ValueError(
            "mechanism_changes must not repeat id values: " + ", ".join(duplicates)
        )


class HypothesisProposalInput(BaseModel):
    hypothesis_text: str
    change_locus: str
    action: str
    target_file: Optional[str] = None
    predicted_direction: Literal["improve", "tradeoff", "exploratory"] = "exploratory"
    target_weakness: str = ""
    expected_effect: str = ""
    suggested_weight: Optional[float] = None
    target_objectives: list[str] = Field(default_factory=list)
    protected_objectives: list[str] = Field(default_factory=list)
    objective_tradeoff_policy: str = ""
    no_op_condition: str = ""
    risk_to_higher_priority: str = ""
    target_runtime_effect: Optional[str] = None
    complexity_claim: Optional[str] = None
    runtime_budget_strategy: Optional[str] = None
    expected_telemetry: Dict[str, Any] = Field(
        default_factory=dict,
        description=_EXPECTED_TELEMETRY_DESCRIPTION,
    )
    novelty_signature: Dict[str, Any] = Field(default_factory=dict)
    mechanism_changes: list[MechanismChangeInput] = Field(default_factory=list)

    @field_validator("mechanism_changes", mode="before")
    @classmethod
    def normalize_empty_mechanism_changes(cls, value: Any) -> Any:
        return _empty_mechanism_changes_to_list(value)

    @field_validator("novelty_signature", mode="before")
    @classmethod
    def normalize_novelty_signature(cls, value: Any) -> Any:
        return _normalize_novelty_signature(value)

    @field_validator("hypothesis_text", "change_locus")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("field must not be empty")
        return v

    @field_validator("action")
    @classmethod
    def valid_action(cls, v: str) -> str:
        if v not in ("modify", "create_new", "remove"):
            raise ValueError(f"action must be modify/create_new/remove, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_unique_mechanism_changes(self) -> "HypothesisProposalInput":
        _validate_unique_mechanism_change_ids(self.mechanism_changes)
        return self


class PatchFileChangeInput(BaseModel):
    file_path: str
    action: str
    code_content: str
    test_hint: Optional[str] = None

    @field_validator("file_path", "code_content")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("field must not be empty")
        return v

    @field_validator("action")
    @classmethod
    def valid_action(cls, v: str) -> str:
        if v not in ("modify", "create", "delete"):
            raise ValueError(f"action must be modify/create/delete, got '{v}'")
        return v


PremiseCheck = Literal["supported", "contradicted", "duplicate", "wrong_owner"]


def normalize_patch_output_with_repair_attribution(
    raw: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Normalize host-repairable patch output shape issues and record why."""

    normalized = dict(raw)
    repairs: list[dict[str, Any]] = []
    if "additional_changes" not in normalized:
        return normalized, ()

    value = normalized.get("additional_changes")
    if value in (None, ""):
        normalized["additional_changes"] = []
        repairs.append(
            {
                "field": "additional_changes",
                "repair_kind": "host_mechanical_normalization",
                "root_cause": "empty_or_null",
                "action": "normalized_to_empty_array",
            }
        )
        return normalized, tuple(repairs)

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return normalized, ()
        if isinstance(parsed, list):
            normalized["additional_changes"] = parsed
            value = parsed
            repairs.append(
                {
                    "field": "additional_changes",
                    "repair_kind": "host_mechanical_normalization",
                    "root_cause": "json_string_array",
                    "action": "parsed_json_string_to_array",
                }
            )
        else:
            return normalized, tuple(repairs)

    if isinstance(value, list):
        compacted: list[Any] = []
        removed_empty = 0
        removed_duplicates = 0
        seen: set[str] = set()
        for item in value:
            if item in (None, "", {}):
                removed_empty += 1
                continue
            fingerprint = json.dumps(item, sort_keys=True, default=str)
            if fingerprint in seen:
                removed_duplicates += 1
                continue
            seen.add(fingerprint)
            compacted.append(item)
        if removed_empty:
            repairs.append(
                {
                    "field": "additional_changes",
                    "repair_kind": "host_mechanical_normalization",
                    "root_cause": "empty_or_null_item",
                    "action": "dropped_empty_items",
                    "count": removed_empty,
                }
            )
        if removed_duplicates:
            repairs.append(
                {
                    "field": "additional_changes",
                    "repair_kind": "host_mechanical_normalization",
                    "root_cause": "exact_duplicate_item",
                    "action": "deduplicated_exact_items",
                    "count": removed_duplicates,
                }
            )
        if removed_empty or removed_duplicates:
            normalized["additional_changes"] = compacted
    return normalized, tuple(repairs)


def _normalize_novelty_signature(value: Any) -> Any:
    if value in (None, "", [], (), {}):
        return {}
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_novelty_signature_item(item)
            for key, item in value.items()
            if str(key).strip()
        }
    return value


def _normalize_novelty_signature_item(value: Any) -> Any:
    if isinstance(value, str):
        return _compact_novelty_scalar(value)
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_novelty_signature_item(item)
            for key, item in value.items()
            if str(key).strip()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_normalize_novelty_signature_item(item) for item in value]
    return value


def _compact_novelty_scalar(value: str) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= _NOVELTY_SIGNATURE_SCALAR_MAX_CHARS:
        return text
    return text[:_NOVELTY_SIGNATURE_SCALAR_MAX_CHARS].rstrip()


class PatchProposalInput(BaseModel):
    premise_check: PremiseCheck = "supported"
    premise_check_reason: str = ""
    file_path: str = ""
    action: str = "modify"
    code_content: str = ""
    test_hint: Optional[str] = None
    additional_changes: list[PatchFileChangeInput] = Field(default_factory=list)
    mechanism_changes: list[MechanismChangeInput] = Field(default_factory=list)

    @field_validator("mechanism_changes", mode="before")
    @classmethod
    def normalize_empty_mechanism_changes(cls, value: Any) -> Any:
        return _empty_mechanism_changes_to_list(value)

    @field_validator("additional_changes", mode="before")
    @classmethod
    def parse_additional_changes_json_string(cls, value: Any) -> Any:
        if value in (None, ""):
            return []
        if not isinstance(value, str):
            return value
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "additional_changes must be a JSON array, not an unparseable string"
            ) from exc
        if not isinstance(parsed, list):
            raise ValueError(
                "additional_changes JSON string must decode to an array"
            )
        return parsed

    @model_validator(mode="after")
    def validate_supported_patch_fields(self) -> "PatchProposalInput":
        if self.premise_check != "supported":
            return self
        if not self.file_path or not self.file_path.strip():
            raise ValueError("file_path must not be empty")
        if self.action != "delete" and (
            not self.code_content or not self.code_content.strip()
        ):
            raise ValueError("code_content must not be empty")
        if self.action not in ("modify", "create", "delete"):
            raise ValueError(
                f"action must be modify/create/delete, got '{self.action}'"
            )
        paths = [
            self.file_path,
            *[change.file_path for change in self.additional_changes],
        ]
        normalized = [str(path).strip() for path in paths]
        duplicates = sorted(
            {path for path in normalized if normalized.count(path) > 1}
        )
        if duplicates:
            raise ValueError(
                "additional_changes must not repeat file_path values: "
                + ", ".join(duplicates)
            )
        _validate_unique_mechanism_change_ids(self.mechanism_changes)
        return self


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

# ---------------------------------------------------------------------------
# JSON Schemas
# ---------------------------------------------------------------------------

HYPOTHESIS_PROPOSAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["hypothesis_text", "change_locus", "action"],
    "properties": {
        "hypothesis_text": {
            "type": "string",
            "description": "3-5 sentences. What the research-surface change does, why it differs from existing ones, expected mechanism of improvement. No generic filler.",
        },
        "change_locus": {
            "type": "string",
            "description": "Which research surface from the active problem specification.",
        },
        "action": {
            "type": "string",
            "enum": ["modify", "create_new", "remove"],
            "description": "modify: improve existing operator. create_new: add a new one. remove: drop a weak one.",
        },
        "target_file": {
            "type": ["string", "null"],
            "description": "For modify/remove: the target research-surface file path (e.g. operators/move_order.py or policies/search_policy.py). For create_new: the new file path.",
        },
        "predicted_direction": {
            "type": "string",
            "enum": ["improve", "tradeoff", "exploratory"],
        },
        "target_weakness": {
            "type": "string",
            "description": "The specific gap or weakness in the current pool this hypothesis addresses.",
        },
        "expected_effect": {
            "type": "string",
            "description": "Concrete expected measurable outcome.",
        },
        "suggested_weight": {
            "type": ["number", "null"],
            "description": "Operator weight for operator surfaces (0.1-3.0). Use null for policy surfaces.",
        },
        "target_objectives": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Declared objective name(s) this hypothesis is expected to "
                "improve. Use only objective ids from the problem spec; hard "
                "constraints or feasibility conditions belong in risk/no-op "
                "text, not this array."
            ),
        },
        "protected_objectives": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Declared higher-priority or critical objective name(s) this "
                "hypothesis must preserve. Use only objective ids from the "
                "problem spec; hard constraints or feasibility conditions "
                "belong in risk/no-op text, not this array."
            ),
        },
        "objective_tradeoff_policy": {
            "type": "string",
            "description": "How the hypothesis handles lexicographic protection or weighted-sum tradeoffs.",
        },
        "no_op_condition": {
            "type": "string",
            "description": "Condition under which the operator should return the original solution instead of risking harm.",
        },
        "risk_to_higher_priority": {
            "type": "string",
            "description": "Main risk to protected objectives and how the mechanism mitigates it.",
        },
        "target_runtime_effect": {
            "type": ["string", "null"],
            "description": "Short expected runtime impact, e.g. improve, neutral, risk, unknown, or a brief free-text claim.",
        },
        "complexity_claim": {
            "type": ["string", "null"],
            "description": "Structured summary of expected complexity, candidate scale, loop bounds, or neighborhood size.",
        },
        "runtime_budget_strategy": {
            "type": ["string", "null"],
            "description": "How the implementation should bound solve time, e.g. top-k candidates, sampling, early exit, or bounded neighborhoods.",
        },
        "expected_telemetry": {
            "type": "object",
            "additionalProperties": True,
            "description": _EXPECTED_TELEMETRY_DESCRIPTION,
        },
        "novelty_signature": {
            "type": "object",
            "additionalProperties": True,
            "description": "Structured identity values for declared novelty.signature_fields on singleton semantic surfaces. Required when the selected surface declares novelty.strategy=semantic_signature. Use compact scalars, lists, or small objects; scalar strings must be <=120 characters. Do not put rationale prose here.",
        },
        "mechanism_changes": _mechanism_changes_json_schema(),
    },
}

PATCH_PROPOSAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["file_path", "action", "code_content"],
    "properties": {
        "premise_check": {
            "type": "string",
            "enum": ["supported", "contradicted", "duplicate", "wrong_owner"],
            "description": (
                "Return supported only when the approved hypothesis is still "
                "valid, novel, and owned by this target. For contradicted, "
                "duplicate, or wrong_owner, provide premise_check_reason and "
                "do not generate a patch."
            ),
        },
        "premise_check_reason": {"type": "string"},
        "file_path": {"type": "string"},
        "action": {
            "type": "string",
            "enum": ["modify", "create", "delete"],
        },
        "code_content": {"type": "string"},
        "test_hint": {"type": ["string", "null"]},
        "additional_changes": {
            "type": "array",
            "description": (
                "Optional extra complete-file changes that are required for the "
                "approved algorithm change to be executable. Use this for "
                "solver_design module additions that also need scheduler or "
                "entrypoint integration. Each change is independently checked "
                "by Contract and applied in the same tainted candidate workspace."
            ),
            "items": {
                "type": "object",
                "required": ["file_path", "action", "code_content"],
                "properties": {
                    "file_path": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["modify", "create", "delete"],
                    },
                    "code_content": {"type": "string"},
                    "test_hint": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
        "mechanism_changes": _mechanism_changes_json_schema(),
    },
}

TOOL_SELECTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["intent"],
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

# Tool definitions for tool_use mode (avoids JSON escape issues)
HYPOTHESIS_TOOL: Dict[str, Any] = {
    "name": "generate_hypothesis",
    "description": (
        "Propose ONE novel hypothesis for improving a declared solver research surface.\n\n"
        "Usage:\n"
        "- Study ALL existing champion research-surface files before proposing \u2014 avoid duplicating existing logic or policy choices.\n"
        "- Check experiment history for approaches that already failed \u2014 do NOT repeat them.\n"
        "- Check sibling branches to avoid redundant exploration.\n\n"
        "Quality criteria:\n"
        "- Target a specific, named weakness in the current pool (not vague 'improvements').\n"
        "- The mechanism of improvement must be concrete and testable.\n"
        "- State target objective(s), protected objective(s), tradeoff policy, and no-op condition.\n"
        "- `target_objectives` and `protected_objectives` must contain only declared problem objective ids; hard constraints or feasibility conditions go in risk/no-op text.\n"
        "- State expected runtime effect, complexity/candidate bounds, and runtime budget strategy.\n"
        "- When the selected surface declares mechanism telemetry, include mechanism_changes with the specific mechanism id(s) and generic change_type values: add, modify, replace, remove, or integrate.\n"
        "- Declare expected_telemetry probes using runtime keys exposed by the selected surface evidence contract. Top-level expected_telemetry keys must be only activity, activation, effect, or budget; do not use runtime metric names or suffixes such as best_delta, improvement_counts, phase_runtime, or runtime_ms as categories. Activation must be mechanism activity evidence, not objective/outcome fields.\n"
        "- If the selected surface declares novelty.strategy=semantic_signature, provide every declared novelty.signature_fields entry in novelty_signature; free-text rationale is not novelty identity, and scalar string values must be <=120 characters.\n"
        "- Consider the problem-specific solver execution model provided in context; "
        "do not assume a fixed invocation count, pool size, or acceptance rule.\n"
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
        "Generate the complete file contents implementing an approved hypothesis.\n\n"
        "Usage:\n"
        "- Write the COMPLETE file \u2014 not a diff, not a snippet. The entire file content.\n"
        "- Study the champion research-surface files for style, data model usage, and import patterns.\n"
        "- Follow the problem-specific research-surface interface EXACTLY.\n\n"
        "- Echo the approved hypothesis mechanism_changes ids exactly when present.\n\n"
        "Code quality requirements:\n"
        "- Preserve every feasibility and consistency invariant described in the interface spec.\n"
        "- For operator surfaces, use the provided `rng` argument for ALL randomness.\n"
        "- NEVER use `list(set(...))` or iterate over set/dict in order-dependent ways \u2014 "
        "use `sorted()` for determinism.\n"
        "- Keep neighborhood enumeration bounded. Do NOT enumerate all 3/4-way "
        "problem-entity combinations; use top-k candidate caps, sampling, or pairwise "
        "moves with explicit limits.\n"
        "- When the approved hypothesis declares mechanism_changes or "
        "expected_telemetry, use the exact declared mechanism id in the runtime "
        "telemetry helpers exposed by the selected surface. Activation/effect "
        "telemetry failures are repaired by recording the declared mechanism, "
        "not by renaming the mechanism or changing expected_telemetry.\n"
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
        "Fix a code patch that failed verification.\n\n"
        "Usage:\n"
        "- Read the failure details carefully \u2014 fix the SPECIFIC issue reported.\n"
        "- Make MINIMAL changes to fix the failure. Do not refactor unrelated code.\n"
        "- Preserve the intended algorithmic logic \u2014 only fix the mechanical error.\n"
        "- Return the COMPLETE corrected file, not just changed lines.\n\n"
        "Common patterns:\n"
        "- V6_feasibility: output violates the problem-specific feasibility oracle.\n"
        "- V5_solution_consistency: output violates problem-specific solution consistency.\n"
        "- V8_nondeterminism: non-deterministic code (no uuid, use sorted(), use rng).\n"
        "- V1_syntax: indentation, parentheses, colons.\n"
        "- V2_interface: missing Operator base class or wrong execute() signature.\n"
        "- runtime_smoke.telemetry_guard: preserve the declared mechanism id and "
        "add the missing activation/effect runtime records through the selected "
        "surface telemetry helpers; do not change objectives, constraints, or "
        "the approved hypothesis to silence the guard."
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

# ---------------------------------------------------------------------------
# Prompt templates
# Input slots follow §5.2 of scion-engineering-arch-v1.md.
# Section-level placeholders avoid field-level fragility.
# ---------------------------------------------------------------------------

HYPOTHESIS_PROMPT_TEMPLATE = """\
You are a research agent optimising declared research surfaces of a combinatorial optimisation solver.
Your goal is to propose ONE novel hypothesis that, if implemented, would improve solver quality.

## Problem Summary
{problem_summary}

## Current Champion Research Code
The following research-surface files make up the current champion solution.
Study them carefully before proposing anything — avoid duplicating existing logic or policy choices.

{champion_operators_code}

## Champion State
{champion_stats}

## Experiment History — This Branch
Prior hypotheses attempted on this branch and their outcomes.
Do NOT repeat an approach that has already failed.

{experiment_history}

## Globally Blacklisted Approaches
These have been tried and rejected globally — do not repeat them:

{blacklist_summary}

## Sibling Branches Currently Exploring
To avoid redundancy, these directions are already being explored:

{sibling_summary}

## Task
Propose ONE hypothesis for improving a declared research surface.
- Set `change_locus` to one of: {operator_categories}
- Set `action` to: "modify" (change existing surface file), "create_new" (new operator where allowed), or "remove" (delete operator where allowed)
- If action is "modify" or "remove", set `target_file` to the relative path (e.g. "operators/local_move.py" or "policies/search_policy.py")
- Write a detailed `hypothesis_text` explaining the idea, the expected mechanism, and why it should improve results
- Set `target_weakness` to describe what current behaviour you are targeting
- Set `expected_effect` to describe the measurable improvement you expect
- Set `target_runtime_effect` to the expected runtime impact (improve/neutral/risk/unknown or short text)
- Set `complexity_claim` to the expected complexity, candidate scale, or loop bounds
- Set `runtime_budget_strategy` to how the operator or solver body will cap solve time (top-k, sampling, early exit, bounded neighborhood, time-polling, etc.)
- If the selected surface declares mechanism telemetry, set `mechanism_changes` to the mechanism id(s) touched by this hypothesis. Ids must match ^[a-z][a-z0-9_]{0,63}$ and use change_type add/modify/replace/remove/integrate.
- Set `expected_telemetry` to declared runtime keys that should prove activity, activation, effect, or budget allocation for this hypothesis

Respond with a single JSON object (no markdown fences, no extra text) matching this schema:
{{
  "hypothesis_text": "<detailed explanation of the idea>",
  "change_locus": "<one of the research surfaces>",
  "action": "modify" | "create_new" | "remove",
  "target_file": "<relative path or null>",
  "predicted_direction": "improve" | "tradeoff" | "exploratory",
  "target_weakness": "<what current weakness this addresses>",
  "expected_effect": "<expected measurable improvement>",
  "suggested_weight": <sampling weight 0.0–1.0 or null>,
  "target_runtime_effect": "<expected runtime effect or null>",
  "complexity_claim": "<complexity/candidate-bound claim or null>",
  "runtime_budget_strategy": "<runtime budget strategy or null>",
  "mechanism_changes": [
    {{"id": "<mechanism_id>", "change_type": "add" | "modify" | "replace" | "remove" | "integrate"}}
  ],
  "expected_telemetry": {{
    "activity": ["<declared runtime counter expected to be positive>"],
    "activation": ["<declared runtime field proving the mechanism ran>"],
    "effect": ["<declared runtime field proving the claimed effect>"],
    "budget": ["<declared runtime field proving stage budget was not starved>"]
  }}
}}
"""

CODE_PROMPT_TEMPLATE = """\
You are a software engineer implementing a declared research surface for a combinatorial optimisation solver framework.
Your task is to write the complete file contents that implement the approved hypothesis below.

## Problem Summary
{problem_summary}

## Hypothesis to Implement
{hypothesis_detail}

## Current Champion Research Code
Study these implementations for coding style, data model usage, and patterns:

{champion_operators_code}

## Target File (current content — modify this if action is "modify")
{target_file_code}

## Reference Surface Files
{reference_operators}

## Research Surface Interface Specification
Follow this interface exactly:

{operator_interface_spec}

## Allowed Imports
Only use modules from this whitelist — any other import will be rejected:
{import_whitelist}

## Editable Paths
{editable_patterns}

## Frozen Paths (DO NOT MODIFY)
{frozen_patterns}

## Task
Produce the complete file content that implements the hypothesis.
- Conform to the research-surface interface specification exactly
- Preserve all feasibility, consistency, and determinism invariants described there
- For operator surfaces, use the provided `rng` argument for all randomness and return the new solution/artifact, or original if no valid move found
- For policy surfaces, implement the required module-level functions and keep return values inside the documented bounds
- If action is "delete", set code_content to an empty string ""
- If the approved algorithm change requires extra files to be executable, put
  them in `additional_changes`; each item must contain complete file contents
  and will be independently checked.
- Echo the approved hypothesis `mechanism_changes` ids exactly. Do not add or
  drop mechanism ids in the patch response.

Respond with a single JSON object (no markdown fences, no extra text):
{{
  "premise_check": "supported" | "contradicted" | "duplicate" | "wrong_owner",
  "premise_check_reason": "<brief reason when not supported, otherwise empty>",
  "file_path": "<relative path within workspace, e.g. operators/my_operator.py>",
  "action": "modify" | "create" | "delete",
  "code_content": "<complete file contents as a single string>",
  "additional_changes": [
    {{
      "file_path": "<relative path for required integration edit>",
      "action": "modify" | "create" | "delete",
      "code_content": "<complete file contents>"
    }}
  ],
  "mechanism_changes": [
    {{"id": "<approved_mechanism_id>", "change_type": "add" | "modify" | "replace" | "remove" | "integrate"}}
  ],
  "test_hint": "<optional brief testing note, or null>"
}}
"""

FIX_PROMPT_TEMPLATE = """\
You are a software engineer fixing an optimisation research-surface file that failed verification.
Correct the code so it passes, while preserving the intended logic.

## Problem Summary
{problem_summary}

## Original Code That Failed
{original_code}

## Verification Failure Details
{failure_detail}

## Research Surface Interface Specification
{operator_interface_spec}

## Allowed Imports
{import_whitelist}

## Editable Paths
{editable_patterns}

## Frozen Paths (DO NOT MODIFY)
{frozen_patterns}

## Task
Fix the code so it passes verification.
Preserve the research-surface interface specification exactly.
Make only the minimal changes needed to fix the reported failure.

Respond with a single JSON object (no markdown fences, no extra text):
{{
  "premise_check": "supported",
  "premise_check_reason": "",
  "file_path": "<same relative path as original>",
  "action": "modify" | "create" | "delete",
  "code_content": "<complete corrected file contents>",
  "additional_changes": [],
  "test_hint": "<optional note, or null>"
}}
"""
