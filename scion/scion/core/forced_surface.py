"""Diagnostic forced research-surface validation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scion.core.path_match import normalize_relative_glob_pattern, segment_glob_match
from scion.core.paths import normalize_relative_patch_path


KNOWN_HYPOTHESIS_ACTIONS = frozenset({"create_new", "modify", "remove"})


@dataclass(frozen=True)
class ForcedSurfaceRequest:
    """Validated one-shot request for steering proposal surface selection."""

    surface: str
    action: str | None = None
    target_file: str | None = None


def validate_forced_surface_request(
    problem_spec: Any,
    surface_name: str,
    *,
    action: str | None = None,
    target_file: str | None = None,
    adapter_spec: Any | None = None,
) -> ForcedSurfaceRequest:
    """Validate and normalize a diagnostic forced-surface request.

    The accepted surface names are only the names declared on
    ``research_surfaces``.  No problem-specific surface names are interpreted
    here.
    """
    requested_surface = _normalize_surface_name(surface_name)
    surfaces = get_declared_research_surfaces(problem_spec, adapter_spec)
    surface = find_research_surface(surfaces, requested_surface)
    if surface is None:
        declared = ", ".join(surface_names(surfaces)) or "(none)"
        raise ValueError(
            f"unknown research surface '{requested_surface}'. "
            f"Declared research surfaces: {declared}"
        )

    requested_action = _normalize_action(action)
    requested_target = _normalize_target_file(target_file)
    if requested_target is not None and not target_matches_surface(
        requested_target,
        surface,
    ):
        declared_targets = ", ".join(surface_target_files(surface)) or "(none)"
        raise ValueError(
            f"target_file '{requested_target}' is not declared for research "
            f"surface '{requested_surface}'. Declared target files: "
            f"{declared_targets}"
        )

    resolved_action, resolved_target = derive_surface_action_target(
        surface,
        action=requested_action,
        target_file=requested_target,
    )
    if resolved_action is not None and not surface_action_allowed(
        surface,
        resolved_action,
    ):
        raise ValueError(
            f"action '{resolved_action}' is not allowed for research surface "
            f"'{requested_surface}'"
        )
    if resolved_action in {"modify", "remove"} and resolved_target is None:
        raise ValueError(
            f"action '{resolved_action}' for forced research surface "
            f"'{requested_surface}' requires --force-target-file unless the "
            "surface declares exactly one concrete singleton target"
        )

    return ForcedSurfaceRequest(
        surface=requested_surface,
        action=resolved_action,
        target_file=resolved_target,
    )


def get_declared_research_surfaces(
    problem_spec: Any,
    adapter_spec: Any | None = None,
) -> list[Any]:
    for spec in (problem_spec, adapter_spec):
        surfaces = _field(spec, "research_surfaces", None)
        if surfaces:
            return list(surfaces)
    return []


def find_research_surface(surfaces: list[Any], name: str) -> Any | None:
    for surface in surfaces:
        if _field(surface, "name", None) == name:
            return surface
    return None


def surface_names(surfaces: list[Any]) -> list[str]:
    return sorted(
        name for surface in surfaces
        if (name := _field(surface, "name", None))
    )


def derive_surface_action_target(
    surface: Any,
    *,
    action: str | None = None,
    target_file: str | None = None,
) -> tuple[str | None, str | None]:
    """Return the most specific legal action/target implied by a surface.

    For singleton surfaces with one concrete target, this derives the common
    diagnostic case: ``modify`` that exact target file.  Multi-target surfaces
    are left open unless the caller explicitly supplies action/target.
    """
    resolved_action = action
    resolved_target = target_file
    singleton_target = _single_concrete_singleton_target(surface)

    if resolved_action is None:
        if resolved_target is not None:
            if surface_action_allowed(surface, "modify"):
                resolved_action = "modify"
            elif surface_action_allowed(surface, "create_new"):
                resolved_action = "create_new"
            elif surface_action_allowed(surface, "remove"):
                resolved_action = "remove"
        elif singleton_target and surface_action_allowed(surface, "modify"):
            resolved_action = "modify"
            resolved_target = singleton_target

    if resolved_target is None and resolved_action in {"modify", "remove"}:
        resolved_target = singleton_target

    return resolved_action, resolved_target


def surface_action_allowed(surface: Any, action: str) -> bool:
    attr = {
        "create_new": "create_new_allowed",
        "modify": "modify_allowed",
        "remove": "remove_allowed",
    }.get(action)
    if attr is None:
        return False
    targets = _field(surface, "targets", None)
    if targets is not None and _has_field(targets, attr):
        return bool(_field(targets, attr, False))
    default = action in {"create_new", "modify"}
    return bool(_field(surface, attr, default))


def surface_target_files(surface: Any) -> list[str]:
    targets = _field(surface, "targets", None)
    if targets is not None:
        files = _field(targets, "files", None)
        if files is not None:
            return [str(path) for path in files]
    return [str(path) for path in (_field(surface, "target_files", []) or [])]


def surface_is_singleton(surface: Any) -> bool:
    targets = _field(surface, "targets", None)
    if targets is not None and _has_field(targets, "singleton"):
        return bool(_field(targets, "singleton", False))
    return False


def target_matches_surface(file_rel: str, surface: Any) -> bool:
    try:
        normalized = normalize_relative_patch_path(file_rel)
    except ValueError:
        return False
    return any(
        _matches_target_pattern(normalized, str(pattern).lstrip("/"))
        for pattern in surface_target_files(surface)
    )


def _normalize_surface_name(surface_name: str) -> str:
    name = str(surface_name).strip()
    if not name:
        raise ValueError("forced research surface must not be empty")
    return name


def _normalize_action(action: str | None) -> str | None:
    if action is None:
        return None
    normalized = str(action).strip()
    if not normalized:
        raise ValueError("forced surface action must not be empty")
    if normalized not in KNOWN_HYPOTHESIS_ACTIONS:
        allowed = ", ".join(sorted(KNOWN_HYPOTHESIS_ACTIONS))
        raise ValueError(
            f"unknown forced surface action '{normalized}'. "
            f"Expected one of: {allowed}"
        )
    return normalized


def _normalize_target_file(target_file: str | None) -> str | None:
    if target_file is None:
        return None
    return normalize_relative_patch_path(str(target_file).strip())


def _single_concrete_singleton_target(surface: Any) -> str | None:
    if not surface_is_singleton(surface):
        return None
    concrete = [
        target.lstrip("/")
        for target in surface_target_files(surface)
        if not _contains_glob(target)
    ]
    if len(concrete) == 1:
        return concrete[0]
    return None


def _contains_glob(path: str) -> bool:
    return any(char in str(path) for char in "*?[")


def _matches_target_pattern(file_rel: str, pattern: str) -> bool:
    try:
        normalized_pattern = normalize_relative_glob_pattern(pattern)
    except ValueError:
        return False
    return segment_glob_match(file_rel, normalized_pattern)


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _has_field(obj: Any, name: str) -> bool:
    if isinstance(obj, dict):
        return name in obj
    return hasattr(obj, name)
