"""JSON schemas and prompt templates for hypothesis and patch proposals."""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Pydantic v2 validation models (T19)
# ---------------------------------------------------------------------------

class HypothesisProposalInput(BaseModel):
    hypothesis_text: str
    change_locus: str
    action: str
    target_file: Optional[str] = None
    predicted_direction: str = "exploratory"
    target_weakness: str = ""
    expected_effect: str = ""
    suggested_weight: Optional[float] = None

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

# ---------------------------------------------------------------------------
# JSON Schemas
# ---------------------------------------------------------------------------

HYPOTHESIS_PROPOSAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["hypothesis_text", "change_locus", "action"],
    "properties": {
        "hypothesis_text": {
            "type": "string",
            "description": "3-5 sentences. What the operator does, why it differs from existing ones, expected mechanism of improvement. No generic filler.",
        },
        "change_locus": {
            "type": "string",
            "description": "Which operator category: order_level or vehicle_level.",
        },
        "action": {
            "type": "string",
            "enum": ["modify", "create_new", "remove"],
            "description": "modify: improve existing operator. create_new: add a new one. remove: drop a weak one.",
        },
        "target_file": {
            "type": ["string", "null"],
            "description": "For modify/remove: the operator file path (e.g. operators/move_order.py). For create_new: the new file path.",
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
            "description": "Concrete expected outcome: e.g. 'reduce splits by consolidating same-subcategory vehicles'.",
        },
        "suggested_weight": {
            "type": ["number", "null"],
            "description": "Operator weight (0.1-3.0). Use 0.5-1.0 for unproven new operators.",
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

# Tool definitions for tool_use mode (avoids JSON escape issues)
HYPOTHESIS_TOOL: Dict[str, Any] = {
    "name": "generate_hypothesis",
    "description": (
        "Propose ONE novel hypothesis for improving the VNS solver's operator pool.\n\n"
        "Usage:\n"
        "- Study ALL existing champion operators before proposing \u2014 avoid duplicating existing logic.\n"
        "- Check experiment history for approaches that already failed \u2014 do NOT repeat them.\n"
        "- Check sibling branches to avoid redundant exploration.\n\n"
        "Quality criteria:\n"
        "- Target a specific, named weakness in the current pool (not vague 'improvements').\n"
        "- The mechanism of improvement must be concrete and testable.\n"
        "- Consider the solver's execution model: your operator runs ~1000 times per solve, "
        "high variance is good, rare great outcomes beat frequent mediocre ones.\n"
        "- Prefer operators that provide a CAPABILITY the pool currently LACKS.\n\n"
        "Common mistakes to avoid:\n"
        "- Proposing random order moves between arbitrary vehicles (unlikely to improve splits).\n"
        "- Ignoring feasibility constraints (your operator MUST produce feasible solutions).\n"
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
        "- Study the champion operator code for style, data model usage, and import patterns.\n"
        "- Follow the operator interface EXACTLY: subclass Operator, implement execute(self, solution, rng) -> Solution.\n\n"
        "Code quality requirements:\n"
        "- Deep-copy the solution FIRST: `new_sol = solution.deep_copy()`.\n"
        "- Skip locked orders: check `order.locked_vehicle_id is not None`.\n"
        "- Use `rng` for ALL randomness \u2014 do NOT import random directly.\n"
        "- NEVER use `list(set(...))` or iterate over set/dict in order-dependent ways \u2014 "
        "use `sorted()` for determinism.\n"
        "- Call `new_sol.remove_empty_vehicles()` before returning.\n"
        "- Maintain assignment dict consistency: update BOTH vehicle.order_ids and solution.assignment.\n\n"
        "Common rejection causes:\n"
        "- Feasibility violation: dropping or duplicating orders.\n"
        "- Non-determinism: iterating over sets without sorting.\n"
        "- Import violation: using modules not in the whitelist.\n"
        "- Interface mismatch: wrong method signature or missing deep copy."
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
        "- V3_feasibility: assignment dict and vehicle.order_ids inconsistent.\n"
        "- V5_solution_consistency: output solution has assignment/vehicle mismatch or missing/duplicate orders.\n"
        "- V8_nondeterminism: non-deterministic code (no uuid, use sorted(), use rng).\n"
        "- V1_syntax: indentation, parentheses, colons.\n"
        "- V2_interface: missing Operator base class or wrong execute() signature."
    ),
    "input_schema": PATCH_PROPOSAL_SCHEMA,
}

# ---------------------------------------------------------------------------
# Prompt templates
# Input slots follow §5.2 of scion-engineering-arch-v1.md.
# Section-level placeholders avoid field-level fragility.
# ---------------------------------------------------------------------------

HYPOTHESIS_PROMPT_TEMPLATE = """\
You are a research agent optimising a combinatorial optimisation solver's operator pool.
Your goal is to propose ONE novel hypothesis that, if implemented, would improve solver quality.

## Problem Summary
{problem_summary}

## Current Champion Operator Code
The following operators make up the current champion solution.
Study them carefully before proposing anything — avoid duplicating existing logic.

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
Propose ONE hypothesis for improving the solver's operator pool.
- Set `change_locus` to one of: {operator_categories}
- Set `action` to: "modify" (change existing), "create_new" (new operator), or "remove" (delete operator)
- If action is "modify" or "remove", set `target_file` to the relative path (e.g. "operators/swap_orders.py")
- Write a detailed `hypothesis_text` explaining the idea, the expected mechanism, and why it should improve results
- Set `target_weakness` to describe what current behaviour you are targeting
- Set `expected_effect` to describe the measurable improvement you expect

Respond with a single JSON object (no markdown fences, no extra text) matching this schema:
{{
  "hypothesis_text": "<detailed explanation of the idea>",
  "change_locus": "<one of the operator categories>",
  "action": "modify" | "create_new" | "remove",
  "target_file": "<relative path or null>",
  "predicted_direction": "improve" | "tradeoff" | "exploratory",
  "target_weakness": "<what current weakness this addresses>",
  "expected_effect": "<expected measurable improvement>",
  "suggested_weight": <sampling weight 0.0–1.0 or null>
}}
"""

CODE_PROMPT_TEMPLATE = """\
You are a software engineer implementing a vehicle-assignment operator for a solver optimisation framework.
Your task is to write the complete file contents that implement the approved hypothesis below.

## Problem Summary
{problem_summary}

## Hypothesis to Implement
{hypothesis_detail}

## Current Champion Operator Code
Study these implementations for coding style, data model usage, and patterns:

{champion_operators_code}

## Target File (current content — modify this if action is "modify")
{target_file_code}

## Reference Operators (same category — use as style guide)
{reference_operators}

## Operator Interface Specification
All operator classes MUST conform to this interface exactly:

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
- Subclass `Operator` and implement `execute(self, solution, rng) -> Solution`
- Deep-copy the solution at the start: `new_sol = solution.deep_copy()`
- Skip locked orders (where `order.locked_vehicle_id is not None`)
- Use `rng` for all randomness
- Return the new solution (or original if no valid move found)
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
You are a software engineer fixing a vehicle-assignment operator that failed verification.
Correct the code so it passes, while preserving the intended logic.

## Problem Summary
{problem_summary}

## Original Code That Failed
{original_code}

## Verification Failure Details
{failure_detail}

## Operator Interface Specification
{operator_interface_spec}

## Allowed Imports
{import_whitelist}

## Editable Paths
{editable_patterns}

## Frozen Paths (DO NOT MODIFY)
{frozen_patterns}

## Task
Fix the code so it passes verification.
Preserve the operator interface: `def execute(self, solution, rng) -> Solution`.
Make only the minimal changes needed to fix the reported failure.

Respond with a single JSON object (no markdown fences, no extra text):
{{
  "file_path": "<same relative path as original>",
  "action": "modify" | "create" | "delete",
  "code_content": "<complete corrected file contents>",
  "test_hint": "<optional note, or null>"
}}
"""
