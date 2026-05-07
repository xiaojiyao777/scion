"""Generic metadata helpers shared by verification runtime checks."""
from __future__ import annotations

from typing import Any, Mapping


def requires_adapter_for_runtime(
    problem_spec: Any | None,
    *,
    explicit: bool = False,
) -> bool:
    """Return whether runtime verification must use a ProblemAdapter."""

    if explicit:
        return True
    if problem_spec is None:
        return False
    if bool(getattr(problem_spec, "requires_adapter_for_runtime", False)):
        return True
    return (
        getattr(problem_spec, "spec_version", None) == "problem-v1"
        and bool(getattr(problem_spec, "adapter_import_path", ""))
    )


def declared_objective_metric_names(problem_spec: Any | None) -> tuple[str, ...]:
    """Return ordered objective metric names declared by the active problem spec."""

    raw_objectives = getattr(problem_spec, "objectives", ()) if problem_spec else ()
    if raw_objectives is None or isinstance(raw_objectives, (str, bytes)):
        return ()

    names: list[str] = []
    seen: set[str] = set()
    for metric in raw_objectives:
        if isinstance(metric, str):
            name = metric.strip()
        else:
            name = str(_get_field(metric, "name") or "").strip()
        if not name or name in seen:
            continue
        names.append(name)
        seen.add(name)
    return tuple(names)


def research_surface_target_files(
    problem_spec: Any | None,
    selected_surface: str | None,
) -> tuple[str, ...]:
    """Return target file patterns for a declared research surface."""

    surface = find_research_surface(problem_spec, selected_surface)
    if surface is None:
        return ()

    targets = _get_field(surface, "targets")
    raw_files = _get_field(targets, "files") if targets is not None else None
    if raw_files is None:
        raw_files = _get_field(surface, "target_files")
    if not isinstance(raw_files, (list, tuple)):
        return ()

    patterns: list[str] = []
    seen: set[str] = set()
    for raw_pattern in raw_files:
        pattern = str(raw_pattern).strip()
        if not pattern or pattern in seen:
            continue
        patterns.append(pattern)
        seen.add(pattern)
    return tuple(patterns)


def find_research_surface(
    problem_spec: Any | None,
    selected_surface: str | None,
) -> Any | None:
    """Return a declared research surface by name, if present."""

    surface_name = (selected_surface or "").strip()
    if not surface_name:
        return None
    surfaces = getattr(problem_spec, "research_surfaces", None)
    if not surfaces:
        return None
    for surface in surfaces:
        if _get_field(surface, "name") == surface_name:
            return surface
    return None


def _get_field(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)
