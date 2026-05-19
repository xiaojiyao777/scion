"""Helpers for code-generation context assembly."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

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
) -> str:
    normalized_target = str(target_file or "").replace("\\", "/").lstrip("/")
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
        )
        lines.append(
            f"### {rel}\n"
            f"Provenance: {artifact['source']}; readable={artifact['readable']}\n"
            f"```python\n{artifact['content']}\n```"
        )
    summary_lines: list[str] = []
    for rel in _solver_design_integration_summary_files(provider):
        artifact = _read_solver_design_context_artifact(
            rel,
            source_root=source_root,
            champion_root=champion_root,
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
