"""CVRP state-bridge API contract checks."""

from __future__ import annotations

import ast

from scion.problems.cvrp.contract_checks.ast_discovery import (
    _assigned_name_targets,
)

_FORBIDDEN_SOLUTION_BRIDGE_METHODS = frozenset(
    {"from_routes", "from_public", "from_cvrp_solution", "to_public"}
)


def _state_model_bridge_api_error(
    *,
    file_rel: str,
    tree: ast.AST,
) -> str | None:
    defined = _forbidden_solution_bridge_definitions(file_rel, tree)
    called = _forbidden_solution_bridge_calls(tree)
    if not defined and not called:
        return None
    parts: list[str] = []
    if defined:
        parts.append(f"forbidden_definitions={defined}")
    if called:
        parts.append(f"forbidden_calls={called}")
    return (
        "solver_design patches must use the branch-owned CVRP state model "
        "instead of inventing _Solution bridge APIs. _Solution exposes copy(), "
        "rebuild_index(), remove_empty_routes(), is_feasible(), and "
        "routes_as_tuples(); it does not expose from_routes, from_public, "
        "from_cvrp_solution, or to_public. Existing construction.py helpers "
        "already return internal _Solution objects. If public route tuples "
        "must become internal state, import _Route and _Solution from .state "
        "and construct _Solution(instance, [_Route(instance, route) for route "
        "in routes]); return public output with "
        "context.make_solution(solution.routes_as_tuples()). " + "; ".join(parts)
    )


def _forbidden_solution_bridge_definitions(
    file_rel: str,
    tree: ast.AST,
) -> list[dict[str, object]]:
    if file_rel != "policies/baseline_modules/state.py":
        return []
    findings: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "_Solution":
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if item.name in _FORBIDDEN_SOLUTION_BRIDGE_METHODS:
                findings.append(
                    {"method": item.name, "line": int(getattr(item, "lineno", 0) or 0)}
                )
    return findings


def _forbidden_solution_bridge_calls(tree: ast.AST) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    imported_solution_aliases = _solution_import_aliases(tree)
    assigned_solution_names = _solution_assigned_names(tree, imported_solution_aliases)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr not in _FORBIDDEN_SOLUTION_BRIDGE_METHODS:
            continue
        receiver = func.value
        receiver_name = receiver.id if isinstance(receiver, ast.Name) else ""
        if func.attr.startswith("from_"):
            if receiver_name not in imported_solution_aliases:
                continue
        elif (
            func.attr != "to_public"
            and receiver_name
            and receiver_name not in assigned_solution_names
        ):
            continue
        findings.append(
            {
                "method": func.attr,
                "line": int(getattr(node, "lineno", 0) or 0),
                "receiver": receiver_name or type(receiver).__name__,
            }
        )
    return findings


def _solution_import_aliases(tree: ast.AST) -> set[str]:
    names = {"_Solution"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            if alias.name == "_Solution":
                names.add(alias.asname or alias.name)
    return names


def _solution_assigned_names(
    tree: ast.AST,
    solution_aliases: set[str],
) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        if not isinstance(value, ast.Call):
            continue
        if not (isinstance(value.func, ast.Name) and value.func.id in solution_aliases):
            continue
        for target in targets:
            names.update(_assigned_name_targets(target))
    return names
