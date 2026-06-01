"""Patch proposal input models, typed edit schema, and prompt templates."""

from __future__ import annotations

import json
from typing import Any, Dict, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .shared import (
    _mechanism_changes_json_schema,
    _normalize_mechanism_changes_preflight,
    _validate_unique_mechanism_change_ids,
    MechanismChangeInput,
)

PatchEditIntent = Literal["exact_replace", "full_file"]
PremiseCheck = Literal["supported", "contradicted", "duplicate", "wrong_owner"]


class PatchSchemaPreflightError(ValueError):
    """Raised when patch JSON shape fails before typed-edit normalization."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = dict(payload)
        super().__init__(
            json.dumps(self.payload, sort_keys=True, separators=(",", ":"))
        )


def preflight_patch_exact_replace_shape(raw: Mapping[str, Any]) -> None:
    """Reject malformed exact_replace edit selectors before normalization."""

    if raw.get("premise_check") not in (None, "", "supported"):
        return
    for change_pointer, change in _patch_change_slots(raw):
        if str(change.get("edit_intent") or "").strip() != "exact_replace":
            continue
        file_path = str(change.get("file_path") or "").strip()
        _require_source_digest(change, file_path, change_pointer)
        _require_old_string(change, file_path, change_pointer)
        _require_new_string(change, file_path, change_pointer)


def _patch_change_slots(
    raw: Mapping[str, Any],
) -> list[tuple[str, Mapping[str, Any]]]:
    slots: list[tuple[str, Mapping[str, Any]]] = [("/", raw)]
    additional = raw.get("additional_changes")
    if not isinstance(additional, list):
        return slots
    for index, item in enumerate(additional):
        if isinstance(item, Mapping):
            slots.append((f"/additional_changes/{index}", item))
    return slots


def _require_source_digest(
    change: Mapping[str, Any],
    file_path: str,
    change_pointer: str,
) -> None:
    if _source_digest_text(change.get("source_digest")):
        return
    reason = (
        "exact_replace_missing_source_digest"
        if "source_digest" not in change
        else "exact_replace_empty_source_digest"
    )
    _raise_exact_replace_shape_error(
        reason=reason,
        field="source_digest",
        file_path=file_path,
        change_pointer=change_pointer,
        detail=(
            "exact_replace requires source_digest for the existing file. "
            "Use the host-provided sha256 digest for that file."
        ),
    )


def _require_old_string(
    change: Mapping[str, Any],
    file_path: str,
    change_pointer: str,
) -> None:
    if "old_string" not in change:
        _raise_exact_replace_shape_error(
            reason="exact_replace_missing_old_string",
            field="old_string",
            file_path=file_path,
            change_pointer=change_pointer,
            detail=(
                "exact_replace requires old_string to be present as a "
                "non-empty string copied exactly from the current file."
            ),
        )
    old_string = change.get("old_string")
    if isinstance(old_string, str) and old_string != "":
        return
    if old_string is None:
        reason = "exact_replace_null_old_string"
        detail = (
            "exact_replace old_string must be a non-empty string, not null."
        )
    elif isinstance(old_string, str):
        reason = "exact_replace_empty_old_string"
        detail = (
            "exact_replace old_string must be a non-empty string copied "
            "exactly from the current file."
        )
    else:
        reason = "exact_replace_non_string_old_string"
        detail = (
            "exact_replace old_string must be a string copied exactly from "
            "the current file."
        )
    _raise_exact_replace_shape_error(
        reason=reason,
        field="old_string",
        file_path=file_path,
        change_pointer=change_pointer,
        detail=detail,
    )


def _require_new_string(
    change: Mapping[str, Any],
    file_path: str,
    change_pointer: str,
) -> None:
    if "new_string" not in change:
        _raise_exact_replace_shape_error(
            reason="exact_replace_missing_new_string",
            field="new_string",
            file_path=file_path,
            change_pointer=change_pointer,
            detail=(
                "exact_replace requires new_string to be present as a string. "
                "For deletion, set new_string to the empty string \"\"; do "
                "not omit the field."
            ),
        )
    new_string = change.get("new_string")
    if isinstance(new_string, str):
        return
    if new_string is None:
        reason = "exact_replace_null_new_string"
        detail = (
            "exact_replace new_string must be a string, not null. For "
            "deletion, set new_string to the empty string \"\"."
        )
    else:
        reason = "exact_replace_non_string_new_string"
        detail = (
            "exact_replace new_string must be a string. For deletion, set "
            "new_string to the empty string \"\"."
        )
    _raise_exact_replace_shape_error(
        reason=reason,
        field="new_string",
        file_path=file_path,
        change_pointer=change_pointer,
        detail=detail,
    )


def _raise_exact_replace_shape_error(
    *,
    reason: str,
    field: str,
    file_path: str,
    change_pointer: str,
    detail: str,
) -> None:
    field_pointer = (
        f"/{field}" if change_pointer == "/" else f"{change_pointer}/{field}"
    )
    minimal_shape = {
        "file_path": file_path or "<same relative path>",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": "<host-provided sha256 digest>",
        "old_string": "<non-empty exact current text>",
        "new_string": "<replacement text; use \"\" for deletion>",
        "replace_all": False,
    }
    payload = {
        "error": "patch_edit_protocol",
        "stage": "schema_preflight",
        "reason": reason,
        "field": field,
        "file_path": file_path,
        "json_pointer": field_pointer,
        "change_pointer": change_pointer,
        "edit_intent": "exact_replace",
        "detail": detail,
        "guidance": (
            "Retry with a complete typed exact_replace object. Minimal JSON "
            "shape: action='modify', edit_intent='exact_replace', "
            "source_digest='<host-provided sha256 digest>', "
            "old_string='<non-empty exact current text>', "
            "new_string='<replacement text>', replace_all=false. For deletion "
            "use new_string: \"\"; never omit new_string or set it to null."
        ),
        "minimal_json_shape": minimal_shape,
    }
    raise PatchSchemaPreflightError(payload)


def _source_digest_text(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ("sha256", "digest", "source_digest"):
            text = str(value.get(key) or "").strip()
            if text:
                return _strip_digest_prefix(text)
        return ""
    if value is None:
        return ""
    return _strip_digest_prefix(str(value).strip())


def _strip_digest_prefix(value: str) -> str:
    return value[7:] if value.startswith("sha256:") else value


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
                "are rejected by default. Existing files must not use create "
                "or create_new/full_file as a modification path."
            ),
        },
        "source_digest": {
            "type": ["string", "object", "null"],
            "description": (
                "sha256 digest of the file content used for this edit. Required "
                "and non-empty for exact_replace on existing files; null only "
                "for create/full_file edits to new files."
            ),
            "additionalProperties": True,
        },
        "old_string": {
            "type": "string",
            "description": (
                "Exact non-empty text to replace when "
                "edit_intent=exact_replace. Omit or use an empty string for "
                "full_file/create; never use null."
            ),
        },
        "new_string": {
            "type": "string",
            "description": (
                "Replacement text when edit_intent=exact_replace. Must be "
                "present as a string; use an empty string for deletion, never "
                "null or a missing field."
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
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
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
- For existing-file `exact_replace`, keep `old_string` scoped to a function,
  import block, registry entry, or local code block. Host preflight rejects
  whole-file and near-whole-file selectors (hard limit 85% of files over 2000
  chars); aim for each `old_string` to stay under 35% of the file.
- For `exact_replace`, `old_string` must be a non-empty string and `new_string` must be present as a string. To delete text, set `new_string` to `""`; do not omit it or set it to null.
- Use `edit_intent="full_file"` with `content_after` only for creates or deletes. Host-visible existing-file modifies that emit `full_file`/`content_after` are rejected by default; `full_file_reason` is not authorization.
- Existing files must never be changed through `action="create"`, `create_new`, or `full_file`; existing file requires `action="modify"` with `edit_intent="exact_replace"` and `source_digest`. Create/full content is only for genuinely new files.
- Legacy `code_content` full-file output is rejected for model-facing existing-file modifies; it is only accepted for creates/deletes or host-internal compatibility.
- Do not emit unified diffs; Scion derives audit diffs from host before/after content.
- If action is "delete", use `edit_intent="full_file"` and set `content_after` to an empty string ""
- If the approved algorithm change requires extra files to be executable, put
  them in `additional_changes`; each item may be exact_replace or full_file and
  will be independently checked.
- When one file needs multiple small edits, prefer a single file change or
  serializable `exact_replace` edits for the same `file_path`; each later
  `old_string` must match the content after earlier same-file edits. Do not
  emit no-op `exact_replace` entries such as `old_string == new_string` or
  EOF/trailing newline edits. Do not emit conflicting `full_file` entries for
  the same file.
- Echo the approved hypothesis `mechanism_changes` ids exactly. Do not add or
  drop mechanism ids in the patch response.
- `premise_check="duplicate"` is diagnostic only. Use it to disclose close
  overlap with visible code, but still provide the typed edit when the approved
  hypothesis is a material variant. Do not use `contradicted` for novelty,
  duplicate-risk, near-existing mechanism, or baseline-already-has-similar-
  capability observations. Only hard boundary/objective-policy/protected-
  constraint contradictions and `wrong_owner` are no-patch premise outcomes.

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
For exact_replace, include source_digest, non-empty old_string, and new_string
as a string. Use new_string "" for deletion; never omit it or set it to null.

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
    "PatchSchemaPreflightError",
    "PatchEditIntent",
    "PatchFileChangeInput",
    "PatchProposalInput",
    "PremiseCheck",
    "preflight_patch_exact_replace_shape",
]
