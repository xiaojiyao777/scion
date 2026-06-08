"""Hypothesis proposal input model, JSON schema, and legacy prompt template."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .normalization import _normalize_novelty_signature
from .shared import (
    _EXPECTED_TELEMETRY_DESCRIPTION,
    _mechanism_changes_json_schema,
    _normalize_mechanism_changes_preflight,
    _validate_unique_mechanism_change_ids,
    MechanismChangeInput,
)

_MATERIAL_DIFFERENCE_MAX_STRING = 120
_MATERIAL_DIFFERENCE_MAX_LIST_ITEMS = 12
_MATERIAL_DIFFERENCE_MAX_DICT_KEYS = 24
_MATERIAL_DIFFERENCE_MAX_DEPTH = 3
_MATERIAL_DIFFERENCE_BLOCKED_KEY_PARTS = (
    "raw",
    "rationale",
    "reasoning",
    "trace",
    "transcript",
    "prompt",
    "observation",
    "llm",
    "hypothesis_text",
    "cross_branch_text",
)

_BRANCH_LESSON_USAGE_MAX_STRING = 120
_BRANCH_LESSON_USAGE_MAX_LIST_ITEMS = 12
_BRANCH_LESSON_USAGE_MAX_DICT_KEYS = 24
_BRANCH_LESSON_USAGE_MAX_DEPTH = 4
_BRANCH_LESSON_USAGE_BLOCKED_KEY_PARTS = (
    *_MATERIAL_DIFFERENCE_BLOCKED_KEY_PARTS,
    "prose",
)


def normalize_material_difference(value: Any) -> Dict[str, Any]:
    """Return a compact proposal-visible material-difference record.

    This is tainted proposal/audit data. It intentionally keeps only bounded
    structured facts and drops prose-like or raw provenance fields.
    """

    normalized = _normalize_material_difference_value(value, depth=0)
    return normalized if isinstance(normalized, dict) else {}


def normalize_branch_lesson_usage(value: Any) -> Dict[str, Any]:
    """Return a compact proposal-only branch lesson usage record.

    This stays in tainted proposal/audit metadata. It records which sibling or
    same-branch lessons the proposal claims to borrow, avoid, contrast, or
    preserve, while dropping raw prompt/context text and long prose.
    """

    normalized = _normalize_branch_lesson_usage_value(value, depth=0)
    return normalized if isinstance(normalized, dict) else {}


def _normalize_material_difference_value(value: Any, *, depth: int) -> Any:
    if depth > _MATERIAL_DIFFERENCE_MAX_DEPTH:
        return None
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text or len(text) > _MATERIAL_DIFFERENCE_MAX_STRING:
            return None
        if "\n" in text or "\r" in text:
            return None
        return text
    if isinstance(value, (list, tuple, set)):
        items: list[Any] = []
        for item in list(value)[:_MATERIAL_DIFFERENCE_MAX_LIST_ITEMS]:
            normalized = _normalize_material_difference_value(item, depth=depth + 1)
            if normalized not in (None, "", [], {}, ()):
                items.append(normalized)
        return items
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for raw_key, raw_item in list(value.items())[
            :_MATERIAL_DIFFERENCE_MAX_DICT_KEYS
        ]:
            key = str(raw_key or "").strip()
            if not key or len(key) > _MATERIAL_DIFFERENCE_MAX_STRING:
                continue
            key_lower = key.lower()
            if any(
                part in key_lower for part in _MATERIAL_DIFFERENCE_BLOCKED_KEY_PARTS
            ):
                continue
            normalized = _normalize_material_difference_value(
                raw_item,
                depth=depth + 1,
            )
            if normalized not in (None, "", [], {}, ()):
                out[key] = normalized
        return out
    return None


def _normalize_branch_lesson_usage_value(value: Any, *, depth: int) -> Any:
    if depth > _BRANCH_LESSON_USAGE_MAX_DEPTH:
        return None
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text or len(text) > _BRANCH_LESSON_USAGE_MAX_STRING:
            return None
        if "\n" in text or "\r" in text:
            return None
        return text
    if isinstance(value, (list, tuple, set)):
        items: list[Any] = []
        for item in list(value)[:_BRANCH_LESSON_USAGE_MAX_LIST_ITEMS]:
            normalized = _normalize_branch_lesson_usage_value(
                item,
                depth=depth + 1,
            )
            if normalized not in (None, "", [], {}, ()):
                items.append(normalized)
        return items
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for raw_key, raw_item in list(value.items())[
            :_BRANCH_LESSON_USAGE_MAX_DICT_KEYS
        ]:
            key = str(raw_key or "").strip()
            if not key or len(key) > _BRANCH_LESSON_USAGE_MAX_STRING:
                continue
            key_lower = key.lower()
            if any(
                part in key_lower for part in _BRANCH_LESSON_USAGE_BLOCKED_KEY_PARTS
            ):
                continue
            normalized = _normalize_branch_lesson_usage_value(
                raw_item,
                depth=depth + 1,
            )
            if normalized not in (None, "", [], {}, ()):
                out[key] = normalized
        return out
    return None


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
    material_difference: Dict[str, Any] = Field(default_factory=dict)
    branch_lesson_usage: Dict[str, Any] = Field(default_factory=dict)
    mechanism_changes: list[MechanismChangeInput] = Field(default_factory=list)

    @field_validator("mechanism_changes", mode="before")
    @classmethod
    def normalize_empty_mechanism_changes(cls, value: Any) -> Any:
        return _normalize_mechanism_changes_preflight(value)

    @field_validator("novelty_signature", mode="before")
    @classmethod
    def normalize_novelty_signature(cls, value: Any) -> Any:
        return _normalize_novelty_signature(value)

    @field_validator("material_difference", mode="before")
    @classmethod
    def normalize_material_difference(cls, value: Any) -> Dict[str, Any]:
        return normalize_material_difference(value)

    @field_validator("branch_lesson_usage", mode="before")
    @classmethod
    def normalize_branch_lesson_usage(cls, value: Any) -> Dict[str, Any]:
        return normalize_branch_lesson_usage(value)

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
            "description": "modify: improve an existing file. create_new: add a genuinely new file. remove: drop a weak one.",
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
        "material_difference": {
            "type": "object",
            "additionalProperties": True,
            "description": (
                "Compact structured proposal/audit record explaining how this "
                "hypothesis is materially different from nearby branch attempts "
                "when required by branch metadata. Use short scalar strings "
                "(<=120 chars), enums, small lists, changed dimension names, "
                "signature digests, or compact evidence-status fields. Do not "
                "include raw cross-branch text, LLM rationale, trace, prompt, "
                "transcript, or hypothesis prose."
            ),
        },
        "branch_lesson_usage": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "borrowed_lessons": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "avoided_lessons": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "contrasted_lessons": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "preserved_same_branch_lesson": {
                    "type": "object",
                    "additionalProperties": True,
                },
                "rejected_weak_positive_lessons": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "clean_fork_diversity_claim": {
                    "type": "object",
                    "additionalProperties": True,
                },
            },
            "description": (
                "Compact structured proposal-only/audit record describing how "
                "this tainted hypothesis uses visible branch lessons when "
                "branch metadata or branch lesson records require it. Supported "
                "shape includes borrowed_lessons, avoided_lessons, "
                "contrasted_lessons, preserved_same_branch_lesson, "
                "rejected_weak_positive_lessons, and clean_fork_diversity_claim "
                "with lesson ids, source branch ids, target_file/action/"
                "specific mechanism linkage, changed generic contrast dimensions, "
                "activation/effect paths for weak-positive reuse, and short "
                "enum-like tokens. Prefer `mechanism` or `mechanism_change_id` "
                "using a concrete mechanism_changes id; `mechanism_id` is an "
                "accepted compatibility alias. Do not use only a broad "
                "mechanism family token as linkage. Excluded from DecisionFeatures; do not include raw "
                "cross-branch text, LLM rationale, reasoning, trace, prompt, "
                "transcript, observation, hypothesis prose, or long free text."
            ),
        },
        "mechanism_changes": _mechanism_changes_json_schema(),
    },
}


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
- Set `action` to: "modify" (change existing surface file), "create_new" (new file only, where allowed), or "remove" (delete operator where allowed)
- If action is "modify" or "remove", set `target_file` to the relative path (e.g. "operators/local_move.py" or "policies/search_policy.py")
- Write a detailed `hypothesis_text` explaining the idea, the expected mechanism, and why it should improve results
- Set `target_weakness` to describe what current behaviour you are targeting
- Set `expected_effect` to describe the measurable improvement you expect
- Set `target_runtime_effect` to the expected runtime impact (improve/neutral/risk/unknown or short text)
- Set `complexity_claim` to the expected complexity, candidate scale, or loop bounds
- Set `runtime_budget_strategy` to how the operator or solver body will cap solve time (top-k, sampling, early exit, bounded neighborhood, time-polling, etc.)
- If branch metadata says a material difference is required, set `material_difference` to a compact structured record of changed generic dimensions, signature digests, and evidence-status differences. Do not include raw cross-branch text, LLM rationale, trace, prompt, transcript, or repeated hypothesis prose.
- If context includes a `branch_lesson_usage_requirement` or branch lesson records, set `branch_lesson_usage` to a compact proposal-only/audit record explaining which lessons you borrow, avoid, contrast, preserve, or reject with machine-readable reason codes. Clean forks and sibling-aware proposals need at least one borrowed_lessons, avoided_lessons, or contrasted_lessons entry plus changed generic dimensions and target_file/action/specific mechanism linkage. Prefer `mechanism` or `mechanism_change_id` and use the concrete mechanism_changes id touched by the proposal; `mechanism_id` is also accepted for compatibility. Do not use only broad family tokens such as mechanism_family/change_locus as the mechanism linkage. Weak-positive transfer must either borrow/preserve with activation_path and effect_path, or emit rejected_weak_positive_lessons with a reject_reason_code and the same linkage. Do not include raw lesson text, prompt text, rationale, transcript, trace, or problem-specific semantics.
- If the selected surface declares mechanism telemetry, set `mechanism_changes` to the mechanism id(s) touched by this hypothesis. Ids must match ^[a-z][a-z0-9_]{0,63}$ and use change_type add/modify/replace/remove/integrate. Branch `allowed_next_actions` labels such as tune, repair, parameterize, and telemetry_wiring are research action labels, not `mechanism_changes[].change_type` values; map tune/parameterize to modify and telemetry_wiring to modify or integrate.
- Set `expected_telemetry` to declared runtime keys that should prove activity, activation, effect, or budget allocation for this hypothesis. Activation must use mechanism-specific activity evidence, not objective/outcome fields. Aggregate outcome or activity fields show effect or activity, not activation. Declare best_delta/delta_sum effect fields only when the mechanism can emit a positive improvement delta through record_move; if it only proves activity or activation, use activity/activation telemetry instead. If you modify an existing phase or component, declare the changed lever as its own mechanism id and use that same id in expected telemetry.

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
  "material_difference": {{
    "changed_dimensions": ["<generic dimension id>"],
    "signature_digest": "<short digest or id>",
    "evidence_status_delta": ["<compact status enum>"]
  }},
  "branch_lesson_usage": {{
    "borrowed_lessons": [{{"lesson_id": "<lesson id>", "source_branch_ids": ["<branch id>"], "lesson_type": "weak_positive", "activation_path": "<compact generic token>", "effect_path": "<compact generic token>", "target_file": "<relative path>", "action": "modify", "mechanism": "<specific mechanism_changes id>"}}],
    "avoided_lessons": [{{"lesson_id": "<lesson id>", "avoid_reason": "<compact generic token>", "target_file": "<relative path>", "action": "modify", "mechanism_change_id": "<specific mechanism_changes id>"}}],
    "contrasted_lessons": [{{"lesson_id": "<lesson id>", "contrast_dimensions": ["<generic dimension id>"], "new_path": "<compact generic token>", "target_file": "<relative path>", "action": "modify", "mechanism_id": "<specific mechanism_changes id>"}}],
    "preserved_same_branch_lesson": {{"lesson_id": "<lesson id>", "preserved_signal": "<compact generic token>", "risk_to_avoid": "<compact generic token>", "target_file": "<relative path>", "action": "modify", "mechanism": "<specific mechanism_changes id>"}},
    "rejected_weak_positive_lessons": [{{"lesson_id": "<lesson id>", "lesson_type": "weak_positive", "reject_reason_code": "<compact generic token>", "target_file": "<relative path>", "action": "modify", "mechanism_change_id": "<specific mechanism_changes id>"}}],
    "clean_fork_diversity_claim": {{"changed_dimensions": ["<generic dimension id>"], "sibling_duplication_allowed": false}}
  }},
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


__all__ = [
    "HYPOTHESIS_PROMPT_TEMPLATE",
    "HYPOTHESIS_PROPOSAL_SCHEMA",
    "HypothesisProposalInput",
    "normalize_branch_lesson_usage",
    "normalize_material_difference",
]
