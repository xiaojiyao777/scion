"""File and code-reading helpers for proposal context assembly."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Mapping, Optional

from scion.core.models import ChampionState
from scion.proposal.context.surfaces import _surface_file_targets, surface_target_files

def _read_champion_operators(
    champion: ChampionState,
    *,
    excluded_paths: tuple[str, ...] = (),
) -> str:
    """Read all operator .py files from the champion snapshot directory."""
    operators_dir = os.path.join(champion.code_snapshot_path, "operators")
    if not os.path.isdir(operators_dir):
        return "(operators directory not found at champion snapshot path)"

    sections: List[str] = []
    try:
        filenames = sorted(
            f for f in os.listdir(operators_dir)
            if f.endswith(".py") and f not in ("__init__.py", "base.py")
        )
    except OSError as exc:
        return f"(could not list operators directory: {exc})"

    excluded = {
        str(item or "").replace("\\", "/").lstrip("/")
        for item in excluded_paths
    }
    for fname in filenames:
        if f"operators/{fname}" in excluded:
            continue
        fpath = os.path.join(operators_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as fh:
                content = fh.read()
            sections.append(f"### operators/{fname}\n```python\n{content}\n```")
        except OSError as exc:
            sections.append(f"### operators/{fname}\n(unreadable: {exc})")

    return "\n\n".join(sections) if sections else "(no operator files found)"

def _read_surface_file(champion: ChampionState, file_rel: str, *, label: str) -> str:
    fpath = os.path.join(champion.code_snapshot_path, file_rel)
    try:
        with open(fpath, encoding="utf-8") as fh:
            content = fh.read()
        return f"### {file_rel} ({label})\n```python\n{content}\n```"
    except OSError as exc:
        return f"### {file_rel}\n(unreadable: {exc})"

def _list_champion_operator_files(champion: ChampionState) -> list[str]:
    files: set[str] = set()
    for op in (champion.operator_pool or {}).values():
        file_path = getattr(op, "file_path", "")
        if file_path:
            files.add(file_path)

    operators_dir = os.path.join(champion.code_snapshot_path, "operators")
    if os.path.isdir(operators_dir):
        try:
            for fname in os.listdir(operators_dir):
                if fname.endswith(".py") and fname not in ("__init__.py", "base.py"):
                    files.add(f"operators/{fname}")
        except OSError:
            pass
    return sorted(files)

def _list_champion_surface_files(
    champion: ChampionState,
    *,
    research_surfaces: list[Any],
) -> list[str]:
    declared_targets: list[str] = []
    for surface in research_surfaces:
        if getattr(surface, "kind", None) == "operator":
            continue
        for target in surface_target_files(surface):
            target_text = str(target or "").strip().lstrip("/")
            if target_text and target_text not in declared_targets:
                declared_targets.append(target_text)

    # Research surfaces may declare package ownership with a wildcard.  H and
    # C must see the concrete current source files behind that declaration;
    # exposing only the wildcard/file names makes the provider choose and edit
    # mechanisms without seeing their implementation.
    expanded = _expand_surface_targets_for_champion(champion, declared_targets)
    return sorted(
        {
            file_rel
            for file_rel in expanded
            if "*" not in file_rel
            and os.path.isfile(os.path.join(champion.code_snapshot_path, file_rel))
        }
    )

def _expand_surface_targets_for_champion(
    champion: ChampionState,
    targets: list[str],
) -> list[str]:
    return _expand_surface_targets_for_root(
        getattr(champion, "code_snapshot_path", ""),
        targets,
    )


def _expand_surface_targets_for_root(
    root_dir: str | None,
    targets: list[str],
) -> list[str]:
    if not targets:
        return []
    root_text = str(root_dir or "").strip()
    root = Path(root_text).expanduser() if root_text else None
    concrete: list[str] = []
    patterns: list[str] = []
    for raw_target in targets:
        target = str(raw_target or "").strip().lstrip("/")
        if not target:
            continue
        if "*" not in target:
            _append_unique(concrete, target)
            continue
        if root is not None and root.is_dir():
            try:
                for path in sorted(root.glob(target)):
                    if not path.is_file():
                        continue
                    try:
                        rel = path.relative_to(root).as_posix()
                    except ValueError:
                        continue
                    if rel.endswith("/__init__.py"):
                        continue
                    _append_unique(concrete, rel)
            except OSError:
                pass
        _append_unique(patterns, target)
    return concrete + [pattern for pattern in patterns if pattern not in concrete]


def _list_branch_surface_files(
    branch_workspace: str | None,
    *,
    research_surfaces: list[Any],
) -> list[str]:
    if not branch_workspace:
        return []
    targets: list[str] = []
    for surface in research_surfaces:
        if getattr(surface, "kind", None) == "operator":
            continue
        for target in surface_target_files(surface):
            target_text = str(target or "").strip().lstrip("/")
            if target_text:
                targets.append(target_text)
    return [
        item
        for item in _expand_surface_targets_for_root(branch_workspace, targets)
        if "*" not in item
    ]

def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)

def _read_solver_design_context_artifact(
    rel: str,
    *,
    source_root: str,
    champion_root: str,
    source_overrides: Mapping[str, str] | None = None,
    allow_champion_fallback: bool = True,
) -> dict[str, Any]:
    normalized = rel.replace("\\", "/").lstrip("/")
    override = (source_overrides or {}).get(normalized)
    if isinstance(override, str):
        return {
            "path": Path(source_root or champion_root or "") / normalized,
            "source": "branch_history_current",
            "readable": True,
            "reason": "ok",
            "content": override,
        }
    roots: list[tuple[Path, str]] = []
    if source_root:
        source = Path(source_root).expanduser()
        champion = Path(champion_root).expanduser() if champion_root else None
        source_kind = (
            "branch_workspace"
            if champion is not None and source.resolve() != champion.resolve()
            else "champion_snapshot"
        )
        roots.append((source, source_kind))
    if champion_root and allow_champion_fallback:
        fallback = Path(champion_root).expanduser()
        if not roots or fallback.resolve() != roots[0][0].resolve():
            roots.append((fallback, "champion_snapshot_fallback"))
    for root, source_kind in roots:
        path = root / normalized
        try:
            resolved_root = root.resolve(strict=True)
            if root.is_symlink():
                continue
            cursor = root
            if any(
                (cursor := cursor / part).is_symlink()
                for part in Path(normalized).parts
            ):
                continue
            resolved_path = path.resolve(strict=True)
            resolved_path.relative_to(resolved_root)
            if not resolved_path.is_file():
                continue
            return {
                "path": resolved_path,
                "source": source_kind,
                "readable": True,
                "reason": "ok",
                "content": resolved_path.read_text(encoding="utf-8"),
            }
        except (OSError, ValueError):
            continue
    return {
        "path": Path(source_root or champion_root or "") / normalized,
        "source": "missing_current_source",
        "readable": False,
        "reason": "not_found",
        "content": f"# could not read {normalized}",
    }

def _read_branch_code_projection(
    branch_workspace: str,
    champion: ChampionState,
    *,
    research_surfaces: Optional[list[Any]] = None,
    include_operator_files: bool = True,
) -> tuple[Optional[str], tuple[str, ...]]:
    """Return branch-current source plus paths that differ from champion.

    The path projection lets callers render one complete current source owner
    per file: unchanged files from champion and changed files from the branch.
    No size threshold, diff compaction, summarization, or truncation is used.
    """

    if not os.path.isdir(branch_workspace):
        return None, ()

    sections: List[str] = []
    changed_paths: list[str] = []

    def record_changed(path: str) -> None:
        normalized = str(path or "").replace("\\", "/").lstrip("/")
        if normalized and normalized not in changed_paths:
            changed_paths.append(normalized)

    if include_operator_files:
        branch_ops_dir = os.path.join(branch_workspace, "operators")
        champ_ops_dir = os.path.join(champion.code_snapshot_path, "operators")
    else:
        branch_ops_dir = ""
        champ_ops_dir = ""

    if include_operator_files and os.path.isdir(branch_ops_dir):
        try:
            filenames = sorted(
                f for f in os.listdir(branch_ops_dir)
                if f.endswith(".py") and f not in ("__init__.py", "base.py")
            )
        except OSError:
            filenames = []

        for fname in filenames:
            branch_path = os.path.join(branch_ops_dir, fname)
            champ_path = os.path.join(champ_ops_dir, fname)

            try:
                with open(branch_path, encoding="utf-8") as fh:
                    branch_content = fh.read()
            except OSError:
                continue

            try:
                with open(champ_path, encoding="utf-8") as fh:
                    champ_content = fh.read()
            except OSError:
                champ_content = None

            if champ_content is None or branch_content != champ_content:
                record_changed(f"operators/{fname}")
                sections.append(
                    f"### operators/{fname} (branch version)\n```python\n{branch_content}\n```"
                )

        if os.path.isdir(champ_ops_dir):
            try:
                champion_filenames = sorted(
                    f for f in os.listdir(champ_ops_dir)
                    if f.endswith(".py") and f not in ("__init__.py", "base.py")
                )
            except OSError:
                champion_filenames = []
            for fname in champion_filenames:
                if not os.path.isfile(os.path.join(branch_ops_dir, fname)):
                    deleted_path = f"operators/{fname}"
                    record_changed(deleted_path)
                    sections.append(
                        f"### {deleted_path} (deleted from branch)\n"
                        "(file is absent from the current branch workspace)"
                    )

    branch_surface_files = _list_branch_surface_files(
        branch_workspace,
        research_surfaces=research_surfaces or [],
    )
    exact_surface_files = _surface_file_targets(research_surfaces or [])
    for file_rel in sorted(set(exact_surface_files) | set(branch_surface_files)):
        branch_path = os.path.join(branch_workspace, file_rel)
        champ_path = os.path.join(champion.code_snapshot_path, file_rel)
        if not os.path.isfile(branch_path):
            continue
        try:
            with open(branch_path, encoding="utf-8") as fh:
                branch_content = fh.read()
        except OSError:
            continue
        try:
            with open(champ_path, encoding="utf-8") as fh:
                champ_content = fh.read()
        except OSError:
            champ_content = None
        if champ_content is None or branch_content != champ_content:
            record_changed(file_rel)
            sections.append(
                f"### {file_rel} (branch research-surface version)\n"
                f"```python\n{branch_content}\n```"
            )

    for file_rel in _list_champion_surface_files(
        champion,
        research_surfaces=research_surfaces or [],
    ):
        if not os.path.isfile(os.path.join(branch_workspace, file_rel)):
            record_changed(file_rel)
            sections.append(
                f"### {file_rel} (deleted from branch)\n"
                "(file is absent from the current branch workspace)"
            )

    return (
        "\n\n".join(sections) if sections else None,
        tuple(changed_paths),
    )
