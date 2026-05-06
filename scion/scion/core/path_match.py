"""Segment-aware POSIX path glob matching for contract target checks."""
from __future__ import annotations

import re
from pathlib import PurePosixPath


def normalize_relative_glob_pattern(pattern: str) -> str:
    """Return a normalized relative POSIX glob pattern.

    Patterns are configuration, not candidate patch paths, so wildcard
    characters are allowed.  Path traversal, absolute paths, and ambiguous
    separators remain invalid.
    """
    if not isinstance(pattern, str):
        raise ValueError("glob pattern must be a string")
    if pattern == "" or pattern != pattern.strip():
        raise ValueError("glob pattern must be a non-empty trimmed path")
    if "\x00" in pattern:
        raise ValueError("glob pattern contains NUL byte")
    if "\\" in pattern:
        raise ValueError("glob pattern must use POSIX '/' separators")

    path = PurePosixPath(pattern)
    if path.is_absolute():
        raise ValueError("glob pattern must be relative")

    parts = pattern.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("glob pattern contains empty, '.', or '..' path segment")
    return PurePosixPath(*parts).as_posix()


def segment_glob_match(path: str, pattern: str) -> bool:
    """Match POSIX-style globs without letting wildcards cross segments."""
    path_parts = tuple(PurePosixPath(path).parts)
    pattern_parts = tuple(PurePosixPath(pattern).parts)
    return _match_path_parts(path_parts, pattern_parts)


def _match_path_parts(path_parts: tuple[str, ...], pattern_parts: tuple[str, ...]) -> bool:
    if not pattern_parts:
        return not path_parts
    head, *tail = pattern_parts
    tail_parts = tuple(tail)
    if head == "**":
        return any(
            _match_path_parts(path_parts[index:], tail_parts)
            for index in range(len(path_parts) + 1)
        )
    if not path_parts:
        return False
    return _glob_segment_match(path_parts[0], head) and _match_path_parts(
        path_parts[1:],
        tail_parts,
    )


def _glob_segment_match(value: str, pattern: str) -> bool:
    regex = "^" + _glob_segment_regex(pattern) + "$"
    return re.match(regex, value) is not None


def _glob_segment_regex(pattern: str) -> str:
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            parts.append("[^/]*")
        elif char == "?":
            parts.append("[^/]")
        elif char == "[":
            end = index + 1
            if end < len(pattern) and pattern[end] in {"!", "^"}:
                end += 1
            if end < len(pattern) and pattern[end] == "]":
                end += 1
            while end < len(pattern) and pattern[end] != "]":
                end += 1
            if end >= len(pattern):
                parts.append(re.escape(char))
            else:
                content = pattern[index + 1 : end]
                if content.startswith("!"):
                    content = "^" + content[1:]
                elif content.startswith("^"):
                    content = "\\" + content
                parts.append("[" + content + "]")
                index = end
        else:
            parts.append(re.escape(char))
        index += 1
    return "".join(parts)
