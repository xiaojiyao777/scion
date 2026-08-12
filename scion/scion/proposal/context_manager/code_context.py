"""Helpers for code-generation context assembly."""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Sequence

from scion.core.candidate_disposition import (
    CandidateDisposition,
    CandidateDispositionError,
    CandidateDispositionMapper,
)
from scion.core.models import (
    Branch,
    ChampionState,
    DecisionOutcome,
    StepRecord,
    patch_file_changes,
)
from scion.core.paths import normalize_relative_patch_path

from .io import (
    _list_champion_operator_files,
    _list_champion_surface_files,
    _read_champion_operators,
    _read_solver_design_context_artifact,
    _read_surface_file,
)

DURABLE_BRANCH_CREATED_FILES_KEY = "verified_branch_created_files"
DURABLE_BRANCH_TOUCHED_FILES_KEY = "verified_branch_touched_files"


def _branch_steps(
    branch: Branch,
    steps: Sequence[StepRecord],
) -> tuple[StepRecord, ...]:
    return tuple(step for step in steps if step.branch_id == branch.branch_id)


def _verified_branch_steps(
    branch: Branch,
    steps: Sequence[StepRecord],
) -> tuple[StepRecord, ...]:
    """Return only patch facts that reached the durable verified workspace."""

    return tuple(
        step
        for step in _branch_steps(branch, steps)
        if step.verification_passed
        and step.patch is not None
        and _step_can_own_branch_source(step)
    )


def _step_can_own_branch_source(step: StepRecord) -> bool:
    """Accept branch source only for an explicit code-retaining disposition."""

    if step.decision is None or step.decision_features_snapshot is None:
        return False
    try:
        plan = CandidateDispositionMapper.map(
            DecisionOutcome(
                decision=step.decision,
                reason_codes=tuple(step.decision_reason_codes or ()),
                features_snapshot=step.decision_features_snapshot,
            )
        )
    except (CandidateDispositionError, TypeError):
        return False
    return plan.disposition in {
        CandidateDisposition.PROVISIONAL_HEAD,
        CandidateDisposition.EXACT_REUSE,
        CandidateDisposition.PROMOTE_EXACT,
    }


def _clean_history_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/").lstrip("/")
    if not text or any(part in {"", ".", ".."} for part in text.split("/")):
        return ""
    return text


def _append_unique_path(paths: list[str], value: Any) -> None:
    path = _clean_history_path(value)
    if path and path not in paths:
        paths.append(path)


def branch_created_files(
    branch: Branch | None,
    steps: Sequence[StepRecord] | None,
) -> tuple[str, ...]:
    """Return every file created on the durable branch history."""

    if branch is None:
        return ()
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    durable = summary.get(DURABLE_BRANCH_CREATED_FILES_KEY, [])
    if not isinstance(durable, list):
        raise ValueError("durable branch created-file history is invalid")
    files: list[str] = []
    for path in durable:
        _append_unique_path(files, path)
    for step in _verified_branch_steps(branch, steps or ()):
        hypothesis = getattr(step, "hypothesis", None)
        if getattr(hypothesis, "action", None) == "create_new":
            _append_unique_path(files, getattr(hypothesis, "target_file", ""))
        patch = getattr(step, "patch", None)
        if patch is None:
            continue
        for change in patch_file_changes(patch):
            if getattr(change, "action", None) == "create":
                _append_unique_path(files, getattr(change, "file_path", ""))
    return tuple(files)


def branch_touched_files(
    branch: Branch | None,
    steps: Sequence[StepRecord] | None,
) -> tuple[str, ...]:
    """Return every file touched on the durable branch history."""

    if branch is None:
        return ()
    summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    durable = summary.get(DURABLE_BRANCH_TOUCHED_FILES_KEY, [])
    if not isinstance(durable, list):
        raise ValueError("durable branch touched-file history is invalid")
    files: list[str] = []
    for path in durable:
        _append_unique_path(files, path)
    for step in _verified_branch_steps(branch, steps or ()):
        hypothesis = getattr(step, "hypothesis", None)
        _append_unique_path(files, getattr(hypothesis, "target_file", ""))
        patch = getattr(step, "patch", None)
        if patch is None:
            continue
        for change in patch_file_changes(patch):
            _append_unique_path(files, getattr(change, "file_path", ""))
    return tuple(files)


def branch_current_file_sources(
    branch: Branch | None,
    steps: Sequence[StepRecord] | None,
) -> dict[str, str]:
    """Reconstruct current branch-owned sources from all durable patch facts."""

    if branch is None:
        return {}
    sources: dict[str, str] = {}
    for step in _verified_branch_steps(branch, steps or ()):
        patch = getattr(step, "patch", None)
        if patch is None:
            continue
        for change in patch_file_changes(patch):
            path = _clean_history_path(getattr(change, "file_path", ""))
            action = str(getattr(change, "action", "") or "")
            if not path:
                continue
            if action == "delete":
                sources.pop(path, None)
                continue
            content = getattr(change, "code_content", None)
            if action in {"create", "modify"} and isinstance(content, str):
                sources[path] = content
    return sources


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


def _branch_current_context_paths(
    branch_created_files: Sequence[str],
    branch_touched_files: Sequence[str],
) -> tuple[str, ...]:
    paths: list[str] = []
    for collection in (branch_created_files, branch_touched_files):
        for item in collection or ():
            if not str(item or "").strip():
                continue
            rel = _normalize_source_path(item)
            if rel and rel not in paths:
                paths.append(rel)
    return tuple(paths)


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
    branch_created_files: Sequence[str] = (),
    branch_touched_files: Sequence[str] = (),
    branch_current_file_sources: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Collect each current editable source once, with no identity metadata."""

    target = _normalize_source_path(target_file)
    branch_paths = _branch_current_context_paths(
        branch_created_files, branch_touched_files
    )
    overrides = branch_current_file_sources or {}
    sources: dict[str, str | None] = {}

    def add(rel: str) -> None:
        path = _normalize_source_path(rel)
        if path in sources:
            return
        if (
            path in branch_paths
            and path not in overrides
            and _same_source_root(source_root, champion.code_snapshot_path)
        ):
            sources[path] = None
            return
        artifact = _read_solver_design_context_artifact(
            path,
            source_root=source_root,
            champion_root=champion.code_snapshot_path,
            source_overrides=overrides,
            # A durable branch touch makes absence authoritative. Falling back
            # would silently resurrect a deleted helper from the champion.
            allow_champion_fallback=path not in branch_paths,
        )
        content = artifact.get("content")
        sources[path] = (
            content if artifact.get("readable") and isinstance(content, str) else None
        )

    add(target)
    operator_paths = _list_champion_operator_files(champion)
    surface_paths = _list_champion_surface_files(
        champion, research_surfaces=research_surfaces
    )
    champion_paths = list(dict.fromkeys([*operator_paths, *surface_paths]))
    for path in champion_paths:
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
    for path in branch_paths:
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


def _same_source_root(left: str, right: str) -> bool:
    return bool(left and right) and os.path.realpath(left) == os.path.realpath(right)


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
