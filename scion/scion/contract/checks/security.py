"""Static import and sensitive-API checks for ContractGate."""
from __future__ import annotations

import ast
import time
from collections.abc import Callable

from scion.config.problem import ProblemSpec
from scion.contract.patch_graph import PatchSetGraph
from scion.contract.result_payload import check_result
from scion.core.models import CheckResult, PatchProposal
from scion.core.paths import normalize_relative_patch_path

_SENSITIVE_APIS = frozenset({"subprocess", "socket", "eval", "exec"})
_SENSITIVE_OS_ATTRS = frozenset({"system", "popen", "execve", "execvp", "execv"})
_SENSITIVE_OS_ENV_CALLS = frozenset({"getenv", "putenv", "unsetenv"})
_REFLECTIVE_PRIMITIVES = frozenset(
    {"getattr", "setattr", "delattr", "globals", "locals", "vars"}
)
_DANGEROUS_FILE_READ_ATTRS = frozenset(
    {"open", "read_text", "read_bytes", "readlink", "iterdir", "glob", "rglob"}
)


def check_import_whitelist(
    patch: PatchProposal,
    *,
    problem_spec: ProblemSpec,
    patch_graph: PatchSetGraph | None = None,
    is_editable_solver_file: Callable[[str], bool] | None = None,
) -> CheckResult:
    t0 = time.monotonic_ns()
    if patch.action == "delete":
        return check_result(
            "C8_import_whitelist",
            True,
            "heavy",
            "delete action — no import check",
            t0,
        )

    whitelist = set(problem_spec.search_space.import_whitelist)

    try:
        tree = ast.parse(patch.code_content)
    except SyntaxError:
        return check_result(
            "C8_import_whitelist",
            False,
            "heavy",
            "unparseable code",
            t0,
        )

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if not _in_whitelist(top, whitelist):
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if (
                patch_graph is not None
                and is_editable_solver_file is not None
                and patch_graph.allows_same_patch_relative_import(
                    importer_path=patch.file_path,
                    node=node,
                    is_editable_solver_file=is_editable_solver_file,
                )
            ):
                continue
            if node.module:
                top = node.module.split(".")[0]
                if not _in_whitelist(top, whitelist):
                    violations.append(node.module)
            elif node.level > 0:
                for alias in node.names:
                    name = str(alias.name or "")
                    if name and name != "*" and not _in_whitelist(name, whitelist):
                        violations.append(name)

    passed = len(violations) == 0
    detail = "imports ok" if passed else f"non-whitelisted imports: {violations}"
    return check_result("C8_import_whitelist", passed, "heavy", detail, t0)


