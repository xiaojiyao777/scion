"""Patch proposal input models, typed edit schema, and prompt templates."""

from __future__ import annotations

import json
from typing import Any, Dict, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PatchEditIntent = Literal["exact_replace", "exact_line_replace", "full_file"]


class PatchSchemaPreflightError(ValueError):
    """Raised when patch JSON shape fails before typed-edit normalization."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = dict(payload)
        super().__init__(
            json.dumps(self.payload, sort_keys=True, separators=(",", ":"))
        )


def preflight_patch_exact_replace_shape(raw: Mapping[str, Any]) -> None:
    """Reject malformed source-bound edit selectors before normalization."""

    for change_pointer, change in _patch_change_slots(raw):
        edit_intent = str(change.get("edit_intent") or "").strip()
        if edit_intent not in {"exact_replace", "exact_line_replace"}:
            continue
        file_path = str(change.get("file_path") or "").strip()
        _require_old_string(
            change,
            file_path,
            change_pointer,
            edit_intent=edit_intent,
        )
        _require_new_string(
            change,
            file_path,
            change_pointer,
            edit_intent=edit_intent,
        )
        if edit_intent == "exact_line_replace":
            _validate_exact_line_replace_shape(
                change,
                file_path=file_path,
                change_pointer=change_pointer,
            )


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


def _require_old_string(
    change: Mapping[str, Any],
    file_path: str,
    change_pointer: str,
    *,
    edit_intent: str = "exact_replace",
) -> None:
    if "old_string" not in change:
        _raise_exact_replace_shape_error(
            reason=f"{edit_intent}_missing_old_string",
            field="old_string",
            file_path=file_path,
            change_pointer=change_pointer,
            edit_intent=edit_intent,
            detail=(
                f"{edit_intent} requires old_string to be present as a "
                "non-empty string copied exactly from the current file."
            ),
        )
    old_string = change.get("old_string")
    if isinstance(old_string, str) and old_string != "":
        return
    if old_string is None:
        reason = f"{edit_intent}_null_old_string"
        detail = f"{edit_intent} old_string must be a non-empty string, not null."
    elif isinstance(old_string, str):
        reason = f"{edit_intent}_empty_old_string"
        detail = (
            f"{edit_intent} old_string must be a non-empty string copied "
            "exactly from the current file."
        )
    else:
        reason = f"{edit_intent}_non_string_old_string"
        detail = (
            f"{edit_intent} old_string must be a string copied exactly from "
            "the current file."
        )
    _raise_exact_replace_shape_error(
        reason=reason,
        field="old_string",
        file_path=file_path,
        change_pointer=change_pointer,
        edit_intent=edit_intent,
        detail=detail,
    )


def _require_new_string(
    change: Mapping[str, Any],
    file_path: str,
    change_pointer: str,
    *,
    edit_intent: str = "exact_replace",
) -> None:
    if "new_string" not in change:
        _raise_exact_replace_shape_error(
            reason=f"{edit_intent}_missing_new_string",
            field="new_string",
            file_path=file_path,
            change_pointer=change_pointer,
            edit_intent=edit_intent,
            detail=(
                f"{edit_intent} requires new_string to be present as a string. "
                'For deletion, set new_string to the empty string ""; do '
                "not omit the field."
            ),
        )
    new_string = change.get("new_string")
    if isinstance(new_string, str):
        return
    if new_string is None:
        reason = f"{edit_intent}_null_new_string"
        detail = (
            f"{edit_intent} new_string must be a string, not null. For "
            'deletion, set new_string to the empty string "".'
        )
    else:
        reason = f"{edit_intent}_non_string_new_string"
        detail = (
            f"{edit_intent} new_string must be a string. For deletion, set "
            'new_string to the empty string "".'
        )
    _raise_exact_replace_shape_error(
        reason=reason,
        field="new_string",
        file_path=file_path,
        change_pointer=change_pointer,
        edit_intent=edit_intent,
        detail=detail,
    )


def _validate_exact_line_replace_shape(
    change: Mapping[str, Any],
    *,
    file_path: str,
    change_pointer: str,
) -> None:
    old_string = change.get("old_string")
    new_string = change.get("new_string")
    assert isinstance(old_string, str)
    assert isinstance(new_string, str)
    if "\r" in old_string or "\n" in old_string:
        _raise_exact_replace_shape_error(
            reason="exact_line_replace_multiline_old_string",
            field="old_string",
            file_path=file_path,
            change_pointer=change_pointer,
            edit_intent="exact_line_replace",
            detail=(
                "exact_line_replace old_string must contain exactly one "
                "logical-line body without a line ending."
            ),
        )
    if old_string.startswith((" ", "\t")):
        _raise_exact_replace_shape_error(
            reason="exact_line_replace_indented_old_string",
            field="old_string",
            file_path=file_path,
            change_pointer=change_pointer,
            edit_intent="exact_line_replace",
            detail=(
                "exact_line_replace old_string must omit leading indentation; "
                "the host captures it from each complete-line match."
            ),
        )
    if "\r" in new_string:
        _raise_exact_replace_shape_error(
            reason="exact_line_replace_cr_in_new_string",
            field="new_string",
            file_path=file_path,
            change_pointer=change_pointer,
            edit_intent="exact_line_replace",
            detail="exact_line_replace new_string must use LF separators only.",
        )
    if new_string and new_string.endswith("\n"):
        _raise_exact_replace_shape_error(
            reason="exact_line_replace_terminal_lf_in_new_string",
            field="new_string",
            file_path=file_path,
            change_pointer=change_pointer,
            edit_intent="exact_line_replace",
            detail=(
                "exact_line_replace new_string must omit the terminal line "
                "ending because the host preserves the matched source EOL."
            ),
        )


def _raise_exact_replace_shape_error(
    *,
    reason: str,
    field: str,
    file_path: str,
    change_pointer: str,
    edit_intent: str = "exact_replace",
    detail: str,
) -> None:
    field_pointer = (
        f"/{field}" if change_pointer == "/" else f"{change_pointer}/{field}"
    )
    minimal_shape = {
        "file_path": file_path or "<same relative path>",
        "action": "modify",
        "edit_intent": edit_intent,
        "old_string": "<non-empty exact current text>",
        "new_string": '<replacement text; use "" for deletion>',
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
        "edit_intent": edit_intent,
        "detail": detail,
        "guidance": (
            f"A complete typed {edit_intent} object has this minimal JSON "
            f"shape: action='modify', edit_intent='{edit_intent}', "
            "old_string='<non-empty exact current text>', "
            "new_string='<replacement text>', replace_all=false. For deletion "
            'use new_string: ""; never omit new_string or set it to null.'
        ),
        "minimal_json_shape": minimal_shape,
    }
    raise PatchSchemaPreflightError(payload)


class PatchFileChangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str
    action: str
    code_content: str = ""
    edit_intent: PatchEditIntent
    old_string: Optional[str] = None
    new_string: Optional[str] = None
    replace_all: bool = False
    content_after: Optional[str] = None
    full_file_reason: Optional[str] = None
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

    file_path: str = ""
    action: str = "modify"
    code_content: str = ""
    edit_intent: PatchEditIntent
    old_string: Optional[str] = None
    new_string: Optional[str] = None
    replace_all: bool = False
    content_after: Optional[str] = None
    full_file_reason: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)
    test_hint: Optional[str] = None
    additional_changes: list[PatchFileChangeInput] = Field(default_factory=list)

    @field_validator("additional_changes", mode="before")
    @classmethod
    def parse_additional_changes_json_string(cls, value: Any) -> Any:
        if value in (None, ""):
            return []
        if not isinstance(value, str):
            return value
        raise ValueError(
            "additional_changes must be a JSON array, not a JSON-encoded string."
        )

    @model_validator(mode="after")
    def validate_supported_patch_fields(self) -> "PatchProposalInput":
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
        duplicates = sorted({path for path in normalized if normalized.count(path) > 1})
        if duplicates:
            raise ValueError(
                "additional_changes must not repeat file_path values: "
                + ", ".join(duplicates)
            )
        return self


EXACT_LINE_REPLACE_EXAMPLE: Dict[str, Any] = {
    "file_path": "module.py",
    "action": "modify",
    "edit_intent": "exact_line_replace",
    "old_string": "worker.advance()",
    "new_string": "worker.advance(progress)",
    "replace_all": True,
}

_ADDITIONAL_CHANGES_DESCRIPTION = (
    "Optional extra typed or full-file changes that are required for the "
    "approved algorithm change to be executable. Use this for solver_design "
    "module additions that also need scheduler or entrypoint integration. Each "
    "change is independently checked by Contract and applied in the same "
    "tainted candidate workspace. Each file_path may appear exactly once. "
    "Express all intended changes to one file in that single typed edit; the "
    "host rejects duplicate paths and never composes model outputs."
)


def _patch_change_properties() -> Dict[str, Any]:
    """Return the identical flat change-field schema for root and nested edits."""

    return {
        "file_path": {
            "type": "string",
            "description": "Repository-relative path for this file change.",
        },
        "action": {
            "type": "string",
            "enum": ["modify", "create", "delete"],
            "description": (
                "Use modify for an existing file, create for a new file, or "
                "delete to remove an existing file."
            ),
        },
        "edit_intent": {
            "type": "string",
            "enum": ["exact_replace", "exact_line_replace", "full_file"],
            "description": (
                "Choose exact_replace for an exact source block whose indentation "
                "is part of the selector. Choose exact_line_replace when the "
                "identical complete logical-line body repeats at different outer "
                "indentation depths. Choose full_file for creates, broad rewrites, "
                "or an edit with no stable exact selector. The host binds "
                "modifications to the current visible source."
            ),
        },
        "old_string": {
            "type": "string",
            "description": (
                "Exact non-empty selector. For exact_replace, copy exact source "
                "text. For exact_line_replace, provide one complete logical-line "
                "body with no leading indentation or line ending. Omit or use an "
                "empty string for full_file/create; never use null."
            ),
        },
        "new_string": {
            "type": "string",
            "description": (
                "Replacement text for exact_replace, or an LF-separated "
                "relative-indentation block for exact_line_replace. The latter "
                "must omit its terminal line ending. For either localized intent, "
                "this field must be present as a string; use an empty string for "
                "deletion, never null or a missing field."
            ),
        },
        "replace_all": {
            "type": "boolean",
            "description": (
                "For exact_replace or exact_line_replace, set true to replace all "
                "matches. Set false when old_string must match exactly once."
            ),
        },
        "content_after": {
            "type": ["string", "null"],
            "description": (
                "Complete file content after a full_file edit. The host also fills "
                "this for localized edits before Contract and Workspace."
            ),
        },
        "full_file_reason": {
            "type": ["string", "null"],
            "description": (
                "Optional explanation of why the approved algorithm change is "
                "best expressed as a full-file edit."
            ),
        },
        "evidence_refs": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Observation or source evidence references supporting this file change."
            ),
        },
        "test_hint": {
            "type": ["string", "null"],
            "description": (
                "Optional concise test idea for the behavior changed in this file."
            ),
        },
    }


def _edit_intent_all_of() -> list[Dict[str, Any]]:
    """Describe the three required explicit edit intents."""

    localized_required = ["edit_intent", "old_string", "new_string"]
    return [
        {
            "oneOf": [
                {
                    "title": "Exact source-span replacement",
                    "properties": {
                        "action": {"enum": ["modify"]},
                        "edit_intent": {"enum": ["exact_replace"]},
                    },
                    "required": list(localized_required),
                },
                {
                    "title": "Indentation-neutral exact-line replacement",
                    "description": (
                        "The example illustrates only the JSON shape for one "
                        "unindented repeated logical-line selector applied at "
                        "every indentation depth with replace_all=true; it "
                        "does not require this edit intent."
                    ),
                    "properties": {
                        "action": {"enum": ["modify"]},
                        "edit_intent": {"enum": ["exact_line_replace"]},
                    },
                    "required": list(localized_required),
                    "examples": [dict(EXACT_LINE_REPLACE_EXAMPLE)],
                },
                {
                    "title": "Complete-file creation or modification",
                    "properties": {
                        "action": {"enum": ["modify", "create"]},
                        "edit_intent": {"enum": ["full_file"]},
                        "content_after": {"type": "string"},
                    },
                    "required": ["edit_intent", "content_after"],
                },
                {
                    "title": "Typed file deletion",
                    "properties": {
                        "action": {"enum": ["delete"]},
                        "edit_intent": {"enum": ["full_file"]},
                    },
                    "required": ["edit_intent"],
                },
            ],
        }
    ]


def _patch_change_schema() -> Dict[str, Any]:
    """Build one flat file-change schema used at both wire nesting levels."""

    return {
        "type": "object",
        "required": ["file_path", "action", "edit_intent"],
        "additionalProperties": False,
        "properties": _patch_change_properties(),
        "allOf": _edit_intent_all_of(),
    }


PATCH_PROPOSAL_SCHEMA: Dict[str, Any] = _patch_change_schema()
PATCH_PROPOSAL_SCHEMA["properties"]["additional_changes"] = {
    "type": "array",
    "description": _ADDITIONAL_CHANGES_DESCRIPTION,
    "items": _patch_change_schema(),
}
__all__ = [
    "PATCH_PROPOSAL_SCHEMA",
    "EXACT_LINE_REPLACE_EXAMPLE",
    "PatchSchemaPreflightError",
    "PatchEditIntent",
    "PatchFileChangeInput",
    "PatchProposalInput",
    "preflight_patch_exact_replace_shape",
]
