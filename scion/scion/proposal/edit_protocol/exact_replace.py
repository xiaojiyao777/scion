"""Exact-replace validation and application for typed edit normalization."""

from __future__ import annotations

import json
from typing import Any, Mapping

from scion.proposal.edit_protocol.errors import (
    PatchEditProtocolError,
    raise_duplicate_file_error,
)
from scion.proposal.edit_protocol.source_discovery import source_digest_for_content

_NEAR_WHOLE_FILE_EXACT_REPLACE_MIN_CHARS = 2000
_NEAR_WHOLE_FILE_EXACT_REPLACE_MAX_COVERAGE = 0.85
_RECOMMENDED_EXACT_REPLACE_MAX_COVERAGE = 0.35


def apply_exact_replace(
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
    expected_digest = digest_text(change.get("source_digest"))
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
        eof_adjusted = _apply_eof_final_newline_drift(
            before=before,
            old_string=old_string,
            new_string=new_string,
        )
        if eof_adjusted is not None:
            if isinstance(change, dict):
                change["_host_eof_final_newline_tolerated"] = True
            return eof_adjusted
        if composing_same_file:
            raise_duplicate_file_error(
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


def validate_optional_source_digest(
    change: Mapping[str, Any],
    *,
    file_path: str,
    before: str | None,
    original_before: str | None = None,
    change_pointer: str,
    allow_original_source_digest: bool = False,
) -> None:
    expected_digest = digest_text(change.get("source_digest"))
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


def digest_text(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ("sha256", "digest", "source_digest"):
            text = str(value.get(key) or "").strip()
            if text:
                return _strip_digest_prefix(text)
        return ""
    if value is None:
        return ""
    return _strip_digest_prefix(str(value).strip())


def _apply_eof_final_newline_drift(
    *,
    before: str,
    old_string: str,
    new_string: str,
) -> str | None:
    """Tolerate selectors copied with one terminal newline absent in source."""
    if old_string.endswith("\r\n"):
        old_adjusted = old_string[:-2]
        new_adjusted = new_string[:-2] if new_string.endswith("\r\n") else new_string
    elif old_string.endswith("\n"):
        old_adjusted = old_string[:-1]
        new_adjusted = new_string[:-1] if new_string.endswith("\n") else new_string
    else:
        return None
    if not old_adjusted or before.endswith(old_string):
        return None
    if not before.endswith(old_adjusted):
        return None
    return before[: len(before) - len(old_adjusted)] + new_adjusted


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


def _strip_digest_prefix(value: str) -> str:
    return value[7:] if value.startswith("sha256:") else value


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
