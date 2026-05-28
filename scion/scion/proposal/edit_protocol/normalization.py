"""Normalize model-facing typed edits into canonical full-file patch content."""

from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from scion.proposal.schemas.patch import (
    PatchSchemaPreflightError,
    preflight_patch_exact_replace_shape,
)


_SOURCE_FILE_RE = re.compile(
    r"^(?:###\s+|File:\s*)(?P<path>[^\n]+?)"
    r"(?:\s+\([^\n]*\))?\n"
    r"(?:[^\n]*\n)*?"
    r"```(?:python|py)?\n"
    r"(?P<content>.*?)"
    r"(?P<terminal_newline>\n)```",
    re.DOTALL | re.MULTILINE,
)

_FENCED_SOURCE_RE = re.compile(
    r"^\s*```(?:python|py)?\n(?P<content>.*?)(?P<terminal_newline>\n)```\s*$",
    re.DOTALL,
)

_LOOSE_FILE_SOURCE_RE = re.compile(
    r"^\s*File:\s*(?P<path>[^\n]+?)\n```(?:python|py)?\n(?P<content>.*)\Z",
    re.DOTALL,
)

_NEAR_WHOLE_FILE_EXACT_REPLACE_MIN_CHARS = 2000
_NEAR_WHOLE_FILE_EXACT_REPLACE_MAX_COVERAGE = 0.85
_RECOMMENDED_EXACT_REPLACE_MAX_COVERAGE = 0.35


class PatchEditProtocolError(ValueError):
    """Raised when a typed edit cannot be safely normalized."""


@dataclass
class _ChangeSlot:
    pointer: str
    raw: Mapping[str, Any]
    is_primary: bool
    additional_index: int | None = None


@dataclass
class _ComposedChange:
    path: str
    canonical_slot: _ChangeSlot
    change: dict[str, Any]
    json_pointers: list[str] = field(default_factory=list)
    intents: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _SourceRecord:
    content: str
    provenance: str

    @property
    def digest(self) -> str:
        return source_digest_for_content(self.content)


