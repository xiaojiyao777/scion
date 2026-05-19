"""Same-patch import/export validation for CVRP solver-design changes."""

from __future__ import annotations

import ast
from collections.abc import Callable

from scion.problems.cvrp.contract_checks.ast_discovery import (
    _assigned_name_targets,
)


def _solver_design_import_export_error(
    candidate_sources: dict[str, str],
    *,
    champion_file_content: Callable[[str], str | None],
    primary_path: str,
) -> str | None:
    if not candidate_sources:
        return None
    exports_cache: dict[str, set[str] | None] = {}
    missing: list[dict[str, object]] = []
    for file_rel, source in sorted(candidate_sources.items()):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            target_rel = _solver_design_import_target(file_rel, node)
            if target_rel is None:
                continue
            aliases = [
                str(alias.name or "")
                for alias in node.names
                if str(alias.name or "") and str(alias.name or "") != "*"
            ]
            if not aliases:
                continue
            exports = exports_cache.get(target_rel)
            if target_rel not in exports_cache:
                target_source = candidate_sources.get(target_rel)
                if target_source is None:
                    target_source = champion_file_content(target_rel)
                exports = _module_exported_names_from_source(target_source)
                exports_cache[target_rel] = exports
            if exports is None:
                continue
            missing_names = sorted(name for name in aliases if name not in exports)
            if missing_names:
                missing.append(
                    {
                        "file": file_rel,
                        "line": getattr(node, "lineno", None),
                        "module": target_rel,
                        "missing": missing_names,
                        "available_exports": sorted(exports)[:80],
                    }
                )
    if not missing:
        return None
    return (
        "solver_design module imports must resolve against the candidate "
        "workspace after applying all additional_changes. "
        f"primary_target={primary_path}; missing_import_symbols={missing}. "
        "Use only names listed in available_exports, or define the exact "
        "symbol in the imported module in the same patch. If scheduler.py is "
        "only wiring a non-scheduler primary target, keep scheduler imports "
        "minimal and do not introduce unrelated construction/local_search "
        "imports. If a module-level integration edit "
        "imports a sibling helper, define that exact symbol in the changed "
        "module or keep the existing champion import name; do not invent "
        "scheduler/construction/local_search helper names."
    )


def _solver_design_import_target(
    file_rel: str,
    node: ast.ImportFrom,
) -> str | None:
    module = str(node.module or "").strip(".")
    if node.level > 0:
        if not module:
            return None
        package_parts = file_rel.removesuffix(".py").split("/")[:-1]
        if node.level > 1:
            package_parts = package_parts[: -(node.level - 1)]
        if module:
            package_parts.extend(part for part in module.split(".") if part)
        if not package_parts:
            return None
        if package_parts[-1] == "__init__":
            return None
        return "/".join(package_parts) + ".py"

    if module.startswith("policies.baseline_modules."):
        suffix = module.removeprefix("policies.baseline_modules.")
        return "policies/baseline_modules/" + suffix.replace(".", "/") + ".py"
    if module == "policies.baseline_modules":
        return "policies/baseline_modules/__init__.py"
    if module.startswith("baseline_modules."):
        suffix = module.removeprefix("baseline_modules.")
        return "policies/baseline_modules/" + suffix.replace(".", "/") + ".py"
    if module in {"policies.baseline_algorithm", "policies.solver_algorithm"}:
        return module.replace(".", "/") + ".py"
    return None


def _module_exported_names_from_source(code: str | None) -> set[str] | None:
    if code is None:
        return None
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    names: set[str] = set()
    if not isinstance(tree, ast.Module):
        return names
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            else:
                targets = [node.target]
            for target in targets:
                names.update(_assigned_name_targets(target))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name.rsplit(".", 1)[-1]
                if local:
                    names.add(local)
    return names
