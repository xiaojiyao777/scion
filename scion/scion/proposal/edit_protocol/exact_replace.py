"""Exact-replace validation and application for typed edit normalization."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from scion.proposal.edit_protocol.errors import (
    PatchEditProtocolError,
    raise_duplicate_file_error,
)
from scion.proposal.edit_protocol.source_discovery import source_digest_for_content

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
            f"{change_pointer}: exact_replace has no host source binding"
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
    replace_all = _bool_value(change.get("replace_all", False))
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
        blank_line_adjusted = None
        if not replace_all:
            blank_line_adjusted = _apply_blank_line_run_count_drift(
                before=before,
                old_string=old_string,
                new_string=new_string,
            )
        if blank_line_adjusted is not None:
            if isinstance(change, dict):
                change["_host_blank_line_run_count_tolerated"] = True
            return blank_line_adjusted
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


def _apply_blank_line_run_count_drift(
    *,
    before: str,
    old_string: str,
    new_string: str,
) -> str | None:
    """Apply one unambiguous selector whose internal blank-run counts drifted.

    Every non-blank source byte remains part of the exact selector. Only the
    number of completely empty lines in an existing internal run is flexible;
    zero-line gaps, whitespace-only lines, and line-ending changes do not
    match. Leading and trailing blank runs are deliberately unsupported
    because they do not provide two-sided source anchors.
    """

    pattern = _blank_line_run_pattern(old_string)
    if pattern is None:
        return None
    matcher = re.compile(f"(?=(?P<candidate>{pattern}))")
    matches = [match.span("candidate") for match in matcher.finditer(before)]
    if len(matches) != 1:
        return None
    start, end = matches[0]
    return before[:start] + new_string + before[end:]


def _blank_line_run_pattern(selector: str) -> str | None:
    lines = selector.splitlines(keepends=True)
    if len(lines) < 3 or _empty_line_ending(lines[0]) is not None:
        return None
    if _empty_line_ending(lines[-1]) is not None:
        return None

    parts: list[str] = []
    has_blank_run = False
    index = 0
    while index < len(lines):
        ending = _empty_line_ending(lines[index])
        if ending is None:
            parts.append(re.escape(lines[index]))
            index += 1
            continue

        has_blank_run = True
        run_ending = ending
        index += 1
        while index < len(lines):
            next_ending = _empty_line_ending(lines[index])
            if next_ending is None:
                break
            if next_ending != run_ending:
                return None
            index += 1
        parts.append(f"(?:{re.escape(run_ending)})+")

    if not has_blank_run:
        return None
    return "".join(parts)


def _empty_line_ending(line: str) -> str | None:
    if line in {"\n", "\r\n", "\r"}:
        return line
    return None


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
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    start = 0
    while True:
        index = before.find(old_string, start)
        if index < 0:
            break
        line, column = _line_column_for_offset(before, index)
        line_start = before.rfind("\n", 0, index) + 1
        line_end = before.find("\n", index + len(old_string))
        if line_end < 0:
            line_end = len(before)
        candidates.append(
            {
                "line": line,
                "column": column,
                "line_content": before[line_start:line_end],
                "match": old_string,
            }
        )
        start = index + max(1, len(old_string))
    return candidates


def _line_column_for_offset(text: str, offset: int) -> tuple[int, int]:
    safe_offset = max(0, min(len(text), offset))
    line = text.count("\n", 0, safe_offset) + 1
    line_start = text.rfind("\n", 0, safe_offset) + 1
    return line, safe_offset - line_start + 1


def _strip_digest_prefix(value: str) -> str:
    return value[7:] if value.startswith("sha256:") else value


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
