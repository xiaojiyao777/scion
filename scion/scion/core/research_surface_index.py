"""Research-surface file selectors shared by generic Scion core code."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from scion.core.path_match import normalize_relative_glob_pattern


def editable_patterns(problem_spec: Any | None) -> tuple[str, ...]:
    """Return normalized editable file patterns for a problem spec.

    Surface declarations are the preferred source of truth.  Older specs that
    do not declare research surfaces fall back to ``search_space.editable``.
    """
    patterns = list(_research_surface_target_patterns(problem_spec))
    if not patterns:
        search_space = _field(problem_spec, "search_space")
        patterns = list(_field(search_space, "editable", []) or [])
        if not patterns:
            patterns = list(_field(problem_spec, "search_space_editable", []) or [])
    return normalize_editable_patterns(patterns)


def normalize_editable_patterns(patterns: Iterable[Any]) -> tuple[str, ...]:
    """Normalize and deduplicate editable glob patterns."""
    normalized: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        value = _normalize_editable_pattern(pattern)
        if value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return tuple(normalized)


def _research_surface_target_patterns(problem_spec: Any | None) -> Iterable[Any]:
    for surface in _field(problem_spec, "research_surfaces", []) or []:
        targets = _field(surface, "targets")
        if targets is not None:
            files = _field(targets, "files")
            if files is not None:
                yield from files
                continue
        yield from (_field(surface, "target_files", []) or [])


def _normalize_editable_pattern(pattern: Any) -> str:
    if not isinstance(pattern, str):
        pattern = str(pattern)
    if (
        pattern.endswith("/")
        and not pattern.startswith("/")
        and not pattern.endswith("//")
    ):
        pattern = pattern[:-1]
    return normalize_relative_glob_pattern(pattern)


def _field(obj: Any | None, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)
