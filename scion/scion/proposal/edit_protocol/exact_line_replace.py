"""Indentation-relative full-line replacement for typed edit normalization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from scion.proposal.edit_protocol.errors import (
    PatchEditProtocolError,
    raise_duplicate_file_error,
)
from scion.proposal.edit_protocol.exact_replace import digest_text
from scion.proposal.edit_protocol.source_discovery import source_digest_for_content


@dataclass(frozen=True)
class ExactLineReplaceResult:
    """Canonical source content and the snapshot match cardinality."""

    content_after: str
    match_count: int


@dataclass(frozen=True)
class _LineMatch:
    start: int
    end: int
    outer_indent: str
    eol: str


def apply_exact_line_replace(
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
) -> ExactLineReplaceResult:
    """Replace complete logical lines while replaying their outer indentation."""

    if action != "modify":
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_line_replace requires action='modify'"
        )
    if before is None:
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_line_replace source unavailable for {file_path}"
        )
    _validate_required_source_digest(
        change,
        file_path=file_path,
        before=before,
        original_before=original_before,
        change_pointer=change_pointer,
        allow_original_source_digest=allow_original_source_digest,
    )

    old_string = change.get("old_string")
    new_string = change.get("new_string")
    if not isinstance(old_string, str) or old_string == "":
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_line_replace requires non-empty old_string"
        )
    if "\r" in old_string or "\n" in old_string:
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_line_replace old_string must be one line body"
        )
    if old_string.startswith((" ", "\t")):
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_line_replace old_string must not include "
            "leading indentation"
        )
    if not isinstance(new_string, str):
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_line_replace requires new_string"
        )
    if "\r" in new_string:
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_line_replace new_string must use LF only"
        )
    if new_string and new_string.endswith("\n"):
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_line_replace new_string must not include "
            "a terminal line ending"
        )

    matches = _find_line_matches(before, old_string)
    if not matches:
        if composing_same_file:
            raise_duplicate_file_error(
                reason="exact_line_replace_not_serializable",
                file_path=file_path,
                change_pointer=change_pointer,
                prior_change_pointers=prior_change_pointers,
                detail=(
                    "exact_line_replace old_string does not match a complete "
                    "line in the content after prior same-file edits"
                ),
            )
        raise PatchEditProtocolError(
            f"{change_pointer}: old_line_not_found in {file_path}"
        )
    replace_all = _bool_value(change.get("replace_all", False))
    if len(matches) > 1 and not replace_all:
        raise PatchEditProtocolError(
            f"{change_pointer}: old_line_not_unique in {file_path}: "
            f"found {len(matches)} complete-line matches"
        )
    selected = matches if replace_all else matches[:1]
    if new_string and "\n" in new_string and any(not match.eol for match in selected):
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_line_replace cannot insert multiple lines "
            "at an unterminated EOF line"
        )

    pieces: list[str] = []
    cursor = 0
    for match in selected:
        pieces.append(before[cursor : match.start])
        pieces.append(
            _replacement_text(
                new_string,
                outer_indent=match.outer_indent,
                eol=match.eol,
            )
        )
        cursor = match.end
    pieces.append(before[cursor:])
    content_after = "".join(pieces)
    if before and not content_after.strip():
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_line_replace_empty_file_modify in "
            f"{file_path}; use action='delete' to delete the file"
        )
    return ExactLineReplaceResult(
        content_after=content_after,
        match_count=len(selected),
    )


def _validate_required_source_digest(
    change: Mapping[str, Any],
    *,
    file_path: str,
    before: str,
    original_before: str | None,
    change_pointer: str,
    allow_original_source_digest: bool,
) -> None:
    expected_digest = digest_text(change.get("source_digest"))
    if not expected_digest:
        raise PatchEditProtocolError(
            f"{change_pointer}: exact_line_replace has no host source binding"
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


def _find_line_matches(source: str, old_string: str) -> list[_LineMatch]:
    matches: list[_LineMatch] = []
    for start, end, body, eol in _logical_lines(source):
        unindented = body.lstrip(" \t")
        if unindented != old_string:
            continue
        matches.append(
            _LineMatch(
                start=start,
                end=end,
                outer_indent=body[: len(body) - len(unindented)],
                eol=eol,
            )
        )
    return matches


def _logical_lines(source: str) -> list[tuple[int, int, str, str]]:
    lines: list[tuple[int, int, str, str]] = []
    start = 0
    cursor = 0
    while cursor < len(source):
        if source[cursor] not in {"\r", "\n"}:
            cursor += 1
            continue
        eol_start = cursor
        eol = (
            "\r\n"
            if source[cursor] == "\r" and source[cursor : cursor + 2] == "\r\n"
            else source[cursor]
        )
        end = eol_start + len(eol)
        lines.append((start, end, source[start:eol_start], eol))
        start = end
        cursor = end
    if start < len(source):
        lines.append((start, len(source), source[start:], ""))
    return lines


def _replacement_text(new_string: str, *, outer_indent: str, eol: str) -> str:
    if new_string == "":
        return ""
    relative_lines = new_string.split("\n")
    replayed = [
        "" if not relative.strip() else outer_indent + relative
        for relative in relative_lines
    ]
    return eol.join(replayed) + eol


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