def normalize_patch_typed_edits(
    raw: Mapping[str, Any],
    *,
    context: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Return a full-content patch payload plus host-derived audit metadata.

    The proposal protocol lets the model submit small typed edits. Existing
    Scion Contract/Workspace code still consumes full file contents, so this
    function is the compatibility boundary: it validates typed edit
    preconditions, applies exact replacements to the host-visible source, and
    writes canonical ``code_content`` values before Pydantic parsing.
    """

    normalized = dict(raw)
    if normalized.get("premise_check") not in (None, "", "supported"):
        return normalized, ()
    try:
        preflight_patch_exact_replace_shape(normalized)
    except PatchSchemaPreflightError as exc:
        raise PatchEditProtocolError(str(exc)) from exc

    source_records = _source_records_from_context(
        context,
        requested_paths=_patch_requested_paths(normalized),
    )
    source_files = {
        path: record.content for path, record in source_records.items()
    }
    source_provenance = {
        path: record.provenance for path, record in source_records.items()
    }
    reject_legacy_code_content = bool(
        (context or {}).get("reject_legacy_code_content_full_file_modify")
    )
    allow_host_internal_full_file_modify = bool(
        (context or {}).get("allow_host_internal_full_file_modify")
    )
    normalized, metadata = _normalize_patch_set_changes(
        normalized,
        source_files=source_files,
        source_provenance=source_provenance,
        reject_legacy_code_content=reject_legacy_code_content,
        allow_host_internal_full_file_modify=allow_host_internal_full_file_modify,
    )

    return normalized, tuple(metadata)


def build_patch_edit_source_manifest(context: Mapping[str, Any]) -> str:
    """Render compact source digests for model-facing typed edit prompts."""

    source_records = _source_records_from_context(context)
    if not source_records:
        return "(no editable source digests available)"
    lines = [
        (
            "Use these canonical sha256 source_digest values for "
            "exact_replace edits. For create actions use null. Each record "
            "also lists the source provenance used to compute the digest."
        )
    ]
    for path, record in sorted(source_records.items()):
        lines.append(
            f"- {path}: source_digest={record.digest}; "
            f"provenance={record.provenance}"
        )
    return "\n".join(lines)


def source_digest_for_content(content: str) -> str:
    """Return the canonical per-file source digest for typed edit checks."""

    return hashlib.sha256(str(content).encode("utf-8")).hexdigest()


def _normalize_change(
    raw_change: Mapping[str, Any],
    *,
    source_files: Mapping[str, str],
    source_provenance: Mapping[str, str] | None = None,
    original_source_files: Mapping[str, str] | None = None,
    change_pointer: str,
    allow_original_source_digest: bool = False,
    composing_same_file: bool = False,
    prior_change_pointers: tuple[str, ...] = (),
    has_source_context: bool | None = None,
    reject_legacy_code_content: bool = False,
    allow_host_internal_full_file_modify: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    change = dict(raw_change)
    explicit_intent = _edit_intent(change)
    edit_intent = explicit_intent
    has_content_after = isinstance(change.get("content_after"), str)
    has_code_content = isinstance(change.get("code_content"), str)
    if not edit_intent:
        edit_intent = "full_file" if _has_full_file_content(change) else ""
    if not edit_intent:
        return change, []
    source_context_available = (
        bool(source_files) if has_source_context is None else has_source_context
    )
    file_path = _normalize_path(change.get("file_path"))
    action = str(change.get("action") or "modify").strip()
    if not explicit_intent and not has_content_after and not source_context_available:
        _validate_existing_file_full_file_modify(
            file_path=file_path,
            action=action,
            before=None,
            explicit_intent=explicit_intent,
            has_content_after=has_content_after,
            has_code_content=has_code_content,
            reject_legacy_code_content=reject_legacy_code_content,
            allow_host_internal_full_file_modify=allow_host_internal_full_file_modify,
            change_pointer=change_pointer,
        )
        return change, []
    if edit_intent not in {"exact_replace", "full_file"}:
        raise PatchEditProtocolError(
            f"{change_pointer}: unsupported edit_intent {edit_intent!r}"
        )

    before = source_files.get(file_path)
    original_before = (
        original_source_files.get(file_path) if original_source_files else None
    )
    _validate_existing_file_create_action(
        file_path=file_path,
        action=action,
        before=before,
        change_pointer=change_pointer,
    )
    if edit_intent == "exact_replace":
        content_after = _apply_exact_replace(
            change,
            file_path=file_path,
            action=action,
            before=before,
            original_before=original_before,
            change_pointer=change_pointer,
            allow_original_source_digest=allow_original_source_digest,
            composing_same_file=composing_same_file,
            prior_change_pointers=prior_change_pointers,
        )
    else:
        _validate_existing_file_full_file_modify(
            file_path=file_path,
            action=action,
            before=before,
            explicit_intent=explicit_intent,
            has_content_after=has_content_after,
            has_code_content=has_code_content,
            reject_legacy_code_content=reject_legacy_code_content,
            allow_host_internal_full_file_modify=allow_host_internal_full_file_modify,
            change_pointer=change_pointer,
        )
        content_after = _full_file_content_after(change)
        if action == "delete":
            content_after = ""
        _validate_optional_source_digest(
            change,
            file_path=file_path,
            before=before,
            original_before=original_before,
            change_pointer=change_pointer,
            allow_original_source_digest=allow_original_source_digest,
        )

    if edit_intent == "full_file" and "content_after" in change:
        change["code_content"] = content_after
    elif edit_intent == "exact_replace":
        change["content_after"] = content_after
        change["code_content"] = content_after

    metadata = _normalization_metadata(
        change,
        file_path=file_path,
        action=action,
        edit_intent=edit_intent,
        before=before,
        source_provenance=(
            source_provenance.get(file_path)
            if source_provenance is not None
            else None
        ),
        content_after=content_after,
        change_pointer=change_pointer,
    )
    return change, [metadata]


def _normalize_patch_set_changes(
    normalized: dict[str, Any],
    *,
    source_files: Mapping[str, str],
    source_provenance: Mapping[str, str] | None = None,
    reject_legacy_code_content: bool = False,
    allow_host_internal_full_file_modify: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    slots = _patch_set_slots(normalized)
    path_counts = Counter(
        _normalize_path(slot.raw.get("file_path"))
        for slot in slots
        if _normalize_path(slot.raw.get("file_path"))
    )
    source_state = dict(source_files)
    slot_results: dict[str, dict[str, Any]] = {}
    composed_by_path: dict[str, _ComposedChange] = {}
    metadata: list[dict[str, Any]] = []

    for slot in slots:
        path = _normalize_path(slot.raw.get("file_path"))
        repeated_path = bool(path and path_counts[path] > 1)
        prior = composed_by_path.get(path) if repeated_path else None
        if prior is not None:
            _validate_same_file_action_sequence(
                prior,
                slot=slot,
                file_path=path,
            )
            _validate_same_file_full_file_sequence(
                slot,
                file_path=path,
                current_content=source_state.get(path),
                prior_change_pointers=tuple(prior.json_pointers),
            )

        change, change_metadata = _normalize_change(
            slot.raw,
            source_files=source_state,
            source_provenance=source_provenance,
            original_source_files=source_files,
            change_pointer=slot.pointer,
            allow_original_source_digest=(
                prior is not None and _prior_intents_are_exact_replace(prior)
            ),
            composing_same_file=prior is not None,
            prior_change_pointers=tuple(prior.json_pointers) if prior else (),
            has_source_context=bool(source_files),
            reject_legacy_code_content=reject_legacy_code_content,
            allow_host_internal_full_file_modify=allow_host_internal_full_file_modify,
        )
        slot_results[slot.pointer] = change
        metadata.extend(change_metadata)

        if not path:
            continue
        content_after = _change_content_after(change)
        if content_after is not None:
            source_state[path] = content_after
        if not repeated_path:
            continue

        intent = _effective_edit_intent(change)
        action = str(change.get("action") or "modify").strip()
        if prior is None:
            composed_by_path[path] = _ComposedChange(
                path=path,
                canonical_slot=slot,
                change=change,
                json_pointers=[slot.pointer],
                intents=[intent],
                actions=[action],
            )
            continue

        prior.json_pointers.append(slot.pointer)
        prior.intents.append(intent)
        prior.actions.append(action)
        prior.change = _canonical_composed_change(
            prior.change,
            final_change=change,
        )

    metadata.extend(_composition_metadata(composed_by_path))
    return (
        _rebuild_normalized_patch_set(
            normalized,
            slot_results=slot_results,
            composed_by_path=composed_by_path,
        ),
        metadata,
    )


def _patch_set_slots(normalized: Mapping[str, Any]) -> list[_ChangeSlot]:
    slots = [_ChangeSlot(pointer="/", raw=normalized, is_primary=True)]
    additional = normalized.get("additional_changes")
    if not isinstance(additional, list):
        return slots
    for index, item in enumerate(additional):
        if isinstance(item, Mapping):
            slots.append(
                _ChangeSlot(
                    pointer=f"/additional_changes/{index}",
                    raw=item,
                    is_primary=False,
                    additional_index=index,
                )
            )
    return slots


def _rebuild_normalized_patch_set(
    normalized: Mapping[str, Any],
    *,
    slot_results: Mapping[str, dict[str, Any]],
    composed_by_path: Mapping[str, _ComposedChange],
) -> dict[str, Any]:
    rebuilt = dict(normalized)
    primary_path = _normalize_path(normalized.get("file_path"))
    primary_record = composed_by_path.get(primary_path)
    if primary_record is not None and primary_record.canonical_slot.is_primary:
        rebuilt.update(primary_record.change)
    elif "/" in slot_results:
        rebuilt.update(slot_results["/"])

    additional = normalized.get("additional_changes")
    if not isinstance(additional, list):
        return rebuilt

    rebuilt_additional: list[Any] = []
    for index, item in enumerate(additional):
        if not isinstance(item, Mapping):
            rebuilt_additional.append(item)
            continue
        pointer = f"/additional_changes/{index}"
        path = _normalize_path(item.get("file_path"))
        record = composed_by_path.get(path)
        if record is not None:
            if (
                not record.canonical_slot.is_primary
                and record.canonical_slot.additional_index == index
            ):
                rebuilt_additional.append(record.change)
            continue
        rebuilt_additional.append(slot_results.get(pointer, dict(item)))
    rebuilt["additional_changes"] = rebuilt_additional
    return rebuilt


def _validate_same_file_action_sequence(
    prior: _ComposedChange,
    *,
    slot: _ChangeSlot,
    file_path: str,
) -> None:
    next_action = str(slot.raw.get("action") or "modify").strip()
    actions = {action for action in [*prior.actions, next_action] if action}
    if "delete" in actions and len(actions) > 1:
        _raise_duplicate_file_error(
            reason="mixed_delete_create_or_modify",
            file_path=file_path,
            change_pointer=slot.pointer,
            prior_change_pointers=tuple(prior.json_pointers),
            detail="delete mixed with create/modify cannot be safely composed",
        )
    if (
        actions.intersection({"create", "create_new", "full_file"})
        and len(actions) > 1
    ):
        _raise_duplicate_file_error(
            reason="mixed_create_modify",
            file_path=file_path,
            change_pointer=slot.pointer,
            prior_change_pointers=tuple(prior.json_pointers),
            detail="create mixed with modify/delete cannot be safely composed",
        )


def _validate_same_file_full_file_sequence(
    slot: _ChangeSlot,
    *,
    file_path: str,
    current_content: str | None,
    prior_change_pointers: tuple[str, ...],
) -> None:
    if _effective_edit_intent(slot.raw) != "full_file":
        return
    next_content = _raw_change_content_after(slot.raw)
    if current_content is None or next_content == current_content:
        return
    _raise_duplicate_file_error(
        reason="full_file_conflict",
        file_path=file_path,
        change_pointer=slot.pointer,
        prior_change_pointers=prior_change_pointers,
        detail="full_file content_after conflicts with prior same-file edits",
    )


def _canonical_composed_change(
    canonical_change: Mapping[str, Any],
    *,
    final_change: Mapping[str, Any],
) -> dict[str, Any]:
    composed = dict(canonical_change)
    action = str(
        final_change.get("action") or composed.get("action") or "modify"
    ).strip()
    content_after = _change_content_after(final_change)
    composed["action"] = action
    if content_after is not None:
        composed["edit_intent"] = "full_file"
        composed["content_after"] = content_after
        composed["code_content"] = content_after
        composed.pop("old_string", None)
        composed.pop("new_string", None)
        composed.pop("source_digest", None)
        composed.pop("replace_all", None)
    if final_change.get("test_hint"):
        composed["test_hint"] = final_change.get("test_hint")
    evidence_refs = [
        *(_string_list(composed.get("evidence_refs"))),
        *(_string_list(final_change.get("evidence_refs"))),
    ]
    if evidence_refs:
        composed["evidence_refs"] = list(dict.fromkeys(evidence_refs))
    return composed


def _composition_metadata(
    composed_by_path: Mapping[str, _ComposedChange],
) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for record in composed_by_path.values():
        if len(record.json_pointers) < 2:
            continue
        metadata.append(
            {
                "field": "patch_set_change",
                "repair_kind": "patch_set_composition",
                "root_cause": "duplicate_file_path",
                "action": "composed_duplicate_file_changes",
                "file_path": record.path,
                "canonical_json_pointer": record.json_pointers[0],
                "source_json_pointers": list(record.json_pointers),
                "merged_change_count": len(record.json_pointers),
            }
        )
    return metadata


def _prior_intents_are_exact_replace(record: _ComposedChange) -> bool:
    return bool(record.intents) and all(
        intent == "exact_replace" for intent in record.intents
    )


def _raw_change_content_after(change: Mapping[str, Any]) -> str:
    action = str(change.get("action") or "modify").strip()
    if action == "delete":
        return ""
    return _full_file_content_after(change)


def _change_content_after(change: Mapping[str, Any]) -> str | None:
    action = str(change.get("action") or "modify").strip()
    if action == "delete":
        return ""
    content = change.get("content_after")
    if isinstance(content, str):
        return content
    content = change.get("code_content")
    if isinstance(content, str):
        return content
    return None


def _effective_edit_intent(change: Mapping[str, Any]) -> str:
    edit_intent = _edit_intent(change)
    if edit_intent:
        return edit_intent
    return "full_file" if _change_content_after(change) is not None else ""


def _raise_duplicate_file_error(
    *,
    reason: str,
    file_path: str,
    change_pointer: str,
    prior_change_pointers: tuple[str, ...],
    detail: str,
) -> None:
    raise PatchEditProtocolError(
        json.dumps(
            {
                "error": "patch_edit_protocol",
                "reason": reason,
                "file_path": file_path,
                "json_pointer": change_pointer,
                "prior_json_pointers": list(prior_change_pointers),
                "detail": detail,
                "guidance": (
                    "Use one file change for this file or serializable "
                    "exact_replace edits whose old_string values match the "
                    "content after earlier same-file edits."
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _validate_existing_file_full_file_modify(
    *,
    file_path: str,
    action: str,
    before: str | None,
    explicit_intent: str,
    has_content_after: bool,
    has_code_content: bool,
    reject_legacy_code_content: bool,
    allow_host_internal_full_file_modify: bool,
    change_pointer: str,
) -> None:
    if action != "modify" or allow_host_internal_full_file_modify:
        return
    if (
        explicit_intent != "full_file"
        and not has_content_after
        and (not has_code_content or not reject_legacy_code_content)
    ):
        return
    content_field = "content_after" if has_content_after else "code_content"
    reason = (
        "existing_file_full_file_modify_rejected"
        if before is not None
        else "existing_file_full_file_modify_source_required"
    )
    detail = (
        "action=modify targets an existing host-visible file; "
        "model-supplied full_file/content_after is disabled by "
        "default. full_file_reason is not an authorization."
        if before is not None
        else "action=modify declares an existing-file change, but no "
        "host-visible source was provided. Model-facing existing-file "
        "modifies must use exact_replace with source_digest; "
        "full_file/content_after/code_content is allowed only for "
        "creates or for host-internal compatibility."
    )
    payload = {
        "error": "patch_edit_protocol",
        "reason": reason,
        "file_path": file_path,
        "json_pointer": change_pointer,
        "action": action,
        "edit_intent": "full_file",
        "content_field": content_field,
        "detail": detail,
        "guidance": (
            "Existing file requires modify exact_replace with source_digest; "
            "create is only for new files. "
            "Rewrite this change as edit_intent='exact_replace': set "
            "source_digest to the host-provided sha256 digest, omit "
            "content_after/code_content, provide a non-empty "
            "old_string copied exactly from the current file, and "
            "provide new_string with only the replacement text. "
            "Use new_string: \"\" for deletion; do not omit new_string or set "
            "it to null. old_string must match exactly once unless "
            "replace_all=true."
        ),
        "minimal_json_shape": {
            "file_path": file_path,
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": "<host-provided sha256 digest>",
            "old_string": "<non-empty exact current text>",
            "new_string": "<replacement text; use \"\" for deletion>",
            "replace_all": False,
        },
    }
    if before is not None:
        payload["source_digest"] = source_digest_for_content(before)
    raise PatchEditProtocolError(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _validate_existing_file_create_action(
    *,
    file_path: str,
    action: str,
    before: str | None,
    change_pointer: str,
) -> None:
    if before is None or action not in {"create", "create_new", "full_file"}:
        return
    payload = {
        "error": "patch_edit_protocol",
        "reason": "existing_file_create_rejected",
        "file_path": file_path,
        "json_pointer": change_pointer,
        "action": action,
        "source_digest": source_digest_for_content(before),
        "detail": (
            "existing file requires modify exact_replace with source_digest; "
            "create is only for new files."
        ),
        "guidance": (
            "Rewrite this existing-file change with action='modify' and "
            "edit_intent='exact_replace': set source_digest to the "
            "host-provided sha256 digest, provide a non-empty old_string "
            "copied exactly from the current file, and provide new_string "
            "with only the replacement text. Use new_string: \"\" for "
            "deletion; do not omit new_string or set it to null. Use "
            "action='create' and edit_intent='full_file' only when the file "
            "does not exist."
        ),
        "minimal_json_shape": {
            "file_path": file_path,
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": "<host-provided sha256 digest>",
            "old_string": "<non-empty exact current text>",
            "new_string": "<replacement text; use \"\" for deletion>",
            "replace_all": False,
        },
    }
    raise PatchEditProtocolError(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _apply_exact_replace(
    change: Mapping[str, Any],
    *,
    file_path: str,
    action: str,
    before: str | None,
    original_before: str | None,
    change_pointer: str,
    allow_original_source_digest: bool = False,
    composing_same_file: bool = False,
    prior_change_pointers: tuple[str, ...] = (),
) -> str:
    if action != "modify":
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_replace requires action='modify'"
        )
    if before is None:
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_replace source unavailable for {file_path}"
        )
    expected_digest = _digest_text(change.get("source_digest"))
    if not expected_digest:
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_replace requires source_digest"
        )
    actual_digest = source_digest_for_content(before)
    original_digest = (
        source_digest_for_content(original_before)
        if original_before is not None
        else ""
    )
    if expected_digest != actual_digest and not (
        allow_original_source_digest and expected_digest == original_digest
    ):
        raise PatchEditProtocolError(
            f"{change_pointer}: stale_source for {file_path}: "
            f"expected {expected_digest}, current {actual_digest}"
        )

    old_string = change.get("old_string")
    new_string = change.get("new_string")
    if not isinstance(old_string, str) or old_string == "":
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_replace requires non-empty old_string"
        )
    if not isinstance(new_string, str):
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_replace requires new_string"
        )
    if old_string == before:
        _raise_exact_replace_granularity_error(
            reason="existing_file_whole_file_exact_replace_rejected",
            file_path=file_path,
            change_pointer=change_pointer,
            source_digest=actual_digest,
            old_string_chars=len(old_string),
            file_chars=len(before),
            coverage_ratio=1.0,
            detail=(
                "exact_replace old_string is the complete existing file; "
                "whole-file rewrites of host-visible files are disabled by default."
            ),
        )
    _validate_exact_replace_granularity(
        file_path=file_path,
        change_pointer=change_pointer,
        source_digest=actual_digest,
        before=before,
        old_string=old_string,
    )
    occurrences = before.count(old_string)
    if occurrences == 0:
        if composing_same_file:
            _raise_duplicate_file_error(
                reason="exact_replace_not_serializable",
                file_path=file_path,
                change_pointer=change_pointer,
                prior_change_pointers=prior_change_pointers,
                detail=(
                    "exact_replace old_string does not match the content "
                    "after prior same-file edits"
                ),
            )
        raise PatchEditProtocolError(
            f"{change_pointer}: old_string_not_found in {file_path}"
        )
    replace_all = _bool_value(change.get("replace_all", False))
    if occurrences > 1 and not replace_all:
        raise PatchEditProtocolError(
            json.dumps(
                _old_string_not_unique_payload(
                    file_path=file_path,
                    change_pointer=change_pointer,
                    source_digest=actual_digest,
                    before=before,
                    old_string=old_string,
                    occurrences=occurrences,
                ),
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    if replace_all:
        return before.replace(old_string, new_string)
    return before.replace(old_string, new_string, 1)


def _old_string_not_unique_payload(
    *,
    file_path: str,
    change_pointer: str,
    source_digest: str,
    before: str,
    old_string: str,
    occurrences: int,
) -> dict[str, Any]:
    candidates = _old_string_candidate_matches(before, old_string)
    return {
        "error": "patch_edit_protocol",
        "reason": "old_string_not_unique",
        "file_path": file_path,
        "json_pointer": change_pointer,
        "source_digest": source_digest,
        "match_count": occurrences,
        "candidate_matches": candidates,
        "guidance": (
            "Rewrite old_string so it matches exactly one intended location by "
            "including stable surrounding context from one candidate snippet. "
            "Keep replace_all=false unless the intended edit is truly global "
            "across every listed match."
        ),
    }


def _old_string_candidate_matches(
    before: str,
    old_string: str,
    *,
    max_candidates: int = 5,
    context_chars: int = 120,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    start = 0
    while len(candidates) < max_candidates:
        index = before.find(old_string, start)
        if index < 0:
            break
        line, column = _line_column_for_offset(before, index)
        prefix_start = max(0, index - context_chars)
        suffix_end = min(len(before), index + len(old_string) + context_chars)
        prefix = before[prefix_start:index]
        suffix = before[index + len(old_string) : suffix_end]
        candidates.append(
            {
                "line": line,
                "column": column,
                "prefix": _single_line_snippet(prefix),
                "match": _single_line_snippet(old_string),
                "suffix": _single_line_snippet(suffix),
                "unique_old_string_hint": _single_line_snippet(
                    before[prefix_start:suffix_end],
                    max_chars=320,
                ),
            }
        )
        start = index + max(1, len(old_string))
    return candidates


def _line_column_for_offset(text: str, offset: int) -> tuple[int, int]:
    safe_offset = max(0, min(len(text), offset))
    line = text.count("\n", 0, safe_offset) + 1
    line_start = text.rfind("\n", 0, safe_offset) + 1
    return line, safe_offset - line_start + 1


def _single_line_snippet(value: str, *, max_chars: int = 220) -> str:
    text = str(value or "").replace("\r", "")
    text = text.replace("\n", "\\n")
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)] + "..."


def _validate_exact_replace_granularity(
    *,
    file_path: str,
    change_pointer: str,
    source_digest: str,
    before: str,
    old_string: str,
) -> None:
    file_chars = len(before)
    if file_chars <= _NEAR_WHOLE_FILE_EXACT_REPLACE_MIN_CHARS:
        return
    coverage_ratio = len(old_string) / max(1, file_chars)
    if coverage_ratio < _NEAR_WHOLE_FILE_EXACT_REPLACE_MAX_COVERAGE:
        return
    _raise_exact_replace_granularity_error(
        reason="existing_file_near_whole_file_exact_replace_rejected",
        file_path=file_path,
        change_pointer=change_pointer,
        source_digest=source_digest,
        old_string_chars=len(old_string),
        file_chars=file_chars,
        coverage_ratio=coverage_ratio,
        detail=(
            "exact_replace old_string covers most of an existing host-visible "
            "file; near-whole-file rewrites are disabled by default."
        ),
    )


def _raise_exact_replace_granularity_error(
    *,
    reason: str,
    file_path: str,
    change_pointer: str,
    source_digest: str,
    old_string_chars: int,
    file_chars: int,
    coverage_ratio: float,
    detail: str,
) -> None:
    raise PatchEditProtocolError(
        json.dumps(
            {
                "error": "patch_edit_protocol",
                "reason": reason,
                "file_path": file_path,
                "json_pointer": change_pointer,
                "source_digest": source_digest,
                "old_string_chars": old_string_chars,
                "file_chars": file_chars,
                "coverage_ratio": round(coverage_ratio, 4),
                "max_coverage_ratio": _NEAR_WHOLE_FILE_EXACT_REPLACE_MAX_COVERAGE,
                "recommended_max_coverage_ratio": (
                    _RECOMMENDED_EXACT_REPLACE_MAX_COVERAGE
                ),
                "detail": detail,
                "guidance": (
                    "Split the change into smaller exact_replace edits for a "
                    "function/block, or create a helper file and add a small "
                    "integration edit. Each old_string should identify only the "
                    "function, import block, registration entry, or local code "
                    "block that actually changes. Keep exact_replace old_string "
                    "well below whole-file scope; use the recommended coverage "
                    "ratio as the retry target."
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _validate_optional_source_digest(
    change: Mapping[str, Any],
    *,
    file_path: str,
    before: str | None,
    original_before: str | None = None,
    change_pointer: str,
    allow_original_source_digest: bool = False,
) -> None:
    expected_digest = _digest_text(change.get("source_digest"))
    if not expected_digest or before is None:
        return
    actual_digest = source_digest_for_content(before)
    original_digest = (
        source_digest_for_content(original_before)
        if original_before is not None
        else ""
    )
    if expected_digest != actual_digest and not (
        allow_original_source_digest and expected_digest == original_digest
    ):
        raise PatchEditProtocolError(
            f"{change_pointer}: stale_source for {file_path}: "
            f"expected {expected_digest}, current {actual_digest}"
        )


def _normalization_metadata(
    change: Mapping[str, Any],
    *,
    file_path: str,
    action: str,
    edit_intent: str,
    before: str | None,
    source_provenance: str | None = None,
    content_after: str,
    change_pointer: str,
) -> dict[str, Any]:
    before_digest = source_digest_for_content(before) if before is not None else None
    after_digest = source_digest_for_content(content_after)
    diff_stats = _diff_stats(before, content_after)
    derived_diff_ref = _derived_diff_ref(
        file_path=file_path,
        before_digest=before_digest,
        after_digest=after_digest,
    )
    return {
        "field": "patch_set_change",
        "repair_kind": "typed_edit_normalization",
        "action": "normalized_to_canonical_full_content",
        "json_pointer": change_pointer,
        "file_path": file_path,
        "patch_action": action,
        "edit_intent": edit_intent,
        "source_digest": _digest_text(change.get("source_digest")) or before_digest,
        "source_record_digest": before_digest,
        "source_provenance": source_provenance or "",
        "content_after_digest": after_digest,
        "derived_diff_ref": derived_diff_ref,
        "derived_diff_summary": diff_stats,
        "evidence_refs": _string_list(change.get("evidence_refs")),
    }


def _diff_stats(before: str | None, after: str) -> dict[str, Any]:
    if before is None:
        return {
            "before_line_count": 0,
            "after_line_count": len(after.splitlines()),
            "added_lines": len(after.splitlines()),
            "removed_lines": 0,
            "available": False,
        }
    diff_lines = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            lineterm="",
        )
    )
    added = sum(
        1
        for line in diff_lines
        if line.startswith("+") and not line.startswith("+++")
    )
    removed = sum(
        1
        for line in diff_lines
        if line.startswith("-") and not line.startswith("---")
    )
    return {
        "before_line_count": len(before.splitlines()),
        "after_line_count": len(after.splitlines()),
        "added_lines": added,
        "removed_lines": removed,
        "available": True,
    }


def _derived_diff_ref(
    *,
    file_path: str,
    before_digest: str | None,
    after_digest: str,
) -> str:
    payload = {
        "file_path": file_path,
        "before": before_digest or "",
        "after": after_digest,
    }
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]
    return f"typed-edit-diff:{digest}"


def _source_files_from_context(context: Mapping[str, Any] | None) -> dict[str, str]:
    return {
        path: record.content
        for path, record in _source_records_from_context(context).items()
    }


def _source_records_from_context(
    context: Mapping[str, Any] | None,
    *,
    requested_paths: tuple[str, ...] = (),
) -> dict[str, _SourceRecord]:
    if not context:
        return {}
    source_files: dict[str, _SourceRecord] = {}
    for key in ("patch_source_files", "source_files", "editable_source_files"):
        value = context.get(key)
        if isinstance(value, Mapping):
            for path, content in value.items():
                normalized_path = _normalize_path(path)
                source = _source_text_from_context_value(
                    content,
                    expected_path=normalized_path,
                )
                if normalized_path and source is not None:
                    _put_source_record(
                        source_files,
                        normalized_path,
                        source,
                        key,
                    )
    target_file = _normalize_path(context.get("target_file"))
    target_content = context.get("target_file_code")
    target_source = _source_text_from_context_value(
        target_content,
        expected_path=target_file,
    )
    if target_file and target_source is not None:
        _put_source_record(source_files, target_file, target_source, "target_file_code")
    original_code = context.get("original_code")
    if isinstance(original_code, str):
        _put_source_records(
            source_files,
            _parse_original_code_source(original_code),
            "original_code",
        )
    for key in ("solver_design_branch_current_integration_files",):
        integration_files = context.get(key)
        if isinstance(integration_files, str):
            _put_source_records(
                source_files,
                _parse_markdown_source_files(integration_files),
                key,
            )
    _put_source_records(
        source_files,
        _solver_design_full_read_sources(
            context.get("solver_design_full_algorithm_file_reads")
        ),
        "solver_design_full_algorithm_file_reads",
    )
    _put_source_records(
        source_files,
        _agentic_tool_observation_full_read_sources(
            context.get("agentic_tool_observations")
        ),
        "agentic_tool_observations.context.read_algorithm_file",
    )
    integration_files = context.get("agentic_required_full_integration_files")
    if isinstance(integration_files, str):
        _put_source_records(
            source_files,
            _parse_markdown_source_files(integration_files),
            "agentic_required_full_integration_files",
        )
    for requested_path in requested_paths:
        if requested_path in source_files:
            continue
        fallback = _branch_workspace_source(context, requested_path)
        if fallback is not None:
            _put_source_record(
                source_files,
                requested_path,
                fallback,
                "branch_workspace_fallback",
            )
    return source_files


def _put_source_records(
    records: dict[str, _SourceRecord],
    sources: Mapping[str, str],
    provenance: str,
) -> None:
    for path, content in sources.items():
        _put_source_record(records, path, content, provenance)


def _put_source_record(
    records: dict[str, _SourceRecord],
    path: str,
    content: str,
    provenance: str,
) -> None:
    normalized_path = _normalize_path(path)
    if not normalized_path or content is None:
        return
    records[normalized_path] = _SourceRecord(
        content=str(content),
        provenance=provenance,
    )


def _patch_requested_paths(raw: Mapping[str, Any]) -> tuple[str, ...]:
    paths: list[str] = []
    for slot in _patch_set_slots(raw):
        path = _normalize_path(slot.raw.get("file_path"))
        if path:
            paths.append(path)
    return tuple(dict.fromkeys(paths))


def _solver_design_full_read_sources(value: Any) -> dict[str, str]:
    records: dict[str, str] = {}
    if isinstance(value, Mapping):
        value = value.get("reads")
    if not isinstance(value, (list, tuple)):
        return records
    for item in value:
        if not isinstance(item, Mapping):
            continue
        source = _full_read_source_from_payload(item)
        path = _normalize_path(item.get("file_path"))
        if path and source is not None:
            records[path] = source
    return records


def _agentic_tool_observation_full_read_sources(value: Any) -> dict[str, str]:
    records: dict[str, str] = {}
    if not isinstance(value, (list, tuple)):
        return records
    for item in value:
        if not isinstance(item, Mapping):
            continue
        if item.get("tool_name") != "context.read_algorithm_file":
            continue
        if bool(item.get("is_error")):
            continue
        payload = item.get("structured_payload")
        if not isinstance(payload, Mapping):
            continue
        source = _full_read_source_from_payload(payload)
        path = _normalize_path(payload.get("file_path"))
        if path and source is not None:
            records[path] = source
    return records


def _full_read_source_from_payload(payload: Mapping[str, Any]) -> str | None:
    if payload.get("readable") is not True:
        return None
    if payload.get("active") is False:
        return None
    if bool(payload.get("truncated")):
        return None
    content = payload.get("content_preview")
    if not isinstance(content, str):
        return None
    return content


def _branch_workspace_source(
    context: Mapping[str, Any],
    requested_path: str,
) -> str | None:
    normalized_path = _normalize_path(requested_path)
    if not normalized_path or not _path_editable_for_branch_fallback(
        context,
        normalized_path,
    ):
        return None
    root_value = (
        context.get("branch_workspace")
        or context.get("solver_design_source_root")
        or context.get("source_root")
    )
    if not isinstance(root_value, str) or not root_value.strip():
        return None
    try:
        root = Path(root_value).resolve()
        candidate = (root / normalized_path).resolve()
        candidate.relative_to(root)
    except Exception:
        return None
    if not candidate.is_file():
        return None
    try:
        return candidate.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _path_editable_for_branch_fallback(
    context: Mapping[str, Any],
    path: str,
) -> bool:
    editable_patterns = _pattern_list(context.get("editable_patterns"))
    if not editable_patterns:
        return False
    frozen_patterns = _pattern_list(context.get("frozen_patterns"))
    if any(fnmatch.fnmatchcase(path, pattern) for pattern in frozen_patterns):
        return False
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in editable_patterns)


def _pattern_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        items = re.split(r"[\n,]+", value)
    elif isinstance(value, (list, tuple, set, frozenset)):
        items = [str(item) for item in value]
    else:
        return ()
    return tuple(item.strip() for item in items if item and item.strip())


def _parse_markdown_source_files(rendered: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for match in _SOURCE_FILE_RE.finditer(rendered):
        path = _normalize_path(match.group("path"))
        content = match.group("content") + match.group("terminal_newline")
        if path:
            files[path] = content
    return files


def _parse_original_code_source(rendered: str) -> dict[str, str]:
    return _parse_markdown_source_files(rendered)


def _source_text_from_context_value(
    value: Any,
    *,
    expected_path: str = "",
) -> str | None:
    if not _is_existing_source_text(value):
        return None
    text = str(value)
    markdown_sources = _parse_markdown_source_files(text)
    normalized_expected = _normalize_path(expected_path)
    if normalized_expected and normalized_expected in markdown_sources:
        return markdown_sources[normalized_expected]
    if not normalized_expected and len(markdown_sources) == 1:
        return next(iter(markdown_sources.values()))

    fenced = _FENCED_SOURCE_RE.match(text)
    if fenced:
        return fenced.group("content") + fenced.group("terminal_newline")

    loose = _LOOSE_FILE_SOURCE_RE.match(text)
    if loose:
        path = _normalize_path(loose.group("path"))
        if not normalized_expected or path == normalized_expected:
            return _strip_trailing_fence(loose.group("content"))

    return text


def _strip_trailing_fence(value: str) -> str:
    text = str(value)
    stripped = text.rstrip()
    if stripped.endswith("```"):
        stripped = stripped[:-3].rstrip()
        return stripped + ("\n" if text.endswith("\n") else "")
    return text


def _is_existing_source_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return False
    return "will be created" not in stripped


def _edit_intent(change: Mapping[str, Any]) -> str:
    return str(change.get("edit_intent") or "").strip()


def _has_full_file_content(change: Mapping[str, Any]) -> bool:
    return isinstance(change.get("content_after"), str) or isinstance(
        change.get("code_content"), str
    )


def _full_file_content_after(change: Mapping[str, Any]) -> str:
    content = change.get("content_after")
    if isinstance(content, str):
        return content
    content = change.get("code_content")
    if isinstance(content, str):
        return content
    return ""


def _digest_text(value: Any) -> str:
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


def _normalize_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()


def _string_list(value: Any) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(item) for item in value if str(item or "").strip()]
    return [str(value)]


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
