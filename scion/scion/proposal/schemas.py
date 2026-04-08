"""JSON schemas and prompt templates for hypothesis and patch proposals."""
from __future__ import annotations

from typing import Any, Dict

# ---------------------------------------------------------------------------
# JSON Schemas
# ---------------------------------------------------------------------------

HYPOTHESIS_PROPOSAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["hypothesis_text", "change_locus", "action"],
    "properties": {
        "hypothesis_text": {"type": "string"},
        "change_locus": {"type": "string"},
        "action": {
            "type": "string",
            "enum": ["modify", "create_new", "remove"],
        },
        "target_file": {"type": ["string", "null"]},
        "predicted_direction": {
            "type": "string",
            "enum": ["improve", "tradeoff", "exploratory"],
        },
        "target_weakness": {"type": "string"},
        "expected_effect": {"type": "string"},
        "suggested_weight": {"type": ["number", "null"]},
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
    "description": "Propose a single hypothesis for improving the solver operator pool",
    "input_schema": HYPOTHESIS_PROPOSAL_SCHEMA,
}

PATCH_TOOL: Dict[str, Any] = {
    "name": "generate_patch",
    "description": "Generate a code patch implementing the approved hypothesis",
    "input_schema": PATCH_PROPOSAL_SCHEMA,
}

FIX_TOOL: Dict[str, Any] = {
    "name": "fix_patch",
    "description": "Fix a code patch that failed verification, preserving intended logic",
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
You are a software engineer implementing a VRP operator for a solver optimisation framework.
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
You are a software engineer fixing a VRP operator that failed verification.
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
