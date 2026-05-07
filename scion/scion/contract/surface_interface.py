"""Shared AST-only validation for research-surface interfaces.

Candidate code is tainted LLM output. This module parses patch content with
``ast`` and never imports candidate modules.
"""
from __future__ import annotations

import ast
import time
from collections.abc import Mapping
from typing import Any

from scion.core.models import CheckResult, PatchProposal
from scion.core.operator_interface import parse_execute_signature
from scion.core.path_match import normalize_relative_glob_pattern, segment_glob_match
from scion.core.paths import normalize_relative_patch_path
from scion.problem.spec import SUPPORTED_RESEARCH_SURFACE_KINDS

_STATIC_UNKNOWN = object()


def check_surface_interface(
    patch: PatchProposal,
    *,
    problem_spec: Any | None = None,
    selected_surface: str | None = None,
    operator_execute_signature: str | None = None,
    check_name: str,
    severity: str = "light",
    detail_suffix: str = "",
) -> CheckResult:
    """Validate a patch against its declared research-surface interface.

    When ``problem_spec.research_surfaces`` is declared, an explicit
    ``selected_surface`` is authoritative: it must exist and the patch target
    must belong to that surface. Without an explicit selection, declared
    surfaces are resolved by patch target path. Specs without research surfaces
    use the legacy operator-class behavior.
    """
    t0 = time.monotonic_ns()
    if patch.action == "delete":
        return _cr(
            check_name,
            True,
            severity,
            _detail("delete action — no interface check", detail_suffix),
            t0,
        )

    try:
        file_rel = normalize_relative_patch_path(patch.file_path)
    except ValueError as exc:
        return _cr(check_name, False, severity, str(exc), t0)

    try:
        tree = ast.parse(patch.code_content)
    except SyntaxError:
        return _cr(
            check_name,
            False,
            severity,
            _detail("unparseable code", detail_suffix),
            t0,
        )

    surfaces = research_surfaces(problem_spec)
    surface = None
    if surfaces:
        surface, error = resolve_surface_for_interface(
            surfaces,
            file_rel=file_rel,
            selected_surface=selected_surface,
        )
        if error is not None:
            return _cr(check_name, False, severity, error, t0)

    kind_error = surface_kind_error(surface)
    if kind_error is not None:
        return _cr(check_name, False, severity, kind_error, t0)

    kind = str(_field(surface, "kind", "operator") or "operator")
    if kind == "policy":
        return _check_policy_interface(
            tree,
            surface,
            check_name=check_name,
            severity=severity,
            detail_suffix=detail_suffix,
            start_ns=t0,
        )
    if kind == "config":
        return _check_module_function_interface(
            tree,
            surface,
            check_name=check_name,
            severity=severity,
            detail_suffix=detail_suffix,
            start_ns=t0,
        )
    if surface is not None and kind not in ("", "operator"):
        return _check_module_function_interface(
            tree,
            surface,
            check_name=check_name,
            severity=severity,
            detail_suffix=detail_suffix,
            start_ns=t0,
        )

    expected = parse_execute_signature(operator_execute_signature)
    return _check_operator_interface(
        tree,
        surface,
        expected_args=expected.args,
        expected_detail=expected.expected_args_detail,
        check_name=check_name,
        severity=severity,
        detail_suffix=detail_suffix,
        start_ns=t0,
    )


def resolve_surface_for_interface(
    surfaces: list[Any],
    *,
    file_rel: str,
    selected_surface: str | None,
) -> tuple[Any | None, str | None]:
    """Resolve and validate the surface used by an interface check."""
    selected = (selected_surface or "").strip()
    if selected:
        surface = find_surface_by_name(surfaces, selected)
        if surface is None:
            return (
                None,
                f"selected research surface '{selected}' is not declared "
                "in problem_spec.research_surfaces",
            )
        if not target_matches_surface(file_rel, surface):
            return (
                None,
                f"patch file_path '{file_rel}' is not in target files "
                f"{surface_target_files(surface)} for selected research "
                f"surface '{selected}'",
            )
        return surface, None

    surface = find_surface_for_patch_path(surfaces, file_rel)
    if surface is not None:
        return surface, None
    return (
        None,
        f"patch file_path '{file_rel}' is not in any declared research "
        "surface target files",
    )


