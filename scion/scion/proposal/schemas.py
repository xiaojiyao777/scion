"""JSON schemas and prompt templates for hypothesis and patch proposals."""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Pydantic v2 validation models (T19)
# ---------------------------------------------------------------------------

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


class PatchProposalInput(BaseModel):
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
            "description": "Objective component(s) this hypothesis is expected to improve.",
        },
        "protected_objectives": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Higher-priority or critical objectives this hypothesis must preserve.",
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
    },
}

PATCH_PROPOSAL_SCHEMA: Dict[str, Any] = {
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
        "- State expected runtime effect, complexity/candidate bounds, and runtime budget strategy.\n"
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
        "Code quality requirements:\n"
        "- Preserve every feasibility and consistency invariant described in the interface spec.\n"
        "- For operator surfaces, use the provided `rng` argument for ALL randomness.\n"
        "- NEVER use `list(set(...))` or iterate over set/dict in order-dependent ways \u2014 "
        "use `sorted()` for determinism.\n"
        "- Keep neighborhood enumeration bounded. Do NOT enumerate all 3/4-way "
        "problem-entity combinations; use top-k candidate caps, sampling, or pairwise "
        "moves with explicit limits.\n"
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
        "- V2_interface: missing Operator base class or wrong execute() signature."
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
- Set `action` to: "modify" (change existing), "create_new" (new operator), or "remove" (delete operator)
- If action is "modify" or "remove", set `target_file` to the relative path (e.g. "operators/local_move.py" or "policies/search_policy.py")
- Write a detailed `hypothesis_text` explaining the idea, the expected mechanism, and why it should improve results
- Set `target_weakness` to describe what current behaviour you are targeting
- Set `expected_effect` to describe the measurable improvement you expect
- Set `target_runtime_effect` to the expected runtime impact (improve/neutral/risk/unknown or short text)
- Set `complexity_claim` to the expected complexity, candidate scale, or loop bounds
- Set `runtime_budget_strategy` to how the operator will cap solve time (top-k, sampling, early exit, bounded neighborhood, etc.)

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
  "runtime_budget_strategy": "<runtime budget strategy or null>"
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

Respond with a single JSON object (no markdown fences, no extra text):
{{
  "file_path": "<relative path within workspace, e.g. operators/my_operator.py>",
  "action": "modify" | "create" | "delete",
  "code_content": "<complete file contents as a single string>",
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
  "file_path": "<same relative path as original>",
  "action": "modify" | "create" | "delete",
  "code_content": "<complete corrected file contents>",
  "test_hint": "<optional note, or null>"
}}
"""
