"""File and code-reading helpers for proposal context assembly."""
from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any, List, Optional

from scion.core.forced_surface import surface_target_files
from scion.core.models import ChampionState
from scion.proposal.context.surfaces import _surface_file_targets

def _read_champion_operators(champion: ChampionState) -> str:
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

    for fname in filenames:
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

def _build_champion_stats(champion: ChampionState) -> str:
    """Return hypothesis-facing champion baseline summary."""
    lines = ["Champion baseline: current selected solver state"]
    if champion.operator_pool:
        lines.append("Operator pool:")
        for name, op in champion.operator_pool.items():
            w = getattr(op, "weight", "?")
            cat = getattr(op, "category", "?")
            fp = getattr(op, "file_path", "?")
            lines.append(f"  - {name} [{cat}] weight={w}  file={fp}")
    else:
        lines.append("Operator pool: (not yet loaded from registry)")
    return "\n".join(lines)

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
    files: set[str] = set()
    for surface in research_surfaces:
        if getattr(surface, "kind", None) == "operator":
            continue
        for target in surface_target_files(surface):
            if "*" in str(target):
                continue
            file_rel = str(target).lstrip("/")
            if os.path.isfile(os.path.join(champion.code_snapshot_path, file_rel)):
                files.add(file_rel)
    return sorted(files)

def _available_hypothesis_actions(
    targetable_operator_files: List[str],
    *,
    targetable_policy_files: Optional[List[str]] = None,
) -> set[str]:
    actions = {"create_new"}
    if targetable_operator_files or targetable_policy_files:
        actions.add("modify")
    if targetable_operator_files:
        actions.add("remove")
    return actions

def _expand_surface_targets_for_champion(
    champion: ChampionState,
    targets: list[str],
) -> list[str]:
    if not targets:
        return []
    root_text = str(getattr(champion, "code_snapshot_path", "") or "").strip()
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

def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)

def _read_target_file(champion: ChampionState, target_file: Optional[str]) -> str:
    """Read the target file from the champion snapshot."""
    if not target_file or not champion.code_snapshot_path:
        return "(no target file specified)"
    return _read_target_file_from_root(champion.code_snapshot_path, target_file)

def _read_target_file_from_root(root: str, target_file: Optional[str]) -> str:
    if not target_file or not root:
        return "(no target file specified)"
    candidate = os.path.join(root, target_file.lstrip("/"))
    try:
        with open(candidate, encoding="utf-8") as fh:
            content = fh.read()
        return f"File: {target_file}\n```python\n{content}\n```"
    except OSError as exc:
        return f"(could not read {target_file}: {exc})"

def _read_solver_design_context_artifact(
    rel: str,
    *,
    source_root: str,
    champion_root: str,
) -> dict[str, Any]:
    normalized = rel.replace("\\", "/").lstrip("/")
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
    if champion_root:
        fallback = Path(champion_root).expanduser()
        if not roots or fallback.resolve() != roots[0][0].resolve():
            roots.append((fallback, "champion_snapshot_fallback"))
    for root, source_kind in roots:
        path = root / normalized
        try:
            if not path.is_file() or path.is_symlink():
                continue
            return {
                "path": path,
                "source": source_kind,
                "readable": True,
                "reason": "ok",
                "content": path.read_text(encoding="utf-8"),
            }
        except OSError:
            continue
    return {
        "path": Path(source_root or champion_root or "") / normalized,
        "source": "missing",
        "readable": False,
        "reason": "not_found",
        "content": f"# could not read {normalized}",
    }

def _python_api_manifest_for_file(path: Path) -> str:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return ""
    exports: list[str] = []
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            exports.append("def " + _python_signature_text(node))
        elif isinstance(node, ast.ClassDef):
            methods = [
                _python_signature_text(child)
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if methods:
                exports.append(f"class {node.name}: " + "; ".join(methods[:8]))
            else:
                exports.append(f"class {node.name}")
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                exports.extend(sorted(_assigned_names_for_manifest(target)))
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            imported = ", ".join(
                alias.asname or alias.name
                for alias in node.names
                if alias.name != "*"
            )
            if imported:
                dots = "." * int(node.level or 0)
                imports.append(f"from {dots}{node.module or ''} import {imported}")
    parts: list[str] = []
    if exports:
        parts.append("exports " + "; ".join(exports[:14]))
    if imports:
        parts.append("current imports " + "; ".join(imports[:8]))
    return " | ".join(parts)

def _python_signature_text(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = node.args
    parts: list[str] = []
    for arg in [*args.posonlyargs, *args.args]:
        parts.append(arg.arg)
    if args.vararg is not None:
        parts.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")
    for arg in args.kwonlyargs:
        parts.append(arg.arg)
    if args.kwarg is not None:
        parts.append("**" + args.kwarg.arg)
    return f"{node.name}({', '.join(parts)})"

def _assigned_names_for_manifest(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for item in node.elts:
            names.update(_assigned_names_for_manifest(item))
        return names
    return set()

def _read_branch_code(
    branch_workspace: str,
    champion: ChampionState,
    *,
    research_surfaces: Optional[list[Any]] = None,
    include_operator_files: bool = True,
) -> Optional[str]:
    """Read branch research-surface files that differ from champion.

    Returns a formatted string showing modified files, or None if no
    differences are found or the workspace is unavailable.
    """
    sections: List[str] = []
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
                sections.append(
                    f"### operators/{fname} (branch version)\n```python\n{branch_content}\n```"
                )

    for file_rel in _surface_file_targets(research_surfaces or []):
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
            sections.append(
                f"### {file_rel} (branch research-surface version)\n"
                f"```python\n{branch_content}\n```"
            )

    return "\n\n".join(sections) if sections else None