def research_surfaces(problem_spec: Any | None) -> list[Any]:
    return list(_field(problem_spec, "research_surfaces", []) or [])


def find_surface_by_name(surfaces: list[Any], name: str) -> Any | None:
    for surface in surfaces:
        if _field(surface, "name") == name:
            return surface
    return None


def find_surface_for_patch_path(surfaces: list[Any], file_rel: str) -> Any | None:
    for surface in surfaces:
        if target_matches_surface(file_rel, surface):
            return surface
    return None


def target_matches_surface(file_rel: str, surface: Any) -> bool:
    try:
        normalized = normalize_relative_patch_path(file_rel)
    except ValueError:
        return False
    return any(
        _matches_config_pattern(normalized, str(pattern).lstrip("/"))
        for pattern in surface_target_files(surface)
    )


def surface_target_files(surface: Any | None) -> list[str]:
    targets = _field(surface, "targets")
    if targets is not None:
        files = _field(targets, "files")
        if files is not None:
            return [str(path) for path in files]
    return [str(path) for path in (_field(surface, "target_files", []) or [])]


def surface_kind_error(surface: Any | None) -> str | None:
    if surface is None:
        return None
    kind = str(_field(surface, "kind", "") or "").strip()
    if kind in SUPPORTED_RESEARCH_SURFACE_KINDS:
        return None
    allowed = ", ".join(sorted(SUPPORTED_RESEARCH_SURFACE_KINDS))
    return (
        f"unsupported research surface kind '{kind}' for surface "
        f"'{_field(surface, 'name', '<unknown>')}', expected one of: {allowed}"
    )


def surface_required_functions(surface: Any | None) -> list[str]:
    interface = _field(surface, "interface")
    if interface is not None:
        required = _field(interface, "required_functions")
        if required is not None:
            return [str(name) for name in required]
    return [str(name) for name in (_field(surface, "required_functions", []) or [])]


def surface_function_signatures(surface: Any | None) -> dict[str, list[str]]:
    interface = _field(surface, "interface")
    signatures = _field(interface, "function_signatures") if interface is not None else None
    if not isinstance(signatures, Mapping):
        return {}
    normalized: dict[str, list[str]] = {}
    for raw_name, raw_args in signatures.items():
        name = str(raw_name).strip()
        if not name:
            continue
        if isinstance(raw_args, str):
            args = [arg.strip() for arg in raw_args.split(",") if arg.strip()]
        else:
            try:
                args = [str(arg).strip() for arg in raw_args if str(arg).strip()]
            except TypeError:
                args = []
        normalized[name] = args
    return normalized


def surface_return_values(surface: Any | None) -> dict[str, Any]:
    interface = _field(surface, "interface")
    values = _field(interface, "return_values") if interface is not None else None
    return dict(values) if isinstance(values, Mapping) else {}


def _check_operator_interface(
    tree: ast.AST,
    surface: Any | None,
    *,
    expected_args: tuple[str, ...],
    expected_detail: str,
    check_name: str,
    severity: str,
    detail_suffix: str,
    start_ns: int,
) -> CheckResult:
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if not classes:
        if surface is not None:
            return _cr(
                check_name,
                False,
                severity,
                _detail("operator surface file must define an operator class", detail_suffix),
                start_ns,
            )
        return _cr(
            check_name,
            True,
            severity,
            _detail("no class found — skipped", detail_suffix),
            start_ns,
        )

    for cls in classes:
        for node in ast.walk(cls):
            if isinstance(node, ast.FunctionDef) and node.name == "execute":
                args = [a.arg for a in node.args.args]
                if tuple(args) == expected_args:
                    return _cr(
                        check_name,
                        True,
                        severity,
                        _detail("execute signature ok", detail_suffix),
                        start_ns,
                    )
                return _cr(
                    check_name,
                    False,
                    severity,
                    _detail(
                        "execute signature wrong: "
                        f"{args}, expected {expected_detail}",
                        detail_suffix,
                    ),
                    start_ns,
                )

    return _cr(
        check_name,
        False,
        severity,
        _detail("class found but no execute method defined", detail_suffix),
        start_ns,
    )


