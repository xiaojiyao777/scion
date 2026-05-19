"""AST discovery primitives for CVRP solver-design contract checks."""

from __future__ import annotations

import ast


def _assigned_name_targets(node: ast.AST) -> set[str]:
    names: set[str] = set()
    if isinstance(node, ast.Name):
        names.add(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for item in node.elts:
            names.update(_assigned_name_targets(item))
    return names


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
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
        for arg in child.args:
            names.update(_active_registration_reference_names(arg))
        for keyword in child.keywords:
            names.update(_active_registration_reference_names(keyword.value))
    for child in ast.walk(node):
        if isinstance(child, ast.Return):
            names.update(_active_registration_reference_names(child.value))
        elif isinstance(child, (ast.Assign, ast.AnnAssign)):
            targets = (
                list(child.targets) if isinstance(child, ast.Assign) else [child.target]
            )
            if any(_is_active_registration_target(target) for target in targets):
                names.update(_active_registration_reference_names(child.value))
    return names


def _active_registration_reference_names(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return {node.id}
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        names: set[str] = set()
        for item in node.elts:
            names.update(_active_registration_reference_names(item))
        return names
    if isinstance(node, ast.Dict):
        names: set[str] = set()
        for item in [*node.keys, *node.values]:
            names.update(_active_registration_reference_names(item))
        return names
    return set()


def _is_active_registration_target(node: ast.AST) -> bool:
    if not isinstance(node, ast.Name):
        return False
    lowered = node.id.lower()
    if lowered in {
        "destroy_ops",
        "repair_ops",
        "local_search_ops",
        "construction_ops",
        "construction_methods",
        "construction_candidates",
        "constructors",
    }:
        return True
    if lowered.endswith("_ops") or lowered.endswith("_operators"):
        return True
    return any(
        token in lowered
        for token in ("operator", "operators", "registry", "registrations", "hooks")
    )


def _load_names(node: ast.AST) -> set[str]:
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }


def _is_alnsvns_constructor_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Name) and node.func.id == "_ALNSVNSSolver"


def _alnsvns_solver_instance_names(tree: ast.AST) -> set[str]:
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
        if not isinstance(value, ast.Call) or not _is_alnsvns_constructor_call(value):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _class_method_node(
    tree: ast.AST,
    class_name: str,
    method_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    if not isinstance(tree, ast.Module):
        return None
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if (
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == method_name
            ):
                return item
    return None


def _function_positional_parameter_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    return [arg.arg for arg in [*node.args.posonlyargs, *node.args.args]]


def _function_keyword_parameter_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    skip_first: bool,
) -> set[str]:
    positional = _function_positional_parameter_names(node)
    if skip_first and positional:
        positional = positional[1:]
    return set(positional) | {arg.arg for arg in node.args.kwonlyargs}


def _function_signature_text(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts = _function_positional_parameter_names(node)
    if node.args.vararg is not None:
        parts.append("*" + node.args.vararg.arg)
    elif node.args.kwonlyargs:
        parts.append("*")
    parts.extend(arg.arg for arg in node.args.kwonlyargs)
    if node.args.kwarg is not None:
        parts.append("**" + node.args.kwarg.arg)
    return f"{node.name}({', '.join(parts)})"


def _scheduler_entrypoint_imports(tree: ast.AST) -> list[str]:
    bad: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = str(node.module or "")
        if not module.endswith("baseline_modules.scheduler"):
            continue
        for alias in node.names:
            name = str(alias.name or "")
            if name in {"solve", "run", "main", "_run", "_run_scheduler"}:
                bad.add(name)
    return sorted(bad)
