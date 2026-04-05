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

# ---------------------------------------------------------------------------
# Prompt templates
# Input slots follow §5.2 of scion-engineering-arch-v1.md
# ---------------------------------------------------------------------------

HYPOTHESIS_PROMPT_TEMPLATE = """\
You are a research agent optimising a VRP solver's operator pool.

## Problem
Name: {problem_name}
Operator categories: {operator_categories}

## Current champion operator pool
{pool_summary}

## Branch history (recent failed hypotheses on this branch)
{branch_history}

## Globally failed / blacklisted approaches (avoid repeating)
{blacklist_summary}

## Sibling branches currently exploring
{sibling_summary}

## Task
Propose ONE new hypothesis for improving the solver.
Choose a category from {operator_categories} as `change_locus`.
Set `action` to one of: "modify", "create_new", "remove".
If action is "modify" or "remove", provide `target_file`.
Explain your reasoning in `hypothesis_text`.

Respond with a single JSON object (no markdown fences) matching this schema:
{{
  "hypothesis_text": "<string>",
  "change_locus": "<string>",
  "action": "modify" | "create_new" | "remove",
  "target_file": "<string or null>",
  "predicted_direction": "improve" | "tradeoff" | "exploratory",
  "target_weakness": "<string>",
  "expected_effect": "<string>",
  "suggested_weight": <number or null>
}}
"""

CODE_PROMPT_TEMPLATE = """\
You are a software engineer implementing a VRP operator.

## Problem
Name: {problem_name}
Editable paths: {editable_patterns}
Frozen paths (DO NOT TOUCH): {frozen_patterns}
Allowed imports: {import_whitelist}

## Hypothesis to implement
{hypothesis_text}
Change locus: {change_locus}
Action: {action}
Target file: {target_file}

## Current champion code for reference
{champion_code}

## Required interface
All operator classes MUST implement:
    def execute(self, solution, rng):
        ...

## Task
Produce the complete file content that implements the hypothesis.
If action is "delete", set code_content to an empty string.

Respond with a single JSON object matching this schema:
{{
  "file_path": "<relative path within workspace>",
  "action": "modify" | "create" | "delete",
  "code_content": "<full file contents>",
  "test_hint": "<optional hint for testing, or null>"
}}
"""

FIX_PROMPT_TEMPLATE = """\
You are a software engineer fixing a failing VRP operator.

## Problem
Name: {problem_name}
Editable paths: {editable_patterns}
Frozen paths (DO NOT TOUCH): {frozen_patterns}
Allowed imports: {import_whitelist}

## Original patch that failed
File: {file_path}
Action: {action}
Code:
{code_content}

## Verification failure
Severity: {failure_severity}
First failure: {first_failure}
Details:
{failure_details}

## Task
Fix the code so it passes verification.
Preserve the operator interface: def execute(self, solution, rng).

Respond with a single JSON object matching this schema:
{{
  "file_path": "<relative path within workspace>",
  "action": "modify" | "create" | "delete",
  "code_content": "<full corrected file contents>",
  "test_hint": "<optional hint, or null>"
}}
"""
