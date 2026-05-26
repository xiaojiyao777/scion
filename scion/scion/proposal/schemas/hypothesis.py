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
        return _normalize_mechanism_changes_preflight(value)

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
]
