"""Static instance-identity leakage checks."""
from __future__ import annotations

import ast
import time
from collections import Counter
from collections.abc import Callable
from typing import Any

from scion.contract.checks.security import (
    collect_import_name_aliases,
    is_string_literal_node,
)
from scion.contract.result_payload import check_result
from scion.contract.surface_access import SurfaceAccess
from scion.core.models import CheckResult, PatchProposal
from scion.core.paths import normalize_relative_patch_path


def check_surface_instance_identity(
    patch: PatchProposal,
    *,
    selected_surface: str | None,
    surface_access: SurfaceAccess,
    surface_disallows_instance_name: Callable[[Any | None], bool],
    champion_file_content: Callable[[str], str | None],
) -> CheckResult:
    t0 = time.monotonic_ns()
    if patch.action == "delete":
        return check_result(
            "C9d_surface_instance_identity",
            True,
            "heavy",
            "delete action — no instance identity check",
            t0,
        )

    try:
        file_rel = normalize_relative_patch_path(patch.file_path)
    except ValueError as exc:
        return check_result(
            "C9d_surface_instance_identity",
            False,
            "heavy",
            str(exc),
            t0,
        )

    surface, surface_error = surface_access.surface_for_patch_selection(
        file_rel,
        selected_surface=selected_surface,
    )
    if surface_error is not None:
        return check_result(
            "C9d_surface_instance_identity",
            False,
            "heavy",
            surface_error,
            t0,
        )
    if not surface_disallows_instance_name(surface):
        return check_result(
            "C9d_surface_instance_identity",
            True,
            "heavy",
            "surface does not restrict instance.name",
            t0,
        )

    try:
        tree = ast.parse(patch.code_content)
    except SyntaxError:
        return check_result(
            "C9d_surface_instance_identity",
            False,
            "heavy",
            "unparseable code",
            t0,
        )

    violations = _instance_identity_violations(patch.code_content, tree)
    violations = _subtract_inherited_identity_violations(
        violations,
        champion_file_content(file_rel),
    )

    if not violations:
        return check_result(
            "C9d_surface_instance_identity",
            True,
            "heavy",
            "no instance identity access",
            t0,
        )
    surface_name = getattr(surface, "name", "<unknown>")
    return check_result(
        "C9d_surface_instance_identity",
        False,
        "heavy",
        f"case-specific instance identity access is forbidden for research "
        f"surface '{surface_name}': {violations}",
        t0,
    )


def _instance_identity_violations(code: str, tree: ast.AST) -> list[str]:
    parent: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node

    module_aliases, imported_call_aliases = collect_import_name_aliases(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        label: str | None = None
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "name"
            and isinstance(node.value, ast.Name)
            and node.value.id == "instance"
        ):
            label = "instance.name"
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == "__dict__"
            and isinstance(node.value, ast.Name)
            and node.value.id == "instance"
        ):
            label = "instance.__dict__"
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"getattr", "hasattr"}
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "instance"
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "name"
        ):
            label = f"{node.func.id}(instance, 'name')"
        elif isinstance(node, ast.Call):
            label = _instance_identity_call_label(
                node,
                module_aliases=module_aliases,
                imported_call_aliases=imported_call_aliases,
            )
        if label is None:
            continue
        statement = _enclosing_statement_source(code, node, parent)
        violations.append(statement or label)
    return violations


def _instance_identity_call_label(
    node: ast.Call,
    *,
    module_aliases: dict[str, str],
    imported_call_aliases: dict[str, tuple[str, str]],
) -> str | None:
    if not node.args or not _is_instance_name(node.args[0]):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        if func.id in {"repr", "str", "vars"}:
            return f"{func.id}(instance)"
        if func.id == "getattr" and len(node.args) >= 2:
            if is_string_literal_node(node.args[1]):
                if node.args[1].value == "name":
                    return "getattr(instance, 'name')"
                return None
            return "getattr(instance, <computed>)"
        dataclass_alias = imported_call_aliases.get(func.id)
        if dataclass_alias in {
            ("dataclasses", "asdict"),
            ("dataclasses", "astuple"),
            ("dataclasses", "fields"),
            ("dataclasses", "is_dataclass"),
        }:
            return f"dataclasses.{dataclass_alias[1]}(instance)"
    elif isinstance(func, ast.Attribute):
        module_name = (
            module_aliases.get(func.value.id, func.value.id)
            if isinstance(func.value, ast.Name)
            else ""
        )
        if module_name == "dataclasses" and func.attr in {
            "asdict",
            "astuple",
            "fields",
            "is_dataclass",
        }:
            return f"dataclasses.{func.attr}(instance)"
    return None


def _is_instance_name(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "instance"


def _subtract_inherited_identity_violations(
    violations: list[str],
    champion_code: str | None,
) -> list[str]:
    if not violations or not champion_code:
        return violations
    try:
        champion_tree = ast.parse(champion_code)
    except SyntaxError:
        return violations
    inherited = Counter(_instance_identity_violations(champion_code, champion_tree))
    remaining: list[str] = []
    for violation in violations:
        if inherited.get(violation, 0) > 0:
            inherited[violation] -= 1
            continue
        remaining.append(violation)
    return remaining


def _enclosing_statement_source(
    code: str,
    node: ast.AST,
    parent: dict[ast.AST, ast.AST],
) -> str | None:
    current: ast.AST | None = node
    while current is not None and not isinstance(current, ast.stmt):
        current = parent.get(current)
    if current is None:
        return None
    source = ast.get_source_segment(code, current)
    if not source:
        return None
    return " ".join(source.strip().split())
