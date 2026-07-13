"""Patch proposal input models, typed edit schema, and prompt templates."""

from __future__ import annotations

import json
from typing import Any, Dict, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PatchEditIntent = Literal["exact_replace", "full_file"]


class PatchSchemaPreflightError(ValueError):
    """Raised when patch JSON shape fails before typed-edit normalization."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = dict(payload)
        super().__init__(
            json.dumps(self.payload, sort_keys=True, separators=(",", ":"))
        )


def preflight_patch_exact_replace_shape(raw: Mapping[str, Any]) -> None:
    """Reject malformed exact_replace edit selectors before normalization."""

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
            "A complete typed exact_replace object has this minimal JSON "
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
        duplicates = sorted(
            {path for path in normalized if normalized.count(path) > 1}
        )
        if duplicates:
            raise ValueError(
                "additional_changes must not repeat file_path values: "
                + ", ".join(duplicates)
            )
        return self


PATCH_PROPOSAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["file_path", "action"],
    "additionalProperties": False,
    "properties": {
        "file_path": {"type": "string"},
        "action": {
            "type": "string",
            "enum": ["modify", "create", "delete"],
        },
        "edit_intent": {
            "type": "string",
            "enum": ["exact_replace", "full_file"],
            "description": (
                "Existing files use action=modify with the current source_digest. "
                "Choose exact_replace or explicit full_file/content_after based "
                "on the algorithm change; create is only for new files."
            ),
        },
        "source_digest": {
            "type": ["string", "object", "null"],
            "description": (
                "sha256 digest of the file content used for this edit. Required "
                "and non-empty for every existing-file modify; null only for "
                "creates of new files."
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
                    "evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "test_hint": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
    },
}
__all__ = [
    "PATCH_PROPOSAL_SCHEMA",
    "PatchSchemaPreflightError",
    "PatchEditIntent",
    "PatchFileChangeInput",
    "PatchProposalInput",
    "preflight_patch_exact_replace_shape",
]
