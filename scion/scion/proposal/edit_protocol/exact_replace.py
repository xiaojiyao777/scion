"""Exact-replace validation and application for typed edit normalization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from scion.proposal.edit_protocol.errors import PatchEditProtocolError


def apply_exact_replace(
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
    if old_string == new_string:
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_replace old_string and new_string are identical"
        )
    replace_all = _bool_value(change.get("replace_all", False))
    occurrences = before.count(old_string)
    if occurrences == 0:
        raise PatchEditProtocolError(
            f"{change_pointer}: old_string_not_found in {file_path}"
        )
    if occurrences > 1 and not replace_all:
        raise PatchEditProtocolError(
            json.dumps(
                _old_string_not_unique_payload(
                    file_path=file_path,
                    change_pointer=change_pointer,
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


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