def _check_policy_interface(
    tree: ast.AST,
    surface: Any,
    *,
    check_name: str,
    severity: str,
    detail_suffix: str,
    start_ns: int,
) -> CheckResult:
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if classes:
        return _cr(
            check_name,
            False,
            severity,
            _detail(
                f"policy surface must use module-level functions, found classes {classes}",
                detail_suffix,
            ),
            start_ns,
        )
    return _check_module_function_interface(
        tree,
        surface,
        check_name=check_name,
        severity=severity,
        detail_suffix=detail_suffix,
        start_ns=start_ns,
        success_prefix="policy interface ok",
        skipped_prefix="policy surface",
    )


def _check_module_function_interface(
    tree: ast.AST,
    surface: Any,
    *,
    check_name: str,
    severity: str,
    detail_suffix: str,
    start_ns: int,
    success_prefix: str = "surface interface ok",
    skipped_prefix: str | None = None,
) -> CheckResult:
    required = tuple(surface_required_functions(surface))
    declared_signatures = surface_function_signatures(surface)
    required_names = _dedupe_preserving_order(
        list(required) + list(declared_signatures)
    )
    kind = str(_field(surface, "kind", "surface") or "surface")
    if skipped_prefix is None:
        skipped_prefix = f"{kind} surface"
    if not required_names:
        return _cr(
            check_name,
            True,
            severity,
            _detail(
                f"{skipped_prefix} has no required functions declared — skipped",
                detail_suffix,
            ),
            start_ns,
        )

    functions = {
        node.name: node
        for node in getattr(tree, "body", [])
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = [name for name in required_names if name not in functions]
    if missing:
        return _cr(
            check_name,
            False,
            severity,
            _detail(f"missing required functions {missing}", detail_suffix),
            start_ns,
        )

    signature_error = _declared_signature_error(functions, declared_signatures)
    if signature_error is not None:
        return _cr(
            check_name,
            False,
            severity,
            _detail(signature_error, detail_suffix),
            start_ns,
        )

    return_error = _declared_return_value_error(functions, surface)
    if return_error is not None:
        return _cr(
            check_name,
            False,
            severity,
            _detail(return_error, detail_suffix),
            start_ns,
        )

    return_detail = _declared_return_value_detail(functions, surface)
    detail = success_prefix
    if return_detail:
        detail = f"{detail}; {return_detail}"
    return _cr(
        check_name,
        True,
        severity,
        _detail(detail, detail_suffix),
        start_ns,
    )


def _declared_signature_error(
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    declared_signatures: dict[str, list[str]],
) -> str | None:
    for name, expected_args in declared_signatures.items():
        node = functions.get(name)
        if node is None:
            continue
        actual_args = [
            arg.arg
            for arg in [*node.args.posonlyargs, *node.args.args]
        ]
        if actual_args[: len(expected_args)] != expected_args:
            return (
                f"function '{name}' positional parameters {actual_args} do "
                f"not match declared prefix {expected_args}"
            )
        required_count = len(actual_args) - len(node.args.defaults)
        if required_count > len(expected_args):
            extra = actual_args[len(expected_args) : required_count]
            return (
                f"function '{name}' declares extra required positional "
                f"parameters {extra}"
            )
    return None


def _declared_return_value_error(
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    surface: Any | None,
) -> str | None:
    for name, spec in surface_return_values(surface).items():
        node = functions.get(str(name))
        if node is None:
            continue
        for return_node in [
            item for item in ast.walk(node) if isinstance(item, ast.Return)
        ]:
            value = _static_literal_value(return_node.value)
            if value is _STATIC_UNKNOWN:
                if not bool(_field(spec, "allow_static_unknown", True)):
                    return (
                        f"function '{name}' return value is not statically "
                        "decidable"
                    )
                continue
            error = _return_value_contract_error(str(name), value, spec)
            if error is not None:
                return error
    return None


def _declared_return_value_detail(
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    surface: Any | None,
) -> str:
    warnings: list[str] = []
    for name, spec in surface_return_values(surface).items():
        node = functions.get(str(name))
        if node is None:
            continue
        has_unknown = any(
            _static_literal_value(return_node.value) is _STATIC_UNKNOWN
            for return_node in ast.walk(node)
            if isinstance(return_node, ast.Return)
        )
        if has_unknown and bool(_field(spec, "allow_static_unknown", True)):
            warnings.append(f"{name} has return paths not statically checked")
    if not warnings:
        return ""
    return "return-value warnings: " + "; ".join(warnings)


def _static_literal_value(node: ast.AST | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        pass
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        if node.id == "None":
            return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _static_literal_value(node.operand)
        if isinstance(operand, bool) or not isinstance(operand, (int, float)):
            return _STATIC_UNKNOWN
        return +operand if isinstance(node.op, ast.UAdd) else -operand
    return _STATIC_UNKNOWN


def _return_value_contract_error(name: str, value: Any, spec: Any) -> str | None:
    value_type = str(_field(spec, "value_type", "any") or "any")
    if not _return_value_type_matches(value, value_type):
        return (
            f"function '{name}' returns {type(value).__name__}, expected "
            f"{value_type}"
        )

    allowed_literals = list(_field(spec, "allowed_literals", []) or [])
    if allowed_literals:
        if isinstance(value, (list, tuple, set, frozenset)):
            bad = [item for item in value if item not in allowed_literals]
            if bad:
                return (
                    f"function '{name}' returns values outside declared "
                    f"allowed_literals: {bad}"
                )
        elif value not in allowed_literals:
            return (
                f"function '{name}' returns {value!r}, expected one of "
                f"{allowed_literals}"
            )

    numeric_range = _field(spec, "numeric_range")
    if numeric_range is not None and isinstance(value, (int, float)) and not isinstance(value, bool):
        lo, hi = float(numeric_range[0]), float(numeric_range[1])
        numeric = float(value)
        if numeric < lo or numeric > hi:
            return (
                f"function '{name}' returns {numeric!r} outside declared "
                f"range [{lo}, {hi}]"
            )

    if isinstance(value, dict):
        allowed_keys = [str(item) for item in (_field(spec, "allowed_keys", []) or [])]
        if allowed_keys:
            bad_keys = [key for key in value if str(key) not in allowed_keys]
            if bad_keys:
                return (
                    f"function '{name}' returns keys outside declared "
                    f"allowed_keys: {bad_keys}"
                )
        required_keys = [
            str(item) for item in (_field(spec, "required_keys", []) or [])
        ]
        if required_keys:
            present = {str(key) for key in value}
            missing = [key for key in required_keys if key not in present]
            if missing:
                return f"function '{name}' is missing declared required keys: {missing}"
        value_range = _field(spec, "value_numeric_range")
        if value_range is not None:
            lo, hi = float(value_range[0]), float(value_range[1])
            for key, item in value.items():
                if isinstance(item, bool) or not isinstance(item, (int, float)):
                    return (
                        f"function '{name}' returns non-numeric value for key "
                        f"{key!r}: {item!r}"
                    )
                numeric = float(item)
                if numeric < lo or numeric > hi:
                    return (
                        f"function '{name}' returns value {numeric!r} for key "
                        f"{key!r} outside declared range [{lo}, {hi}]"
                    )
    return None


def _return_value_type_matches(value: Any, value_type: str) -> bool:
    if value_type == "any":
        return True
    if value_type == "str":
        return isinstance(value, str)
    if value_type == "bool":
        return isinstance(value, bool)
    if value_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type == "sequence":
        return isinstance(value, (list, tuple, set, frozenset)) and not isinstance(value, str)
    if value_type == "mapping":
        return isinstance(value, dict)
    return True


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            deduped.append(text)
    return deduped


def _matches_config_pattern(file_rel: str, pattern: str) -> bool:
    try:
        normalized_pattern = normalize_relative_glob_pattern(pattern)
    except ValueError:
        return False
    return segment_glob_match(file_rel, normalized_pattern)


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _detail(detail: str, suffix: str) -> str:
    if suffix and not detail.endswith(suffix):
        return f"{detail}{suffix}"
    return detail


def _cr(
    name: str,
    passed: bool,
    severity: str,
    detail: str,
    start_ns: int,
) -> CheckResult:
    elapsed_ms = int((time.monotonic_ns() - start_ns) / 1_000_000)
    return CheckResult(
        name=name,
        passed=passed,
        severity=severity,  # type: ignore[arg-type]
        detail=detail,
        elapsed_ms=elapsed_ms,
    )
