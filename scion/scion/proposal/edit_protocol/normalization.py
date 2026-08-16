"""Validate explicit typed edits and materialize their direct source value."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scion.proposal.edit_protocol.errors import PatchEditProtocolError
from scion.proposal.edit_protocol.exact_line_replace import apply_exact_line_replace
from scion.proposal.edit_protocol.exact_replace import apply_exact_replace
from scion.proposal.edit_protocol.source_discovery import source_files_from_context
from scion.proposal.schemas.patch import (
    PatchSchemaPreflightError,
    preflight_patch_exact_replace_shape,
)


def normalize_patch_typed_edits(
    raw: Mapping[str, Any],
    *,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one strictly validated patch value.

    Each file appears exactly once and declares an explicit edit intent. Local
    edits bind to the one source value visible to the C call. The host neither
    repairs selectors nor drops, merges, or otherwise rewrites model intent.
    It only materializes the resulting full-file value consumed by Contract and
    Workspace.
    """

    normalized = dict(raw)
    try:
        preflight_patch_exact_replace_shape(normalized)
    except PatchSchemaPreflightError as exc:
        raise PatchEditProtocolError(str(exc)) from exc

    source_files = source_files_from_context(context)
    slots: list[tuple[str, Mapping[str, Any]]] = [("/", normalized)]
    additional = normalized.get("additional_changes")
    if isinstance(additional, list):
        slots.extend(
            (f"/additional_changes/{index}", item)
            for index, item in enumerate(additional)
            if isinstance(item, Mapping)
        )

    seen_paths: dict[str, str] = {}
    changes: dict[str, dict[str, Any]] = {}
    for pointer, raw_change in slots:
        path = _normalized_path(raw_change.get("file_path"))
        if path in seen_paths:
            raise PatchEditProtocolError(
                f"{pointer}: duplicate file_path {path!r}; each file must be "
                f"expressed by one typed change (first declared at "
                f"{seen_paths[path]})"
            )
        if path:
            seen_paths[path] = pointer
        changes[pointer] = _normalize_change(
            raw_change,
            source_files=source_files,
            pointer=pointer,
        )

    normalized.update(changes["/"])
    if isinstance(additional, list):
        normalized["additional_changes"] = [
            changes.get(f"/additional_changes/{index}", item)
            for index, item in enumerate(additional)
        ]
    return normalized


def _normalize_change(
    raw: Mapping[str, Any],
    *,
    source_files: Mapping[str, str],
    pointer: str,
) -> dict[str, Any]:
    change = dict(raw)
    path = _normalized_path(change.get("file_path"))
    action = str(change.get("action") or "").strip()
    intent = str(change.get("edit_intent") or "").strip()
    if not intent:
        raise PatchEditProtocolError(
            f"{pointer}: edit_intent is required; choose exact_replace, "
            "exact_line_replace, or full_file"
        )
    if intent not in {"exact_replace", "exact_line_replace", "full_file"}:
        raise PatchEditProtocolError(
            f"{pointer}: unsupported edit_intent {intent!r}"
        )

    before = source_files.get(path)
    if intent == "exact_replace":
        content_after = apply_exact_replace(
            change,
            file_path=path,
            action=action,
            before=before,
            change_pointer=pointer,
        )
    elif intent == "exact_line_replace":
        content_after = apply_exact_line_replace(
            change,
            file_path=path,
            action=action,
            before=before,
            change_pointer=pointer,
        ).content_after
    else:
        content_after = _validate_full_file_change(
            change,
            path=path,
            action=action,
            before=before,
            pointer=pointer,
        )

    if action == "modify" and content_after == before:
        raise PatchEditProtocolError(
            f"{pointer}: patch is a no-op for {path}; emit a real source change"
        )
    change["content_after"] = content_after
    change["code_content"] = content_after
    return change


def _validate_full_file_change(
    change: Mapping[str, Any],
    *,
    path: str,
    action: str,
    before: str | None,
    pointer: str,
) -> str:
    if action == "modify":
        if before is None:
            raise PatchEditProtocolError(
                f"{pointer}: full_file modify source unavailable for {path}"
            )
        content = change.get("content_after")
        if not isinstance(content, str) or not content.strip():
            raise PatchEditProtocolError(
                f"{pointer}: full_file modify requires non-empty content_after"
            )
        return content
    if action == "create":
        if before is not None:
            raise PatchEditProtocolError(
                f"{pointer}: create requires a new file; {path} already exists"
            )
        content = change.get("content_after")
        if not isinstance(content, str) or not content.strip():
            raise PatchEditProtocolError(
                f"{pointer}: full_file create requires non-empty content_after"
            )
        return content
    if action == "delete":
        if before is None:
            raise PatchEditProtocolError(
                f"{pointer}: delete source unavailable for {path}"
            )
        supplied = change.get("content_after")
        if supplied not in (None, ""):
            raise PatchEditProtocolError(
                f"{pointer}: delete must not supply content_after"
            )
        return ""
    raise PatchEditProtocolError(
        f"{pointer}: unsupported patch action {action!r}"
    )


def _normalized_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()