def check_sensitive_api(patch: PatchProposal) -> CheckResult:
    t0 = time.monotonic_ns()
    if patch.action == "delete":
        return check_result(
            "C9_sensitive_api",
            True,
            "heavy",
            "delete action — no API check",
            t0,
        )

    try:
        tree = ast.parse(patch.code_content)
    except SyntaxError:
        return check_result(
            "C9_sensitive_api",
            False,
            "heavy",
            "unparseable code",
            t0,
        )

    module_aliases, imported_call_aliases = collect_import_name_aliases(tree)
    sensitive_call_aliases, dynamic_module_aliases = _collect_sensitive_aliases(
        tree,
        module_aliases=module_aliases,
        imported_call_aliases=imported_call_aliases,
    )
    violations: list[str] = []
    violations.extend(
        _context_baseline_call_violations_in_baseline_algorithm(
            patch.file_path,
            tree,
        )
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and _is_os_environ_attr(
            node,
            module_aliases,
        ):
            violations.append("os.environ")
            continue

        if not isinstance(node, ast.Call):
            continue

        violations.extend(
            _sensitive_call_violations(
                node,
                module_aliases=module_aliases,
                imported_call_aliases=imported_call_aliases,
                sensitive_call_aliases=sensitive_call_aliases,
                dynamic_module_aliases=dynamic_module_aliases,
            )
        )

    passed = len(violations) == 0
    detail = "no sensitive APIs" if passed else f"sensitive APIs detected: {violations}"
    return check_result("C9_sensitive_api", passed, "heavy", detail, t0)


def collect_import_name_aliases(
    tree: ast.AST,
) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    module_aliases: dict[str, str] = {}
    imported_call_aliases: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                module_aliases[local] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = str(node.module or "")
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                imported_call_aliases[local] = (module, alias.name)
    return module_aliases, imported_call_aliases


def is_string_literal_node(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _in_whitelist(module_top: str, whitelist: set) -> bool:
    return module_top in whitelist


def _collect_sensitive_aliases(
    tree: ast.AST,
    *,
    module_aliases: dict[str, str],
    imported_call_aliases: dict[str, tuple[str, str]],
) -> tuple[dict[str, str], set[str]]:
    sensitive_call_aliases: dict[str, str] = {}
    dynamic_module_aliases: set[str] = set()
    assignments: list[tuple[set[str], ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            target_names = _assigned_name_targets(list(node.targets))
            if target_names:
                assignments.append((target_names, node.value))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target_names = _assigned_name_targets([node.target])
            if target_names:
                assignments.append((target_names, node.value))
        elif isinstance(node, ast.NamedExpr):
            target_names = _assigned_name_targets([node.target])
            if target_names:
                assignments.append((target_names, node.value))

    changed = True
    while changed:
        changed = False
        for target_names, value in assignments:
            callable_identity = _sensitive_callable_identity(
                value,
                module_aliases=module_aliases,
                imported_call_aliases=imported_call_aliases,
                sensitive_call_aliases=sensitive_call_aliases,
                dynamic_module_aliases=dynamic_module_aliases,
            )
            if callable_identity is not None:
                for target_name in target_names:
                    if sensitive_call_aliases.get(target_name) != callable_identity:
                        sensitive_call_aliases[target_name] = callable_identity
                        changed = True

            if _is_dynamic_import_result(
                value,
                module_aliases=module_aliases,
                imported_call_aliases=imported_call_aliases,
                sensitive_call_aliases=sensitive_call_aliases,
                dynamic_module_aliases=dynamic_module_aliases,
            ):
                before = len(dynamic_module_aliases)
                dynamic_module_aliases.update(target_names)
                changed = changed or len(dynamic_module_aliases) != before

    return sensitive_call_aliases, dynamic_module_aliases


def _assigned_name_targets(targets: list[ast.AST]) -> set[str]:
    names: set[str] = set()
    for target in targets:
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names.update(_assigned_name_targets(list(target.elts)))
    return names


def _sensitive_callable_identity(
    node: ast.AST,
    *,
    module_aliases: dict[str, str],
    imported_call_aliases: dict[str, tuple[str, str]],
    sensitive_call_aliases: dict[str, str],
    dynamic_module_aliases: set[str],
) -> str | None:
    if isinstance(node, ast.Name):
        alias_identity = sensitive_call_aliases.get(node.id)
        if alias_identity is not None:
            return alias_identity
        return _direct_sensitive_name_identity(
            node.id,
            imported_call_aliases=imported_call_aliases,
        )

    if isinstance(node, ast.Attribute):
        return _sensitive_attribute_identity(
            node,
            module_aliases=module_aliases,
            sensitive_call_aliases=sensitive_call_aliases,
            dynamic_module_aliases=dynamic_module_aliases,
        )

    if isinstance(node, ast.Call):
        literal_violation = _literal_reflective_sensitive_violation(
            node,
            module_aliases=module_aliases,
            sensitive_call_aliases=sensitive_call_aliases,
            dynamic_module_aliases=dynamic_module_aliases,
        )
        if literal_violation is not None:
            return literal_violation
        if _is_getattr_dynamic_import_call(
            node,
            module_aliases=module_aliases,
            imported_call_aliases=imported_call_aliases,
            sensitive_call_aliases=sensitive_call_aliases,
        ):
            return "getattr(__import__(...), ...)"

    return None


def _direct_sensitive_name_identity(
    name: str,
    *,
    imported_call_aliases: dict[str, tuple[str, str]],
) -> str | None:
    resolved = imported_call_aliases.get(name)
    if name in _SENSITIVE_APIS:
        return name
    if name == "open" or resolved == ("io", "open"):
        return "open"
    if name == "__import__":
        return "__import__"
    if resolved == ("importlib", "import_module"):
        return "importlib.import_module"
    if name in _REFLECTIVE_PRIMITIVES:
        return name
    if resolved is None:
        return None

    module_name, attr_name = resolved
    if module_name == "os" and attr_name in _SENSITIVE_OS_ATTRS:
        return f"os.{attr_name}"
    if module_name == "os" and attr_name in _SENSITIVE_OS_ENV_CALLS:
        return f"os.{attr_name}"
    if module_name in _SENSITIVE_APIS:
        return f"{module_name}.{attr_name}"
    return None


def _sensitive_attribute_identity(
    node: ast.Attribute,
    *,
    module_aliases: dict[str, str],
    sensitive_call_aliases: dict[str, str],
    dynamic_module_aliases: set[str],
) -> str | None:
    obj_name = node.value.id if isinstance(node.value, ast.Name) else None
    resolved_obj = module_aliases.get(obj_name or "", obj_name or "")

    if obj_name in dynamic_module_aliases:
        return f"dynamic_import.{node.attr}"
    if resolved_obj == "os" and node.attr in _SENSITIVE_OS_ATTRS:
        return f"os.{node.attr}"
    if resolved_obj == "os" and node.attr in _SENSITIVE_OS_ENV_CALLS:
        return f"os.{node.attr}"
    if resolved_obj in _SENSITIVE_APIS:
        return f"{resolved_obj}.{node.attr}"
    if resolved_obj == "importlib" and node.attr == "import_module":
        return "importlib.import_module"
    if _is_dynamic_import_call(
        node.value,
        module_aliases=module_aliases,
        imported_call_aliases={},
        sensitive_call_aliases=sensitive_call_aliases,
    ):
        return f"dynamic_import.{node.attr}"
    if node.attr in _DANGEROUS_FILE_READ_ATTRS:
        return f"*.{node.attr}"
    return None


def _is_dynamic_import_result(
    node: ast.AST,
    *,
    module_aliases: dict[str, str],
    imported_call_aliases: dict[str, tuple[str, str]],
    sensitive_call_aliases: dict[str, str],
    dynamic_module_aliases: set[str],
) -> bool:
    if isinstance(node, ast.Name) and node.id in dynamic_module_aliases:
        return True
    return _is_dynamic_import_call(
        node,
        module_aliases=module_aliases,
        imported_call_aliases=imported_call_aliases,
        sensitive_call_aliases=sensitive_call_aliases,
    )


def _sensitive_call_violations(
    node: ast.Call,
    *,
    module_aliases: dict[str, str],
    imported_call_aliases: dict[str, tuple[str, str]],
    sensitive_call_aliases: dict[str, str],
    dynamic_module_aliases: set[str],
) -> list[str]:
    func = node.func
    violations: list[str] = []

    if isinstance(func, ast.Name):
        sensitive_identity = _sensitive_callable_identity(
            func,
            module_aliases=module_aliases,
            imported_call_aliases=imported_call_aliases,
            sensitive_call_aliases=sensitive_call_aliases,
            dynamic_module_aliases=dynamic_module_aliases,
        )
        if sensitive_identity in _REFLECTIVE_PRIMITIVES:
            literal_violation = _literal_reflective_sensitive_violation(
                node,
                module_aliases=module_aliases,
                sensitive_call_aliases=sensitive_call_aliases,
                dynamic_module_aliases=dynamic_module_aliases,
            )
            if literal_violation is not None:
                violations.append(literal_violation)
            violation = _reflective_primitive_violation(
                sensitive_identity,
                node,
                module_aliases=module_aliases,
                imported_call_aliases=imported_call_aliases,
                sensitive_call_aliases=sensitive_call_aliases,
            )
            if violation is not None:
                violations.append(violation)
        elif sensitive_identity is not None:
            violations.append(
                _format_sensitive_call_violation(func.id, sensitive_identity)
            )

    elif isinstance(func, ast.Attribute):
        sensitive_identity = _sensitive_attribute_identity(
            func,
            module_aliases=module_aliases,
            sensitive_call_aliases=sensitive_call_aliases,
            dynamic_module_aliases=dynamic_module_aliases,
        )
        if sensitive_identity is not None:
            violations.append(_format_sensitive_call_violation(None, sensitive_identity))

    elif isinstance(func, ast.Call):
        if _is_getattr_dynamic_import_call(
            func,
            module_aliases=module_aliases,
            imported_call_aliases=imported_call_aliases,
            sensitive_call_aliases=sensitive_call_aliases,
        ):
            violations.append("getattr(__import__(...), ...)(...)")
        elif (
            _is_getattr_name(func.func, sensitive_call_aliases)
            and _getattr_uses_dynamic_attr_name(func)
        ):
            violations.append("getattr(..., dynamic_name)(...)")

    return violations


def _format_sensitive_call_violation(alias_name: str | None, identity: str) -> str:
    suffix = "" if identity.endswith("(...)") else "(...)"
    if alias_name is not None and alias_name != identity:
        return f"{identity} alias {alias_name}{suffix}"
    return f"{identity}{suffix}"


def _literal_reflective_sensitive_violation(
    node: ast.Call,
    *,
    module_aliases: dict[str, str],
    sensitive_call_aliases: dict[str, str],
    dynamic_module_aliases: set[str],
) -> str | None:
    if not (
        _is_getattr_name(node.func, sensitive_call_aliases)
        and len(node.args) >= 2
        and is_string_literal_node(node.args[1])
        and isinstance(node.args[0], ast.Name)
    ):
        return None
    obj_name = node.args[0].id
    if obj_name in dynamic_module_aliases:
        return "getattr(dynamic_import, ...)"
    module_name = module_aliases.get(obj_name, obj_name)
    attr_name = str(getattr(node.args[1], "value", "") or "")
    if module_name == "os" and attr_name in _SENSITIVE_OS_ATTRS:
        return f"getattr(os, {attr_name!r})(...)"
    if module_name == "os" and attr_name in _SENSITIVE_OS_ENV_CALLS:
        return f"getattr(os, {attr_name!r})(...)"
    if module_name == "os" and attr_name == "environ":
        return "getattr(os, 'environ')"
    if module_name == "importlib" and attr_name == "import_module":
        return "getattr(importlib, 'import_module')(...)"
    if module_name in _SENSITIVE_APIS:
        return f"getattr({module_name}, {attr_name!r})(...)"
    return None


def _reflective_primitive_violation(
    name: str,
    node: ast.Call,
    *,
    module_aliases: dict[str, str],
    imported_call_aliases: dict[str, tuple[str, str]],
    sensitive_call_aliases: dict[str, str],
) -> str | None:
    if name in {"setattr", "delattr", "globals", "locals", "vars"}:
        return f"{name}(...)"
    if name != "getattr":
        return None
    if _is_getattr_dynamic_import_call(
        node,
        module_aliases=module_aliases,
        imported_call_aliases=imported_call_aliases,
        sensitive_call_aliases=sensitive_call_aliases,
    ):
        return "getattr(__import__(...), ...)"
    if _getattr_uses_dynamic_attr_name(node):
        return "getattr(..., dynamic_name)"
    return None


def _getattr_uses_dynamic_attr_name(node: ast.Call) -> bool:
    return len(node.args) >= 2 and not is_string_literal_node(node.args[1])


def _is_getattr_name(
    node: ast.AST,
    sensitive_call_aliases: dict[str, str],
) -> bool:
    return (
        isinstance(node, ast.Name)
        and (node.id == "getattr" or sensitive_call_aliases.get(node.id) == "getattr")
    )


def _is_dynamic_import_call(
    node: ast.AST,
    *,
    module_aliases: dict[str, str],
    imported_call_aliases: dict[str, tuple[str, str]],
    sensitive_call_aliases: dict[str, str],
) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        if func.id == "__import__":
            return True
        if sensitive_call_aliases.get(func.id) in {
            "__import__",
            "importlib.import_module",
        }:
            return True
        if imported_call_aliases.get(func.id) == ("importlib", "import_module"):
            return True
        return False
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "import_module"
        and isinstance(func.value, ast.Name)
        and module_aliases.get(func.value.id, func.value.id) == "importlib"
    )


def _is_getattr_dynamic_import_call(
    node: ast.Call,
    *,
    module_aliases: dict[str, str],
    imported_call_aliases: dict[str, tuple[str, str]],
    sensitive_call_aliases: dict[str, str],
) -> bool:
    return (
        _is_getattr_name(node.func, sensitive_call_aliases)
        and bool(node.args)
        and _is_dynamic_import_call(
            node.args[0],
            module_aliases=module_aliases,
            imported_call_aliases=imported_call_aliases,
            sensitive_call_aliases=sensitive_call_aliases,
        )
    )


def _is_os_environ_attr(
    node: ast.Attribute,
    module_aliases: dict[str, str],
) -> bool:
    if node.attr != "environ" or not isinstance(node.value, ast.Name):
        return False
    return module_aliases.get(node.value.id, node.value.id) == "os"


def _context_baseline_call_violations_in_baseline_algorithm(
    file_path: str,
    tree: ast.AST,
) -> list[str]:
    try:
        normalized = normalize_relative_patch_path(file_path)
    except ValueError:
        normalized = str(file_path or "").replace("\\", "/").lstrip("/")
    if normalized != "policies/baseline_algorithm.py":
        return []

    context_aliases = {"context"}
    getattr_aliases = {"getattr"}
    baseline_aliases: set[str] = set()
    assignments: list[tuple[set[str], ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if value is None:
                continue
            targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
            target_names = _assigned_name_targets_for_contract_baseline(targets)
            if target_names:
                assignments.append((target_names, value))

    changed = True
    while changed:
        changed = False
        for target_names, value in assignments:
            if isinstance(value, ast.Name) and value.id in context_aliases:
                before = len(context_aliases)
                context_aliases.update(target_names)
                changed = changed or len(context_aliases) != before
            elif isinstance(value, ast.Name) and value.id in getattr_aliases:
                before = len(getattr_aliases)
                getattr_aliases.update(target_names)
                changed = changed or len(getattr_aliases) != before
            elif isinstance(value, ast.Name) and value.id in baseline_aliases:
                before = len(baseline_aliases)
                baseline_aliases.update(target_names)
                changed = changed or len(baseline_aliases) != before
            elif _is_context_baseline_attribute(value, context_aliases) or (
                isinstance(value, ast.Call)
                and _is_context_baseline_getattr(
                    value,
                    context_aliases,
                    getattr_aliases,
                )
            ):
                before = len(baseline_aliases)
                baseline_aliases.update(target_names)
                changed = changed or len(baseline_aliases) != before

    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if _is_context_baseline_attribute(func, context_aliases):
            findings.append("context.baseline(...)")
        elif isinstance(func, ast.Call) and _is_context_baseline_getattr(
            func,
            context_aliases,
            getattr_aliases,
        ):
            findings.append("getattr(context, 'baseline')(...)")
        elif isinstance(func, ast.Name) and func.id in baseline_aliases:
            findings.append(f"context.baseline alias {func.id}(...)")

    if not findings:
        return []
    return [
        "policies/baseline_algorithm.py must not call context.baseline(...): "
        + ", ".join(sorted(set(findings)))
    ]


def _assigned_name_targets_for_contract_baseline(
    targets: list[ast.AST],
) -> set[str]:
    names: set[str] = set()
    for target in targets:
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            names.update(_assigned_name_targets_for_contract_baseline(list(target.elts)))
    return names


def _is_context_baseline_attribute(
    node: ast.AST,
    context_aliases: set[str],
) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "baseline"
        and isinstance(node.value, ast.Name)
        and node.value.id in context_aliases
    )


def _is_context_baseline_getattr(
    node: ast.Call,
    context_aliases: set[str],
    getattr_aliases: set[str],
) -> bool:
    return (
        isinstance(node.func, ast.Name)
        and node.func.id in getattr_aliases
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id in context_aliases
        and is_string_literal_node(node.args[1])
        and node.args[1].value == "baseline"
    )
