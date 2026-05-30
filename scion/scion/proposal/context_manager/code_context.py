"""Helpers for code-generation context assembly."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence

from scion.config.problem import ProblemSpec
from scion.core.models import ChampionState
from scion.proposal.context.surfaces import _find_research_surface

from .io import (
    _list_champion_surface_files,
    _python_api_manifest_for_file,
    _read_champion_operators,
    _read_solver_design_context_artifact,
    _read_surface_file,
)

def _read_champion_research_code(
    champion: ChampionState,
    *,
    research_surfaces: list[Any],
    include_operator_files: bool = True,
) -> str:
    sections: list[str] = []
    if include_operator_files:
        operator_code = _read_champion_operators(champion)
        if operator_code:
            sections.append(operator_code)

    for file_rel in _list_champion_surface_files(
        champion,
        research_surfaces=research_surfaces,
    ):
        sections.append(
            _read_surface_file(champion, file_rel, label="research surface")
        )
    return "\n\n".join(sections) if sections else "(no research-surface files found)"

def _read_reference_operators(
    champion: ChampionState,
    change_locus: str,
    problem_spec: ProblemSpec,
    *,
    research_surfaces: Optional[list[Any]] = None,
) -> str:
    """Read same-surface operators as reference for create_new actions."""
    surface = _find_research_surface(research_surfaces or [], change_locus)
    if surface is not None and getattr(surface, "kind", "operator") != "operator":
        return ""
    operators_dir = os.path.join(champion.code_snapshot_path, "operators")
    if not os.path.isdir(operators_dir):
        return ""

    # Map operator files to categories via pool config, or fall back to reading all
    sections: List[str] = []
    filenames = sorted(
        f for f in os.listdir(operators_dir)
        if f.endswith(".py") and f not in ("__init__.py", "base.py")
    )
    # Read up to 2 reference operators
    count = 0
    for fname in filenames:
        if count >= 2:
            break
        fpath = os.path.join(operators_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as fh:
                content = fh.read()
            sections.append(f"### operators/{fname} (reference)\n```python\n{content}\n```")
            count += 1
        except OSError:
            pass
    return "\n\n".join(sections)

def _build_solver_design_api_manifest(
    *,
    source_root: str,
    champion_root: str,
    target_file: Optional[str],
    provider: Any | None = None,
) -> str:
    root = Path(source_root or champion_root).expanduser()
    fallback_root = Path(champion_root).expanduser()
    normalized_target = str(target_file or "").replace("\\", "/").lstrip("/")
    lines = [
        f"Approved target_file: {normalized_target or '(none)'}",
        (
            "Exact importable module API from the current branch snapshot. "
            "Use these names instead of inventing sibling helper imports."
        ),
    ]
    for rel in _solver_design_api_manifest_files(
        provider,
        fallback=(normalized_target,),
    ):
        path = root / rel
        if not path.is_file() and fallback_root != root:
            path = fallback_root / rel
        summary = _python_api_manifest_for_file(path)
        if summary:
            lines.append(f"- {rel}: {summary}")
    target_guidance = _solver_design_target_api_guidance(
        provider,
        normalized_target,
    )
    if target_guidance:
        lines.append(target_guidance)
    return "\n".join(lines)

def _build_solver_design_branch_current_integration_files(
    *,
    source_root: str,
    champion_root: str,
    target_file: Optional[str],
    provider: Any | None = None,
    branch_created_files: Sequence[str] = (),
    branch_touched_files: Sequence[str] = (),
    branch_current_file_sources: Mapping[str, str] | None = None,
) -> str:
    normalized_target = str(target_file or "").replace("\\", "/").lstrip("/")
    branch_current_paths = _branch_current_context_paths(
        branch_created_files,
        branch_touched_files,
    )
    lines = [
        (
            "These files are branch-current integration context for "
            "solver_design additional_changes. The approved target full "
            "content remains the Target File section; use this section only "
            "for minimal necessary wiring based on current content."
        ),
        f"Approved target_file: {normalized_target or '(none)'}",
    ]
    for rel in _solver_design_integration_full_files(
        provider,
        fallback=(normalized_target,),
    ):
        artifact = _read_solver_design_context_artifact(
            rel,
            source_root=source_root,
            champion_root=champion_root,
            source_overrides=branch_current_file_sources,
            allow_champion_fallback=(rel not in branch_current_paths),
        )
        lines.append(_render_solver_design_context_artifact(rel, artifact))
    helper_projection = _branch_created_helper_source_projection(
        branch_current_paths,
        source_root=source_root,
        champion_root=champion_root,
        target_file=normalized_target,
        branch_current_file_sources=branch_current_file_sources,
    )
    if helper_projection:
        lines.append(helper_projection)
    summary_lines: list[str] = []
    for rel in _solver_design_integration_summary_files(provider):
        artifact = _read_solver_design_context_artifact(
            rel,
            source_root=source_root,
            champion_root=champion_root,
            source_overrides=branch_current_file_sources,
        )
        summary = _python_api_manifest_for_file(Path(str(artifact["path"])))
        if not summary:
            summary = artifact["reason"]
        summary_lines.append(
            f"- {rel}: provenance={artifact['source']}; {summary}"
        )
    if summary_lines:
        lines.append(
            "### Compact sibling API summaries\n" + "\n".join(summary_lines)
        )
    return "\n\n".join(lines)


_BRANCH_CREATED_HELPER_MAX_FILES = 3
_BRANCH_CREATED_HELPER_MAX_CHARS = 16000


def _branch_created_helper_source_projection(
    files: Sequence[str],
    *,
    source_root: str,
    champion_root: str,
    target_file: str,
    branch_current_file_sources: Mapping[str, str] | None = None,
) -> str:
    selected: list[str] = []
    target = str(target_file or "").replace("\\", "/").lstrip("/")
    for item in files or ():
        rel = str(item or "").replace("\\", "/").lstrip("/")
        if not rel or rel == target:
            continue
        if rel in selected:
            continue
        selected.append(rel)
        if len(selected) >= _BRANCH_CREATED_HELPER_MAX_FILES:
            break
    if not selected:
        return ""
    lines = [
        "#### Branch-Created Helper Sources",
        (
            "Receipt: same-branch created or touched helper files are included "
            "for bounded cross-target follow-up context. Use them as "
            "branch-current source when the approved target integrates, "
            "repairs, or redirects prior branch-local work."
        ),
    ]
    for rel in selected:
        artifact = _read_solver_design_context_artifact(
            rel,
            source_root=source_root,
            champion_root=champion_root,
            source_overrides=branch_current_file_sources,
            allow_champion_fallback=False,
        )
        content = str(artifact["content"])
        truncated = False
        if len(content) > _BRANCH_CREATED_HELPER_MAX_CHARS:
            content = content[:_BRANCH_CREATED_HELPER_MAX_CHARS].rstrip()
            truncated = True
        lines.append(
            _render_solver_design_context_artifact(
                rel,
                {**artifact, "content": content},
                branch_created_helper=True,
                truncated=truncated,
            )
        )
    return "\n\n".join(lines)


def _branch_current_context_paths(
    branch_created_files: Sequence[str],
    branch_touched_files: Sequence[str],
) -> tuple[str, ...]:
    paths: list[str] = []
    for collection in (branch_created_files, branch_touched_files):
        for item in collection or ():
            rel = str(item or "").replace("\\", "/").lstrip("/")
            if rel and rel not in paths:
                paths.append(rel)
    return tuple(paths)


def _render_solver_design_context_artifact(
    rel: str,
    artifact: Mapping[str, Any],
    *,
    branch_created_helper: bool = False,
    truncated: bool | None = None,
) -> str:
    readable = bool(artifact.get("readable"))
    source = str(artifact.get("source") or "missing_current_source")
    flags = [
        f"Provenance: {source}",
        f"readable={readable}",
        f"source_status={'current_branch_source' if readable else 'missing_current_source'}",
    ]
    if branch_created_helper:
        flags.append("branch_created_helper=True")
    if truncated is not None:
        flags.append(f"truncated={truncated}")
    header = f"### {rel}\n" + "; ".join(flags)
    if readable:
        return f"{header}\n```python\n{artifact['content']}\n```"
    return (
        f"{header}\n"
        "visibility=not_visible; content_status=missing_current_source\n"
        f"Current branch source for {rel} is unavailable. Do not treat this "
        "placeholder as editable source; read the current branch file before "
        "using exact_replace or choose a target with visible current source.\n"
        f"```python\n{artifact['content']}\n```"
    )

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
    items = tuple(
        str(item or "").replace("\\", "/").lstrip("/")
        for item in (raw_items or ())
        if str(item or "").strip()
    )
    return items or tuple(item for item in fallback if item)
