"""C9e solver-design integration check.

This module keeps solver-design call-graph reasoning out of the ContractGate
orchestrator. The check remains static and conservative: new module-level helper
functions must be reachable from a module entrypoint or from the runtime solver
class's ``solve`` call chain inside the same candidate patch. Solver modules may
also pass functions as first-class operators, for example from
``_default_vns_operators()`` into ``_vns(...)``; those name references count as
reachability edges even when the helper is not called at definition time.
"""
from __future__ import annotations

import ast
import difflib
from collections.abc import Callable
from dataclasses import dataclass

from scion.core.models import PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path


@dataclass(frozen=True)
class SolverDesignIntegrationResult:
    passed: bool
    detail: str


def check_solver_design_integration(
    patch: PatchProposal,
    *,
    selected_surface: str | None,
    selected_surface_is_solver_design: Callable[[str | None, PatchProposal], bool],
    is_solver_design_patch_path: Callable[[str], bool],
    champion_file_content: Callable[[str], str | None],
) -> SolverDesignIntegrationResult:
    if not selected_surface_is_solver_design(selected_surface, patch):
        return SolverDesignIntegrationResult(True, "not a solver_design patch")

    new_functions: set[str] = set()
    new_functions_by_file: dict[str, set[str]] = {}
    call_graph: dict[str, set[str]] = {}
    root_calls: set[str] = set()
    changed_paths: list[str] = []
    changed_files = 0
    primary_path = _primary_patch_path(patch)

    for change in patch_file_changes(patch):
        if change.action == "delete":
            continue
        try:
            file_rel = normalize_relative_patch_path(change.file_path)
        except ValueError as exc:
            return SolverDesignIntegrationResult(False, str(exc))
        if not is_solver_design_patch_path(file_rel):
            continue
        changed_files += 1
        changed_paths.append(file_rel)
        champion_code = champion_file_content(file_rel)
        wiring_error = _additional_wiring_edit_error(
            file_rel=file_rel,
            primary_path=primary_path,
            champion_code=champion_code,
            candidate_code=change.code_content,
        )
        if wiring_error is not None:
            return SolverDesignIntegrationResult(False, wiring_error)
        try:
            tree = ast.parse(change.code_content)
        except SyntaxError:
            return SolverDesignIntegrationResult(False, "unparseable code")

        current_defs = _module_level_function_defs(tree)
        champion_defs = _module_level_function_defs_from_source(champion_code)
        local_new = current_defs - champion_defs
        current_methods = _class_method_defs(tree)
        champion_methods = _class_method_defs_from_source(champion_code)
        local_new_methods = _new_class_method_names(current_methods, champion_methods)
        if local_new:
            new_functions.update(local_new)
            new_functions_by_file[file_rel] = set(local_new)
        if local_new_methods:
            new_functions.update(local_new_methods)
            new_functions_by_file.setdefault(file_rel, set()).update(local_new_methods)
        local_existing = current_defs - local_new

        module_calls, function_calls, class_method_calls = _module_call_references(tree)
        root_calls.update(module_calls)
        if file_rel in {
            "policies/baseline_algorithm.py",
            "policies/solver_algorithm.py",
        } and "solve" in current_defs:
            root_calls.add("solve")
        for root in local_existing:
            root_calls.update(function_calls.get(root, set()))
        class_roots = _solver_design_runtime_class_roots(
            tree,
            champion_classes=_module_level_class_defs_from_source(champion_code),
        )
        for class_name in class_roots:
            root_calls.update(
                _reachable_class_method_calls(
                    class_method_calls.get(class_name, {}),
                    root_method="solve",
                )
            )
            root_calls.add("solve")
        for name, calls in function_calls.items():
            call_graph.setdefault(name, set()).update(calls)
        for method_calls in class_method_calls.values():
            for name, calls in method_calls.items():
                call_graph.setdefault(name, set()).update(calls)

    if changed_files == 0 or not new_functions:
        return SolverDesignIntegrationResult(True, "no new solver_design helper functions")

    reachable = set(root_calls)
    queue = list(root_calls)
    seen = set(queue)
    while queue:
        name = queue.pop()
        for called in call_graph.get(name, set()):
            if called in reachable:
                continue
            reachable.add(called)
            if called not in seen:
                seen.add(called)
                queue.append(called)

    inert = sorted(new_functions - reachable)
    if inert:
        inert_by_file = {
            path: sorted(names & set(inert))
            for path, names in sorted(new_functions_by_file.items())
            if names & set(inert)
        }
        guidance = (
            "Solver-design helper functions must be reachable from an existing "
            "module function, baseline_algorithm.py::solve, solver_algorithm.py::solve, "
            "or the runtime solver class _ALNSVNSSolver.solve call chain. If a helper "
            "is added in a helper-only module such as local_search.py, include the "
            "scheduler.py or baseline_algorithm.py import/call-site edit in "
            "additional_changes. Do not add a legacy top-level run(...) entrypoint "
            "unless the current target already uses that entrypoint."
        )
        return SolverDesignIntegrationResult(
            False,
            "new solver_design helper functions are not integrated. "
            f"inert_helpers={inert}; changed_files={changed_paths}; "
            f"recognized_roots={sorted(root_calls)}; inert_helpers_by_file={inert_by_file}. "
            + guidance,
        )
    return SolverDesignIntegrationResult(
        True,
        "new solver_design helper functions are integrated",
    )


