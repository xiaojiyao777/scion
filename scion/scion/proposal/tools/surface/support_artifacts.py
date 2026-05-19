"""Solver-design support artifact readers for surface tools."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from scion.core.path_match import normalize_relative_glob_pattern
from scion.proposal.tools.surface.constants import _COMPACT_SURFACE_CODE_CHARS
from scion.proposal.tools.surface.readers import _read_code_file_from_root
from scion.proposal.tools.utils import _limit_text, _normalize_rel_path


def _read_solver_design_support_artifacts(
    source_root: str | Path,
    target_files: list[str],
    *,
    primary_target: str,
    detail: str,
    primary_code_char_limit: int,
    source_kind: str,
) -> list[dict[str, Any]]:
    root = Path(source_root).expanduser().resolve()
    primary = _normalize_rel_path(primary_target) or ""
    per_file_limit = min(primary_code_char_limit, _COMPACT_SURFACE_CODE_CHARS)
    total_limit = 11000 if detail == "full" else 9000
    artifacts: list[dict[str, Any]] = []
    remaining = total_limit
    for rel, path in _solver_design_support_candidate_paths(
        root,
        target_files,
        primary=primary,
    ):
        if len(artifacts) >= 12 or remaining <= 0:
            return artifacts
        read_limit = max(0, min(per_file_limit, remaining))
        artifact = _read_code_file_from_root(
            root,
            rel,
            max_chars=read_limit,
            source_kind=source_kind,
        )
        api_summary = _python_api_summary_for_file(path)
        if api_summary:
            artifact["python_api_summary"] = api_summary
        artifacts.append(artifact)
        if artifact.get("readable"):
            remaining -= len(str(artifact.get("content_preview", "")))
            remaining -= len(str(artifact.get("python_api_summary", "")))
    return artifacts


def _solver_design_support_candidate_paths(
    root: Path,
    target_files: list[str],
    *,
    primary: str,
) -> list[tuple[str, Path]]:
    declared: dict[str, tuple[int, Path]] = {}
    for pattern_index, raw_pattern in enumerate(target_files):
        try:
            pattern = normalize_relative_glob_pattern(raw_pattern)
        except ValueError:
            continue
        if not any(ch in pattern for ch in "*?["):
            candidates = [root / pattern]
        else:
            candidates = sorted(root.glob(pattern))
        for path in candidates:
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if rel == primary or rel.endswith("/__init__.py"):
                continue
            if not rel.endswith(".py"):
                continue
            declared.setdefault(rel, (pattern_index, path))

    return sorted(
        ((rel, path) for rel, (_pattern_index, path) in declared.items()),
        key=lambda item: (
            declared[item[0]][0],
            item[0],
        ),
    )


def _python_api_summary_for_file(path: Path, *, max_chars: int = 1800) -> str:
    if path.suffix != ".py":
        return ""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return ""
    lines: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [
                _python_function_signature(child)
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if methods:
                lines.append(f"class {node.name}: " + "; ".join(methods[:14]))
            else:
                lines.append(f"class {node.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.append("def " + _python_function_signature(node))
        if len(lines) >= 28:
            break
    if not lines:
        return ""
    return _limit_text("\n".join(lines), max_chars)


def _python_function_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
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

__all__ = [
    "_read_solver_design_support_artifacts",
    "_solver_design_support_candidate_paths",
    "_python_api_summary_for_file",
    "_python_function_signature",
]
