"""Patch proposal input models, typed edit schema, and prompt templates."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .shared import (
    _mechanism_changes_json_schema,
    _normalize_mechanism_changes_preflight,
    _validate_unique_mechanism_change_ids,
    MechanismChangeInput,
)

PatchEditIntent = Literal["exact_replace", "full_file"]
PremiseCheck = Literal["supported", "contradicted", "duplicate", "wrong_owner"]


class PatchFileChangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str
    action: str
    code_content: str = ""
    edit_intent: Optional[PatchEditIntent] = None
    source_digest: Optional[Any] = None
    old_string: Optional[str] = None
    new_string: Optional[str] = None
    replace_all: bool = False
    content_after: Optional[str] = None
    full_file_reason: Optional[str] = None
    derived_diff_ref: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)
    test_hint: Optional[str] = None

    @field_validator("file_path")
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

    @model_validator(mode="after")
    def validate_canonical_content(self) -> "PatchFileChangeInput":
        if self.content_after is not None and not self.code_content:
            self.code_content = self.content_after
        if self.action != "delete" and (
            not self.code_content or not self.code_content.strip()
        ):
            raise ValueError("code_content must not be empty")
        return self


class PatchProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    premise_check: PremiseCheck = "supported"
    premise_check_reason: str = ""
    file_path: str = ""
    action: str = "modify"
    code_content: str = ""
    edit_intent: Optional[PatchEditIntent] = None
    source_digest: Optional[Any] = None
    old_string: Optional[str] = None
    new_string: Optional[str] = None
    replace_all: bool = False
    content_after: Optional[str] = None
    full_file_reason: Optional[str] = None
    derived_diff_ref: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)
    test_hint: Optional[str] = None
    additional_changes: list[PatchFileChangeInput] = Field(default_factory=list)
    mechanism_changes: list[MechanismChangeInput] = Field(default_factory=list)

    @field_validator("mechanism_changes", mode="before")
    @classmethod
    def normalize_empty_mechanism_changes(cls, value: Any) -> Any:
        return _normalize_mechanism_changes_preflight(value)

    @field_validator("additional_changes", mode="before")
    @classmethod
    def parse_additional_changes_json_string(cls, value: Any) -> Any:
        if value in (None, ""):
            return []
        if not isinstance(value, str):
            return value
        raise ValueError(
            "additional_changes must be a JSON array, not a JSON-encoded string; "
            "retry by emitting the same edits as an array of objects."
        )

    @model_validator(mode="after")
    def validate_supported_patch_fields(self) -> "PatchProposalInput":
        if self.premise_check != "supported":
            return self
        if not self.file_path or not self.file_path.strip():
            raise ValueError("file_path must not be empty")
        if self.content_after is not None and not self.code_content:
            self.code_content = self.content_after
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


PATCH_PROPOSAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["file_path", "action"],
    "additionalProperties": False,
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
        "edit_intent": {
            "type": "string",
            "enum": ["exact_replace", "full_file"],
            "description": (
                "Default to exact_replace for action=modify on an existing "
                "file. Use full_file only for creates or deletes; "
                "host-visible existing-file modifies with full_file/content_after "
                "are rejected by default."
            ),
        },
        "source_digest": {
            "type": ["string", "object", "null"],
            "description": (
                "sha256 digest of the file content used for this edit. Required "
                "for exact_replace on existing files; null for create."
            ),
            "additionalProperties": True,
        },
        "old_string": {
            "type": ["string", "null"],
            "description": "Exact text to replace when edit_intent=exact_replace.",
        },
        "new_string": {
            "type": ["string", "null"],
            "description": (
                "Replacement text when edit_intent=exact_replace. May be empty."
            ),
        },
        "replace_all": {
            "type": "boolean",
            "description": (
                "For exact_replace, replace all matches. Otherwise old_string "
                "must occur exactly once."
            ),
        },
        "content_after": {
            "type": ["string", "null"],
            "description": (
                "Complete file content after a full_file edit. The host also "
                "fills this for exact_replace before Contract/Workspace."
            ),
        },
        "full_file_reason": {
            "type": ["string", "null"],
            "description": (
                "Brief note when edit_intent=full_file for create/delete. This "
                "is not authorization for existing-file modify. Omit or leave "
                "empty for exact_replace."
            ),
        },
        "code_content": {
            "type": "string",
            "description": (
                "Legacy complete file content. Supported for compatibility, "
                "but model-facing modify responses must use typed exact_replace; "
                "only creates/deletes may provide full content."
            ),
        },
        "derived_diff_ref": {
            "type": ["string", "null"],
            "description": "Host-generated audit diff reference; model may omit.",
        },
        "evidence_refs": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Observation or source evidence references supporting this file change."
            ),
        },
        "test_hint": {"type": ["string", "null"]},
        "additional_changes": {
            "type": "array",
            "description": (
                "Optional extra typed or full-file changes that are required "
                "for the approved algorithm change to be executable. Use this for "
                "solver_design module additions that also need scheduler or "
                "entrypoint integration. Each change is independently checked "
                "by Contract and applied in the same tainted candidate workspace. "
                "For multiple edits to one file, prefer one file change, or use "
                "serializable exact_replace typed edits for that same file_path. "
                "Do not emit conflicting full_file entries for the same file."
            ),
            "items": {
                "type": "object",
                "required": ["file_path", "action"],
                "properties": {
                    "file_path": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["modify", "create", "delete"],
                    },
                    "edit_intent": {
                        "type": "string",
                        "enum": ["exact_replace", "full_file"],
                    },
                    "source_digest": {
                        "type": ["string", "object", "null"],
                        "additionalProperties": True,
                    },
                    "old_string": {"type": ["string", "null"]},
                    "new_string": {"type": ["string", "null"]},
                    "replace_all": {"type": "boolean"},
                    "content_after": {"type": ["string", "null"]},
                    "full_file_reason": {"type": ["string", "null"]},
                    "code_content": {"type": "string"},
                    "derived_diff_ref": {"type": ["string", "null"]},
                    "evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "test_hint": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
        "mechanism_changes": _mechanism_changes_json_schema(),
    },
}


CODE_PROMPT_TEMPLATE = """\
You are a software engineer implementing a declared research surface for a combinatorial optimisation solver framework.
Your task is to submit typed file edits that implement the approved hypothesis below.

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
Produce a typed edit set that implements the hypothesis.
- Conform to the research-surface interface specification exactly
- Preserve all feasibility, consistency, and determinism invariants described there
- For operator surfaces, use the provided `rng` argument for all randomness and return the new solution/artifact, or original if no valid move found
- For policy surfaces, implement the required module-level functions and keep return values inside the documented bounds
- For existing `action="modify"` files, default to `edit_intent="exact_replace"`. Provide `source_digest`, exact `old_string`, `new_string`, `replace_all`, and `evidence_refs`.
- Use `edit_intent="full_file"` with `content_after` only for creates or deletes. Host-visible existing-file modifies that emit `full_file`/`content_after` are rejected by default; `full_file_reason` is not authorization.
- Legacy `code_content` full-file output is rejected for model-facing existing-file modifies; it is only accepted for creates/deletes or host-internal compatibility.
- Do not emit unified diffs; Scion derives audit diffs from host before/after content.
- If action is "delete", use `edit_intent="full_file"` and set `content_after` to an empty string ""
- If the approved algorithm change requires extra files to be executable, put
  them in `additional_changes`; each item may be exact_replace or full_file and
  will be independently checked.
