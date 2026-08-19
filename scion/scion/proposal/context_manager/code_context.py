"""Helpers for code-generation context assembly."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional

from scion.core.models import ChampionState
from scion.core.path_match import segment_glob_match
from scion.core.paths import normalize_relative_patch_path
from scion.proposal.context.surfaces import surface_target_files

from .io import (
    _expand_surface_targets_for_root,
    _list_champion_surface_files,
    _read_champion_operators,
    _read_solver_design_context_artifact,
    _read_surface_file,
)
from .source_graph import ordered_source_paths, source_graph_roles


def _clean_history_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/").lstrip("/")
    if not text or any(part in {"", ".", ".."} for part in text.split("/")):
        return ""
    return text


def _read_champion_research_code(
    champion: ChampionState,
    *,
    research_surfaces: list[Any],
    include_operator_files: bool = True,
    excluded_paths: Sequence[str] = (),
) -> str:
    """Render hypothesis-facing champion research source."""

    excluded: set[str] = set()
    for path in excluded_paths:
        cleaned = _clean_history_path(path)
        if cleaned:
            excluded.add(cleaned)
    sections = (
        [_read_champion_operators(champion, excluded_paths=tuple(sorted(excluded)))]
        if include_operator_files
        else []
    )
    sections.extend(
        _read_surface_file(champion, path, label="research surface")
        for path in _list_champion_surface_files(
            champion, research_surfaces=research_surfaces
        )
        if path not in excluded
    )
    return "\n\n".join(section for section in sections if section)


EDITABLE_SOURCE_CONTEXT_KEY = "editable_source_context"


def _normalize_source_path(value: Any) -> str:
    try:
        return normalize_relative_patch_path(str(value or ""))
    except ValueError as exc:
        raise ValueError(f"invalid editable source path: {value!r}") from exc


def _build_editable_source_context(
    *,
    champion: ChampionState,
    selected_surface: Any | None,
    source_root: str,
    target_file: Optional[str],
    target_action: str,
    provider: Any | None,
    editable_patterns: Sequence[str],
    frozen_patterns: Sequence[str],
    development_suites: Sequence[Any] = (),
    qualified_module_prefixes: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Collect current selected-surface source and its public development tests."""

    target = _normalize_source_path(target_file)
    sources: dict[str, str | None] = {}

    def add(rel: str) -> None:
        path = _normalize_source_path(rel)
        if path in sources:
            return
        artifact = _read_solver_design_context_artifact(
            path,
            source_root=source_root,
            champion_root=champion.code_snapshot_path,
            allow_champion_fallback=False,
        )
        content = artifact.get("content")
        sources[path] = (
            content if artifact.get("readable") and isinstance(content, str) else None
        )

    declared_targets = (
        surface_target_files(selected_surface)
        if selected_surface is not None
        else list(editable_patterns)
    )
    if not any(segment_glob_match(target, pattern) for pattern in declared_targets):
        raise ValueError("approved target is outside the selected research surface")
    if not any(segment_glob_match(target, pattern) for pattern in editable_patterns):
        raise ValueError("approved target is outside the editable search space")
    if any(segment_glob_match(target, pattern) for pattern in frozen_patterns):
        raise ValueError("approved target is frozen")
    surface_paths = _expand_surface_targets_for_root(
        source_root,
        [str(path) for path in declared_targets],
    )
    add(target)
    for path in surface_paths:
        if not any(
            segment_glob_match(path, pattern) for pattern in editable_patterns
        ):
            continue
        if any(segment_glob_match(path, pattern) for pattern in frozen_patterns):
            continue
        add(path)
        if sources[path] is None and not (
            path == target and target_action in {"create", "create_new"}
        ):
            current_path = Path(source_root) / path
            if current_path.exists() or current_path.is_symlink():
                raise ValueError(
                    f"current selected-surface source is unreadable: {path}"
                )
            sources.pop(path, None)
    if target_action not in {"create", "create_new"} and sources[target] is None:
        raise ValueError(f"approved modify target has no current source: {target}")

    roles = source_graph_roles(
        sources,
        target=target,
        qualified_prefixes=qualified_module_prefixes,
    )
    ordered_paths = ordered_source_paths(roles)
    public_tests: list[dict[str, Any]] = []
    seen_paths = set(sources)
    for suite in development_suites:
        check_name = str(getattr(suite, "check_name", "") or "")
        test_path = _normalize_source_path(getattr(suite, "test_path", ""))
        if test_path in seen_paths:
            raise ValueError(
                "public development test overlaps editable source inventory: "
                f"{test_path}"
            )
        artifact = _read_solver_design_context_artifact(
            test_path,
            source_root=str(getattr(suite, "source_root", "") or ""),
            champion_root=str(getattr(suite, "source_root", "") or ""),
            allow_champion_fallback=False,
        )
        content = artifact.get("content")
        if not artifact.get("readable") or not isinstance(content, str):
            raise ValueError(f"public development test is unreadable: {test_path}")
        public_tests.append(
            {
                "path": test_path,
                "content": content,
                "check_name": check_name,
                "visible": True,
            }
        )
        seen_paths.add(test_path)
    return {
        "approved_target": target,
        "sources": [
            {
                "path": path,
                "content": sources[path],
                "roles": list(roles[path]),
                "visible": "peer" not in roles[path],
            }
            for path in ordered_paths
        ],
        "public_tests": public_tests,
        "target_api_guidance": _solver_design_target_api_guidance(provider, target),
    }


def _solver_design_target_api_guidance(
    provider: Any | None,
    target_file: str,
) -> str:
    method = getattr(provider, "solver_design_target_api_guidance", None)
    if not callable(method):
        return ""
    return str(method(target_file) or "").strip()
