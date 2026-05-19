"""Static solver-design preview checks for CVRP adapter previews."""
from __future__ import annotations

import ast
from typing import Any

from scion.core.models import patch_file_changes
from scion.problems.cvrp.preview.paths import (
    _is_baseline_algorithm_path,
    _is_solver_design_module_path,
)

def _preview_baseline_algorithm_boundary(
    code: str,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    baseline_calls = _context_baseline_call_count(code)
    passed = baseline_calls == 0
    detail = (
        "preferred solver_design target does not call context.baseline"
        if passed
        else (
            "policies/baseline_algorithm.py is the Scion-controlled algorithm "
            "body and must not call context.baseline; modify the editable "
            "construction/search/destroy-repair/VNS logic directly"
        )
    )
    checks.append(
        {
            "name": "baseline_algorithm_no_context_baseline",
            "passed": passed,
            "detail": detail,
        }
    )
    if not passed:
        issues.append(detail)

    mixed = _remaining_time_ms_mixed_comparisons(code)
    time_units_passed = not mixed
    time_units_detail = (
        "remaining_time unit usage is consistent"
        if time_units_passed
        else (
            "context.remaining_time() returns seconds; use "
            "context.remaining_time_ms() when comparing to millisecond-derived "
            f"variables: {mixed[:5]}"
        )
    )
    checks.append(
        {
            "name": "baseline_algorithm_remaining_time_units",
            "passed": time_units_passed,
            "detail": time_units_detail,
        }
    )
    if not time_units_passed:
        issues.append(time_units_detail)

def _preview_solver_design_patch_api_boundary(
    patch: Any,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    for change in patch_file_changes(patch):
        path = str(getattr(change, "file_path", "") or "")
        normalized = path.replace("\\", "/").lstrip("/")
        if not (
            _is_baseline_algorithm_path(normalized)
            or _is_solver_design_module_path(normalized)
        ):
            continue
        code = str(getattr(change, "code_content", "") or "")
        if _is_baseline_algorithm_path(normalized):
            _preview_baseline_algorithm_scheduler_api(
                normalized,
                code,
                issues,
                checks,
            )
        _preview_solver_design_context_api(normalized, code, issues, checks)

def _preview_baseline_algorithm_scheduler_api(
    path: str,
    code: str,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    bad_names = _baseline_algorithm_scheduler_entrypoint_imports(code)
    passed = not bad_names
    detail = (
        "baseline_algorithm uses the stable scheduler class entrypoint"
        if passed
        else (
            f"{path} must keep scheduler integration through "
            "`_ALNSVNSSolver(...).solve(instance, rng)`; do not import "
            f"scheduler entrypoint names {bad_names}"
        )
    )
    checks.append(
        {
            "name": "baseline_algorithm_scheduler_entrypoint_api",
            "passed": passed,
            "detail": detail,
        }
    )
    if not passed:
        issues.append(detail)

def _baseline_algorithm_scheduler_entrypoint_imports(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = str(node.module or "")
        if not module.endswith("baseline_modules.scheduler"):
            continue
        for alias in node.names:
            name = str(alias.name or "")
            if name in {"solve", "run", "main", "_run", "_run_scheduler"}:
                bad.append(name)
    return sorted(set(bad))

def _preview_solver_design_context_api(
    path: str,
    code: str,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    bad_lines = _context_nearest_neighbor_argument_calls(code)
    passed = not bad_lines
    detail = (
        "solver_design context.nearest_neighbor() calls use the no-argument API"
        if passed
        else (
            f"{path} calls context.nearest_neighbor with arguments at lines "
            f"{bad_lines}; the API takes no arguments and returns CvrpSolution"
        )
    )
    checks.append(
        {
            "name": "solver_design_context_nearest_neighbor_no_args",
            "passed": passed,
            "detail": detail,
        }
    )
    if not passed:
        issues.append(detail)

def _context_nearest_neighbor_argument_calls(code: str) -> list[int]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "nearest_neighbor"
            and isinstance(func.value, ast.Name)
            and func.value.id == "context"
        ):
            continue
        if node.args or node.keywords:
            lines.append(int(getattr(node, "lineno", 0) or 0))
    return lines

def _context_baseline_call_count(code: str) -> int:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "baseline"
            and isinstance(func.value, ast.Name)
            and func.value.id == "context"
        ):
            count += 1
    return count

def _remaining_time_ms_mixed_comparisons(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    assignments: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                assignments[target.id] = node.value

    ms_names = {name for name in assignments if name.endswith("_ms")}
    changed = True
    while changed:
        changed = False
        for name, expr in assignments.items():
            if name in ms_names:
                continue
            if _expr_is_millisecond_derived(expr, ms_names):
                ms_names.add(name)
                changed = True

    mixed: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        parts = [node.left, *node.comparators]
        for left, right in zip(parts, parts[1:]):
            if _is_context_remaining_time_call(left) and _expr_references_ms_name(
                right, ms_names
            ):
                mixed.append(_format_compare_issue(right, ms_names))
            elif _is_context_remaining_time_call(right) and _expr_references_ms_name(
                left, ms_names
            ):
                mixed.append(_format_compare_issue(left, ms_names))
    return mixed

def _expr_is_millisecond_derived(expr: ast.AST, ms_names: set[str]) -> bool:
    if _expr_references_ms_name(expr, ms_names):
        return True
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Mult):
        return _is_1000_literal(expr.left) or _is_1000_literal(expr.right)
    return False

def _expr_references_ms_name(expr: ast.AST, ms_names: set[str]) -> bool:
    return any(
        isinstance(node, ast.Name) and node.id in ms_names
        for node in ast.walk(expr)
    )

def _is_1000_literal(expr: ast.AST) -> bool:
    return (
        isinstance(expr, ast.Constant)
        and isinstance(expr.value, (int, float))
        and expr.value == 1000
    )

def _is_context_remaining_time_call(expr: ast.AST) -> bool:
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Attribute)
        and expr.func.attr == "remaining_time"
        and isinstance(expr.func.value, ast.Name)
        and expr.func.value.id == "context"
    )

def _format_compare_issue(expr: ast.AST, ms_names: set[str]) -> str:
    names = sorted(
        {
            node.id
            for node in ast.walk(expr)
            if isinstance(node, ast.Name) and node.id in ms_names
        }
    )
    return ", ".join(names) if names else "millisecond expression"
