"""Normalize model-facing typed edits into canonical full-file patch content."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from typing import Any, Mapping


_SOURCE_FILE_RE = re.compile(
    r"^### (?P<path>[^\n]+)\n"
    r"(?:[^\n]*\n)*?"
    r"```(?:python)?\n"
    r"(?P<content>.*?)"
    r"\n```",
    re.DOTALL | re.MULTILINE,
)


class PatchEditProtocolError(ValueError):
    """Raised when a typed edit cannot be safely normalized."""


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

    source_files = _source_files_from_context(context)
    metadata: list[dict[str, Any]] = []
    primary, primary_metadata = _normalize_change(
        normalized,
        source_files=source_files,
        change_pointer="/",
    )
    normalized.update(primary)
    metadata.extend(primary_metadata)

    additional = normalized.get("additional_changes")
    if isinstance(additional, list):
        normalized_additional: list[Any] = []
        for index, item in enumerate(additional):
            if not isinstance(item, Mapping):
                normalized_additional.append(item)
                continue
            change, change_metadata = _normalize_change(
                item,
                source_files=source_files,
                change_pointer=f"/additional_changes/{index}",
            )
            normalized_additional.append(change)
            metadata.extend(change_metadata)
        normalized["additional_changes"] = normalized_additional

    return normalized, tuple(metadata)


def build_patch_edit_source_manifest(context: Mapping[str, Any]) -> str:
    """Render compact source digests for model-facing typed edit prompts."""

    source_files = _source_files_from_context(context)
    if not source_files:
        return "(no editable source digests available)"
    lines = [
        (
            "Use these sha256 source_digest values for exact_replace edits. "
            "For create actions use null."
        )
    ]
    for path, content in sorted(source_files.items()):
        lines.append(f"- {path}: {source_digest_for_content(content)}")
    return "\n".join(lines)


def source_digest_for_content(content: str) -> str:
    """Return the canonical per-file source digest for typed edit checks."""

    return hashlib.sha256(str(content).encode("utf-8")).hexdigest()


def _normalize_change(
    raw_change: Mapping[str, Any],
    *,
    source_files: Mapping[str, str],
    change_pointer: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    change = dict(raw_change)
    explicit_intent = _edit_intent(change)
    edit_intent = explicit_intent
    has_content_after = isinstance(change.get("content_after"), str)
    if not edit_intent:
        edit_intent = "full_file" if _has_full_file_content(change) else ""
    if not edit_intent:
        return change, []
    if not explicit_intent and not has_content_after and not source_files:
        return change, []
    if edit_intent not in {"exact_replace", "full_file"}:
        raise PatchEditProtocolError(
            f"{change_pointer}: unsupported edit_intent {edit_intent!r}"
        )

    file_path = _normalize_path(change.get("file_path"))
    action = str(change.get("action") or "modify").strip()
    before = source_files.get(file_path)
    if edit_intent == "exact_replace":
        content_after = _apply_exact_replace(
            change,
            file_path=file_path,
            action=action,
            before=before,
            change_pointer=change_pointer,
        )
    else:
        content_after = _full_file_content_after(change)
        if action == "delete":
            content_after = ""
        _validate_optional_source_digest(
            change,
            file_path=file_path,
            before=before,
            change_pointer=change_pointer,
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
        content_after=content_after,
        change_pointer=change_pointer,
    )
    return change, [metadata]


def _apply_exact_replace(
    change: Mapping[str, Any],
    *,
    file_path: str,
    action: str,
    before: str | None,
    change_pointer: str,
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
    if expected_digest != actual_digest:
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
    occurrences = before.count(old_string)
    if occurrences == 0:
        raise PatchEditProtocolError(
            f"{change_pointer}: old_string_not_found in {file_path}"
        )
    replace_all = _bool_value(change.get("replace_all", False))
    if occurrences > 1 and not replace_all:
        raise PatchEditProtocolError(
            f"{change_pointer}: old_string_not_unique in {file_path}: "
            f"{occurrences} matches; set replace_all=true or add context"
        )
    if replace_all:
        return before.replace(old_string, new_string)
    return before.replace(old_string, new_string, 1)


def _validate_optional_source_digest(
    change: Mapping[str, Any],
    *,
    file_path: str,
    before: str | None,
    change_pointer: str,
) -> None:
    expected_digest = _digest_text(change.get("source_digest"))
    if not expected_digest or before is None:
        return
    actual_digest = source_digest_for_content(before)
    if expected_digest != actual_digest:
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
    if not context:
        return {}
    source_files: dict[str, str] = {}
    for key in ("patch_source_files", "source_files", "editable_source_files"):
        value = context.get(key)
        if isinstance(value, Mapping):
            for path, content in value.items():
                if isinstance(content, str):
                    source_files[_normalize_path(path)] = content
    target_file = _normalize_path(context.get("target_file"))
    target_content = context.get("target_file_code")
    if target_file and _is_existing_source_text(target_content):
        source_files[target_file] = str(target_content)
    original_code = context.get("original_code")
    if isinstance(original_code, str):
        source_files.update(_parse_original_code_source(original_code))
    integration_files = context.get("solver_design_branch_current_integration_files")
    if isinstance(integration_files, str):
        source_files.update(_parse_markdown_source_files(integration_files))
    return source_files


def _parse_markdown_source_files(rendered: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for match in _SOURCE_FILE_RE.finditer(rendered):
        path = _normalize_path(match.group("path"))
        content = match.group("content")
        if path:
            files[path] = content
    return files


def _parse_original_code_source(rendered: str) -> dict[str, str]:
    match = re.search(
        r"^File:\s*(?P<path>[^\n]+)\n"
        r"(?:[^\n]*\n)*?"
        r"```(?:python)?\n"
        r"(?P<content>.*?)"
        r"\n```",
        rendered,
        re.DOTALL | re.MULTILINE,
    )
    if not match:
        return {}
    path = _normalize_path(match.group("path"))
    if not path:
        return {}
    return {path: match.group("content")}


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