def _primary_patch_path(patch: PatchProposal) -> str:
    for change in patch_file_changes(patch):
        try:
            return normalize_relative_patch_path(change.file_path)
        except ValueError:
            return str(change.file_path or "")
    return ""


def _additional_wiring_edit_error(
    *,
    file_rel: str,
    primary_path: str,
    champion_code: str | None,
    candidate_code: str,
) -> str | None:
    if file_rel == primary_path:
        return None
    if file_rel not in {
        "policies/baseline_algorithm.py",
        "policies/baseline_modules/scheduler.py",
    }:
        return None
    if not champion_code:
        return None
    changed_lines = _changed_line_count(champion_code, candidate_code)
    max_changed = (
        30
        if file_rel == "policies/baseline_algorithm.py"
        else 80
    )
    if changed_lines <= max_changed:
        return None
    return (
        "solver_design integration edits to scheduler/entrypoint must stay "
        "bounded when they are not the approved primary target. "
        f"primary_target={primary_path}; integration_file={file_rel}; "
        f"changed_lines={changed_lines}; max_wiring_changed_lines={max_changed}. "
        "Put the mechanism in the approved construction/destroy-repair/local-search/"
        "acceptance module and keep scheduler or baseline_algorithm edits as small "
        "wiring changes. Make scheduler.py or baseline_algorithm.py the primary "
        "target for a broad orchestration rewrite."
    )


def _changed_line_count(before: str, after: str) -> int:
    diff = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        lineterm="",
    )
    count = 0
    for line in diff:
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith(("+", "-")):
            count += 1
    return count


def _module_level_function_defs(tree: ast.AST) -> set[str]:
    if not isinstance(tree, ast.Module):
        return set()
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _module_level_function_defs_from_source(code: str | None) -> set[str]:
    if not code:
        return set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    return _module_level_function_defs(tree)


def _module_level_class_defs(tree: ast.AST) -> set[str]:
    if not isinstance(tree, ast.Module):
        return set()
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef)}


def _module_level_class_defs_from_source(code: str | None) -> set[str]:
    if not code:
        return set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    return _module_level_class_defs(tree)


def _class_method_defs(tree: ast.AST) -> dict[str, set[str]]:
    if not isinstance(tree, ast.Module):
        return {}
    result: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        result[node.name] = {
            item.name
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
    return result


def _class_method_defs_from_source(code: str | None) -> dict[str, set[str]]:
    if not code:
        return {}
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {}
    return _class_method_defs(tree)


def _new_class_method_names(
    current: dict[str, set[str]],
    champion: dict[str, set[str]],
) -> set[str]:
    new: set[str] = set()
    for class_name, methods in current.items():
        inherited = champion.get(class_name, set())
        for method_name in methods - inherited:
            if method_name == "solve":
                continue
            if method_name.startswith("__") and method_name.endswith("__"):
                continue
            new.add(method_name)
    return new


def _module_call_references(
    tree: ast.AST,
) -> tuple[set[str], dict[str, set[str]], dict[str, dict[str, set[str]]]]:
    if not isinstance(tree, ast.Module):
        return set(), {}, {}

    module_calls: set[str] = set()
    function_calls: dict[str, set[str]] = {}
    class_method_calls: dict[str, dict[str, set[str]]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_calls[node.name] = _call_reference_names(node)
        elif isinstance(node, ast.ClassDef):
            method_calls: dict[str, set[str]] = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_calls[item.name] = _call_reference_names(item)
            class_method_calls[node.name] = method_calls
        else:
            module_calls.update(_call_reference_names(node))
    return module_calls, function_calls, class_method_calls


def _solver_design_runtime_class_roots(
    tree: ast.AST,
    *,
    champion_classes: set[str],
) -> set[str]:
    if not isinstance(tree, ast.Module):
        return set()

    current_classes = _module_level_class_defs(tree)
    roots = current_classes & champion_classes
    if "_ALNSVNSSolver" in current_classes:
        roots.add("_ALNSVNSSolver")

    runtime_alias_targets = champion_classes | {"_ALNSVNSSolver"}
    for node in tree.body:
        value = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if not isinstance(value, ast.Name) or value.id not in current_classes:
            continue
        if any(
            isinstance(target, ast.Name) and target.id in runtime_alias_targets
            for target in targets
        ):
            roots.add(value.id)
    return roots


def _reachable_class_method_calls(
    method_calls: dict[str, set[str]],
    *,
    root_method: str,
) -> set[str]:
    if root_method not in method_calls:
        return set()

    calls: set[str] = set()
    seen_methods = {root_method}
    queue = [root_method]
    while queue:
        method_name = queue.pop()
        local_calls = method_calls.get(method_name, set())
        calls.update(local_calls)
        for called in local_calls:
            if called in method_calls and called not in seen_methods:
                seen_methods.add(called)
                queue.append(called)
    return calls


def _call_reference_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            names.add(child.id)
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names
