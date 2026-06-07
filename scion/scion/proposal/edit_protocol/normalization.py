"""Normalize model-facing typed edits into canonical full-file patch content."""

from __future__ import annotations

import difflib
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Mapping

from scion.proposal.edit_protocol.errors import (
    PatchEditProtocolError,
    raise_duplicate_file_error as _raise_duplicate_file_error,
)
from scion.proposal.edit_protocol.exact_replace import (
    apply_exact_replace as _apply_exact_replace,
    digest_text as _digest_text,
    validate_optional_source_digest as _validate_optional_source_digest,
)
from scion.proposal.edit_protocol.source_discovery import (
    source_digest_for_content,
    source_records_from_context as _source_records_from_context,
)
from scion.proposal.schemas.patch import (
    PatchSchemaPreflightError,
    preflight_patch_exact_replace_shape,
)


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
        eof_final_newline_tolerated = bool(
            change.pop("_host_eof_final_newline_tolerated", False)
        )
    else:
        eof_final_newline_tolerated = False
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
        eof_final_newline_tolerated=eof_final_newline_tolerated,
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
    dropped_pointers: set[str] = set()
    metadata: list[dict[str, Any]] = []

    for slot in slots:
        path = _normalize_path(slot.raw.get("file_path"))
        if path and _is_droppable_noop_exact_replace(slot):
            dropped_pointers.add(slot.pointer)
            metadata.append(
                _noop_exact_replace_metadata(
                    slot.raw,
                    file_path=path,
                    change_pointer=slot.pointer,
                )
            )
            continue
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
            dropped_pointers=dropped_pointers,
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
    dropped_pointers: set[str] | None = None,
) -> dict[str, Any]:
    rebuilt = dict(normalized)
    dropped = dropped_pointers or set()
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
        if pointer in dropped:
            continue
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


def _is_droppable_noop_exact_replace(slot: _ChangeSlot) -> bool:
    if slot.is_primary:
        return False
    if _effective_edit_intent(slot.raw) != "exact_replace":
        return False
    action = str(slot.raw.get("action") or "modify").strip()
    if action != "modify":
        return False
    old_string = slot.raw.get("old_string")
    new_string = slot.raw.get("new_string")
    return _noop_exact_replace_kind(old_string, new_string) != ""


def _noop_exact_replace_kind(old_string: Any, new_string: Any) -> str:
    if not isinstance(old_string, str) or not isinstance(new_string, str):
        return ""
    if old_string == new_string:
        return "identical_old_and_new"
    if old_string.rstrip() == new_string.rstrip():
        return "trailing_whitespace_only"
    return ""


def _noop_exact_replace_metadata(
    change: Mapping[str, Any],
    *,
    file_path: str,
    change_pointer: str,
) -> dict[str, Any]:
    old_string = change.get("old_string")
    new_string = change.get("new_string")
    return {
        "field": "patch_set_change",
        "repair_kind": "typed_edit_noop_dropped",
        "action": "dropped_noop_exact_replace",
        "reason": "exact_replace_noop",
        "noop_kind": _noop_exact_replace_kind(old_string, new_string),
        "json_pointer": change_pointer,
        "file_path": file_path,
        "patch_action": str(change.get("action") or "modify").strip(),
        "edit_intent": "exact_replace",
        "source_digest": _digest_text(change.get("source_digest")),
        "old_string_chars": len(old_string) if isinstance(old_string, str) else None,
        "new_string_chars": len(new_string) if isinstance(new_string, str) else None,
        "guidance": (
            "Dropped a no-op exact_replace additional change. Do not emit "
            "old_string == new_string or EOF/trailing-whitespace-only edits; "
            "remove the entry or merge meaningful same-file edits into one "
            "serializable file change."
        ),
    }


def _effective_edit_intent(change: Mapping[str, Any]) -> str:
    edit_intent = _edit_intent(change)
    if edit_intent:
        return edit_intent
    return "full_file" if _change_content_after(change) is not None else ""


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
    eof_final_newline_tolerated: bool = False,
) -> dict[str, Any]:
    before_digest = source_digest_for_content(before) if before is not None else None
    after_digest = source_digest_for_content(content_after)
    diff_stats = _diff_stats(before, content_after)
    derived_diff_ref = _derived_diff_ref(
        file_path=file_path,
        before_digest=before_digest,
        after_digest=after_digest,
    )
    metadata = {
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
    if eof_final_newline_tolerated:
        metadata.update(
            {
                "selector_repair": "eof_final_newline_tolerated",
                "eof_final_newline_tolerated": True,
                "selector_repair_guidance": (
                    "Host tolerated a terminal-newline-only selector drift at "
                    "EOF. Future exact_replace old_string values should match "
                    "the displayed source bytes exactly."
                ),
            }
        )
    return metadata


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


def _patch_requested_paths(raw: Mapping[str, Any]) -> tuple[str, ...]:
    paths: list[str] = []
    for slot in _patch_set_slots(raw):
        path = _normalize_path(slot.raw.get("file_path"))
        if path:
            paths.append(path)
    return tuple(dict.fromkeys(paths))


def _edit_intent(change: Mapping[str, Any]) -> str:
    return str(change.get("edit_intent") or "").strip()


def _has_full_file_content(change: Mapping[str, Any]) -> bool:
    return _non_empty_text(change.get("content_after")) or _non_empty_text(
        change.get("code_content")
    )


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _full_file_content_after(change: Mapping[str, Any]) -> str:
    content = change.get("content_after")
    if isinstance(content, str):
        return content
    content = change.get("code_content")
    if isinstance(content, str):
        return content
    return ""


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
