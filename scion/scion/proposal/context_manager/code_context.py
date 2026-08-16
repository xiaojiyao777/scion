"""Helpers for code-generation context assembly."""

from __future__ import annotations

import os
from typing import Any, Optional, Sequence

from scion.core.models import ChampionState
from scion.core.paths import normalize_relative_patch_path

from .io import (
    _list_branch_surface_files,
    _list_champion_operator_files,
    _list_champion_surface_files,
    _read_champion_operators,
    _read_solver_design_context_artifact,
    _read_surface_file,
)


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
    research_surfaces: list[Any],
    source_root: str,
    target_file: Optional[str],
    target_action: str,
    provider: Any | None,
) -> dict[str, Any]:
    """Collect each current editable source once, with no identity metadata."""

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

    add(target)
    operator_paths = _list_current_operator_files(source_root, champion)
    surface_paths = _list_branch_surface_files(
        source_root,
        research_surfaces=research_surfaces,
    )
    for path in dict.fromkeys([*operator_paths, *surface_paths]):
        add(path)
    api_paths = list(
        dict.fromkeys(
            [
                *_solver_design_api_manifest_files(provider, fallback=(target,)),
                *surface_paths,
            ]
        )
    )
    full_paths = list(
        _solver_design_integration_full_files(provider, fallback=(target,))
    )
    summary_paths = list(_solver_design_integration_summary_files(provider))
    for path in dict.fromkeys([*api_paths]):
        add(path)
    for path in dict.fromkeys([*full_paths, *summary_paths]):
        add(path)
    if target_action not in {"create", "create_new"} and sources[target] is None:
        raise ValueError(f"approved modify target has no current source: {target}")
    return {
        "approved_target": target,
        "sources": [
            {"path": path, "content": content} for path, content in sources.items()
        ],
        "target_api_guidance": _solver_design_target_api_guidance(provider, target),
    }


def _list_current_operator_files(
    source_root: str,
    champion: ChampionState,
) -> tuple[str, ...]:
    """List operator source that actually exists in the selected source tree."""

    files = {
        path
        for path in _list_champion_operator_files(champion)
        if os.path.isfile(os.path.join(source_root, path))
    }
    operators_dir = os.path.join(source_root, "operators")
    try:
        files.update(
            f"operators/{name}"
            for name in os.listdir(operators_dir)
            if name.endswith(".py")
            and name not in {"__init__.py", "base.py"}
            and os.path.isfile(os.path.join(operators_dir, name))
        )
    except OSError:
        pass
    return tuple(sorted(files))


def _solver_design_api_manifest_files(
    provider: Any | None,
    *,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    return _provider_string_sequence(
        provider,
        "solver_design_api_manifest_files",
        fallback=fallback,
    )


def _solver_design_integration_full_files(
    provider: Any | None,
    *,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    return _provider_string_sequence(
        provider,
        "solver_design_integration_full_files",
        fallback=fallback,
    )


def _solver_design_integration_summary_files(
    provider: Any | None,
) -> tuple[str, ...]:
    return _provider_string_sequence(
        provider,
        "solver_design_integration_summary_files",
        fallback=(),
    )


def _solver_design_target_api_guidance(
    provider: Any | None,
    target_file: str,
) -> str:
    method = getattr(provider, "solver_design_target_api_guidance", None)
    if not callable(method):
        return ""
    return str(method(target_file) or "").strip()


def _provider_string_sequence(
    provider: Any | None,
    method_name: str,
    *,
    fallback: tuple[str, ...],
) -> tuple[str, ...]:
    method = getattr(provider, method_name, None)
    if not callable(method):
        return tuple(item for item in fallback if item)
    try:
        raw_items = method()
    except TypeError:
        raw_items = method({})
    items: list[str] = []
    for item in raw_items or ():
        if not str(item or "").strip():
            continue
        rel = _normalize_source_path(item)
        if rel and rel not in items:
            items.append(rel)
    if items:
        return tuple(items)
    fallback_items: list[str] = []
    for item in fallback:
        if not str(item or "").strip():
            continue
        rel = _normalize_source_path(item)
        if rel and rel not in fallback_items:
            fallback_items.append(rel)
    return tuple(fallback_items)