- When one file needs multiple small edits, prefer a single file change or
  serializable `exact_replace` edits for the same `file_path`; each later
  `old_string` must match the content after earlier same-file edits. Do not
  emit conflicting `full_file` entries for the same file.
- Echo the approved hypothesis `mechanism_changes` ids exactly. Do not add or
  drop mechanism ids in the patch response.

Respond with a single JSON object (no markdown fences, no extra text):
{{
  "premise_check": "supported" | "contradicted" | "duplicate" | "wrong_owner",
  "premise_check_reason": "<brief reason when not supported, otherwise empty>",
  "file_path": "<relative path within workspace, e.g. operators/my_operator.py>",
  "action": "modify" | "create" | "delete",
  "edit_intent": "exact_replace" | "full_file",
  "source_digest": "<sha256 digest of current file content, or null for create>",
  "old_string": "<exact current text for exact_replace>",
  "new_string": "<replacement text for exact_replace>",
  "replace_all": false,
  "content_after": "<complete file contents for full_file, otherwise omit>",
  "full_file_reason": "<required when edit_intent is full_file, otherwise empty>",
  "evidence_refs": ["<observation/source ref>"],
  "additional_changes": [
    {{
      "file_path": "<relative path for required integration edit>",
      "action": "modify" | "create" | "delete",
      "edit_intent": "exact_replace" | "full_file",
      "source_digest": "<sha256 digest or null>",
      "old_string": "<exact current text>",
      "new_string": "<replacement text>",
      "replace_all": false,
      "content_after": "<complete file contents only for full_file>",
      "full_file_reason": "<required when edit_intent is full_file>",
      "evidence_refs": ["<observation/source ref>"]
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
Correct the code so it passes, while preserving the intended logic. Prefer a
small typed exact_replace edit when possible; use full_file only for creates or
deletes. full_file_reason is not authorization for existing-file modify.

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
  "edit_intent": "exact_replace" | "full_file",
  "source_digest": "<sha256 digest of current file content, or null for create>",
  "old_string": "<exact current text for exact_replace>",
  "new_string": "<replacement text for exact_replace>",
  "replace_all": false,
  "content_after": "<complete corrected file contents only for full_file>",
  "full_file_reason": "<required when edit_intent is full_file, otherwise empty>",
  "additional_changes": [],
  "test_hint": "<optional note, or null>"
}}
"""


__all__ = [
    "CODE_PROMPT_TEMPLATE",
    "FIX_PROMPT_TEMPLATE",
    "PATCH_PROPOSAL_SCHEMA",
    "PatchEditIntent",
    "PatchFileChangeInput",
    "PatchProposalInput",
    "PremiseCheck",
]
