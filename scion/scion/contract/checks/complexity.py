"""Static complexity-bound checks."""
from __future__ import annotations

import ast
import time

from scion.contract.result_payload import check_result
from scion.core.models import CheckResult, PatchProposal


def check_complexity_bound(
    patch: PatchProposal,
    *,
    scale_names: frozenset[str],
    surface_error: str | None,
) -> CheckResult:
    t0 = time.monotonic_ns()
    if patch.action == "delete":
        return check_result(
            "C9c_complexity_bound",
            True,
            "heavy",
            "delete action — no complexity check",
            t0,
        )

    try:
        tree = ast.parse(patch.code_content)
    except SyntaxError:
        return check_result(
            "C9c_complexity_bound",
            False,
            "heavy",
            "unparseable code",
            t0,
        )

    if surface_error is not None:
        return check_result("C9c_complexity_bound", False, "heavy", surface_error, t0)
    itertools_aliases = _collect_itertools_aliases(tree)
    runtime_guard_names = _collect_runtime_guard_function_names(tree)
    _annotate_ast_parents(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_kind = _itertools_call_kind(node, itertools_aliases)
        if call_kind == "combinations":
            if len(node.args) < 2:
                continue
            k_arg = node.args[1]
            if isinstance(k_arg, ast.Constant) and isinstance(k_arg.value, int):
                if k_arg.value <= 2:
                    continue
                violations.append(f"combinations(..., {k_arg.value})")
            else:
                violations.append("combinations(..., variable_k)")
        elif call_kind == "permutations":
            violations.append("permutations(...)")
        elif call_kind == "product":
            scale_args = sum(
                1 for arg in node.args if _is_problem_scale_expr(arg, scale_names)
            )
            repeat_scale = _constant_int_kwarg(node, "repeat")
            if scale_args >= 2 or (
                scale_args == 1 and repeat_scale is not None and repeat_scale > 1
            ):
                violations.append("product(... problem-scale iterables ...)")

    for node in ast.walk(tree):
        if isinstance(node, ast.While) and not _is_bounded_while(
            node,
            scale_names,
            runtime_guard_names,
        ):
            violations.append(_uncapped_while_violation(patch.code_content, node))

    loop_guard = _ProblemScaleLoopGuard(scale_names)
    loop_guard.visit(tree)
    violations.extend(loop_guard.violations)

    if not violations:
        return check_result("C9c_complexity_bound", True, "heavy", "complexity ok", t0)
    return check_result(
        "C9c_complexity_bound",
        False,
        "heavy",
        "unbounded/high-order/high-risk enumeration detected: "
        f"{violations}. Use capped top-k candidate lists or sampling.",
        t0,
    )


def _collect_itertools_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "itertools":
            for alias in node.names:
                if alias.name in {"combinations", "permutations", "product"}:
                    aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "itertools":
                    aliases[alias.asname or alias.name] = "itertools"
    return aliases


def _itertools_call_kind(call_node: ast.Call, aliases: dict[str, str]) -> str | None:
    func = call_node.func
    if isinstance(func, ast.Name):
        return aliases.get(func.id)
    if isinstance(func, ast.Attribute):
        if func.attr not in {"combinations", "permutations", "product"}:
            return None
        if isinstance(func.value, ast.Name):
            resolved = aliases.get(func.value.id)
            if resolved == "itertools":
                return func.attr
        return None
    return None


def _constant_int_kwarg(call_node: ast.Call, name: str) -> int | None:
    for kw in call_node.keywords:
        if (
            kw.arg == name
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, int)
        ):
            return kw.value.value
    return None


def _is_problem_scale_expr(node: ast.AST, scale_names: frozenset[str]) -> bool:
    if not scale_names:
        return False
    if isinstance(node, ast.Name):
        return node.id in scale_names
    if isinstance(node, ast.Attribute):
        return node.attr in scale_names or _is_problem_scale_expr(
            node.value,
            scale_names,
        )
    if isinstance(node, ast.Subscript):
        return _is_problem_scale_expr(node.value, scale_names)
    if isinstance(node, ast.Call):
        return any(_is_problem_scale_expr(arg, scale_names) for arg in node.args)
    return False


def _is_bounded_while(
    node: ast.While,
    scale_names: frozenset[str],
    runtime_guard_names: frozenset[str] = frozenset(),
) -> bool:
    if isinstance(node.test, ast.Constant) and node.test.value is True:
        return (
            _while_body_has_bounded_break(node, runtime_guard_names)
            or _while_body_has_counter_bounded_break(
                node,
                scale_names,
                runtime_guard_names,
            )
            or _while_body_has_collection_progress_break(node)
        )
    if isinstance(node.test, ast.BoolOp):
        return any(
            _compare_has_small_constant(value)
            or _compare_has_incrementing_counter_guard(
                value,
                node,
                scale_names,
                runtime_guard_names,
            )
            or _compare_has_bounded_collection_size_progress(
                value,
                node,
                scale_names,
                runtime_guard_names,
            )
            or _compare_has_runtime_guard(value, runtime_guard_names)
            or _condition_collection_is_shrunk(value, node)
            for value in node.test.values
        ) or _while_body_has_bounded_break(node, runtime_guard_names)
    if isinstance(node.test, ast.Compare):
        return (
            _compare_has_small_constant(node.test)
            or _compare_has_incrementing_counter_guard(
                node.test,
                node,
                scale_names,
                runtime_guard_names,
            )
            or _compare_has_bounded_collection_size_progress(
                node.test,
                node,
                scale_names,
                runtime_guard_names,
            )
            or _compare_has_runtime_guard(node.test, runtime_guard_names)
        ) or _while_body_has_bounded_break(node, runtime_guard_names)
    return (
        _mentions_runtime_guard(node.test, runtime_guard_names)
        or _condition_collection_is_shrunk(node.test, node)
        or _while_body_has_bounded_break(node, runtime_guard_names)
    )


def _condition_collection_is_shrunk(test: ast.AST, node: ast.While) -> bool:
    names = _condition_collection_names(test)
    if not names:
        return False
    return any(_body_shrinks_collection(node.body, name) for name in names)


def _condition_collection_names(test: ast.AST) -> set[str]:
    if isinstance(test, ast.Name):
        return {test.id}
    if isinstance(test, ast.UnaryOp):
        return _condition_collection_names(test.operand)
    if isinstance(test, ast.BoolOp):
        names: set[str] = set()
        for value in test.values:
            names.update(_condition_collection_names(value))
        return names
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Name):
        if test.func.id == "len" and test.args and isinstance(test.args[0], ast.Name):
            return {test.args[0].id}
    return set()


def _compare_has_bounded_collection_size_progress(
    test: ast.AST,
    node: ast.While,
    scale_names: frozenset[str],
    runtime_guard_names: frozenset[str] = frozenset(),
) -> bool:
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    left = test.left
    right = test.comparators[0]
    op = test.ops[0]
    left_name = _len_call_name(left)
    right_name = _len_call_name(right)
    if left_name is not None:
        if not _is_effectively_bounded_limit_expr(
            right,
            node,
            left_name,
            scale_names,
            runtime_guard_names,
        ):
            return False
        if isinstance(op, (ast.Lt, ast.LtE)):
            return _body_grows_collection(node.body, left_name)
        if isinstance(op, (ast.Gt, ast.GtE)):
            return _body_shrinks_collection(node.body, left_name)
    if right_name is not None:
        if not _is_effectively_bounded_limit_expr(
            left,
            node,
            right_name,
            scale_names,
            runtime_guard_names,
        ):
            return False
        if isinstance(op, (ast.Lt, ast.LtE)):
            return _body_shrinks_collection(node.body, right_name)
        if isinstance(op, (ast.Gt, ast.GtE)):
            return _body_grows_collection(node.body, right_name)
    return False


def _len_call_name(expr: ast.AST) -> str | None:
    if (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "len"
        and len(expr.args) == 1
        and isinstance(expr.args[0], ast.Name)
    ):
        return expr.args[0].id
    return None


def _is_effectively_bounded_limit_expr(
    expr: ast.AST,
    while_node: ast.While,
    collection_name: str,
    scale_names: frozenset[str],
    runtime_guard_names: frozenset[str] = frozenset(),
) -> bool:
    if _expr_references_name(expr, collection_name):
        return False
    if _is_bounded_limit_expr(expr, scale_names) or _mentions_runtime_guard(
        expr,
        runtime_guard_names,
    ):
        return True
    if isinstance(expr, ast.Name):
        return _has_prior_bounded_assignment(
            while_node,
            expr.id,
            scale_names,
            runtime_guard_names,
        )
    return False


def _body_shrinks_collection(body: list[ast.stmt], name: str) -> bool:
    shrink_methods = {"remove", "discard", "pop", "clear"}
    for child in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if (
                isinstance(child.func.value, ast.Name)
                and child.func.value.id == name
                and child.func.attr in shrink_methods
            ):
                return True
        if isinstance(child, ast.AugAssign) and isinstance(child.target, ast.Name):
            if child.target.id == name and isinstance(child.op, (ast.Sub, ast.BitAnd)):
                return True
    return False


def _body_grows_collection(body: list[ast.stmt], name: str) -> bool:
    grow_methods = {"append", "add", "extend", "insert", "update"}
    for child in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if (
                isinstance(child.func.value, ast.Name)
                and child.func.value.id == name
                and child.func.attr in grow_methods
            ):
                return True
        if isinstance(child, ast.AugAssign) and isinstance(child.target, ast.Name):
            if child.target.id == name and isinstance(child.op, (ast.Add, ast.BitOr)):
                return True
        if isinstance(child, ast.Assign):
            if not any(
                isinstance(target, ast.Name) and target.id == name
                for target in child.targets
            ):
                continue
            if (
                isinstance(child.value, ast.BinOp)
                and isinstance(child.value.op, ast.Add)
                and _expr_references_name(child.value, name)
            ):
                return True
    return False


def _compare_has_incrementing_counter_guard(
    test: ast.AST,
    node: ast.While,
    scale_names: frozenset[str],
    runtime_guard_names: frozenset[str] = frozenset(),
) -> bool:
    if not isinstance(test, ast.Compare):
        return False
    expressions = [test.left, *test.comparators]
    for index, expr in enumerate(expressions):
        if not isinstance(expr, ast.Name):
            continue
        if not _body_increments_counter(node.body, expr.id):
            continue
        other_exprs = [
            other
            for other_index, other in enumerate(expressions)
            if other_index != index
        ]
        if any(
            _is_bounded_limit_expr(other, scale_names)
            or _mentions_runtime_guard(other, runtime_guard_names)
            for other in other_exprs
        ):
            return True
    return False


def _compare_has_runtime_guard(
    node: ast.AST,
    runtime_guard_names: frozenset[str] = frozenset(),
) -> bool:
    return isinstance(node, ast.Compare) and _mentions_runtime_guard(
        node,
        runtime_guard_names,
    )


def _body_increments_counter(body: list[ast.stmt], name: str) -> bool:
    for child in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(child, ast.AugAssign) and isinstance(child.target, ast.Name):
            if child.target.id == name and isinstance(child.op, (ast.Add, ast.Sub)):
                return True
        if isinstance(child, ast.Assign):
            if not any(
                isinstance(target, ast.Name) and target.id == name
                for target in child.targets
            ):
                continue
            if _expr_references_name(child.value, name):
                return True
    return False


def _is_bounded_limit_expr(expr: ast.AST, scale_names: frozenset[str]) -> bool:
    if _is_small_constant(expr):
        return True
    if isinstance(expr, ast.Name):
        lowered = expr.id.lower()
        return (
            expr.id.isupper()
            or "max" in lowered
            or "limit" in lowered
            or "cap" in lowered
            or "round" in lowered
            or "iter" in lowered
            or "strength" in lowered
        )
    if isinstance(expr, ast.Attribute):
        return expr.attr in scale_names
    if isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Name) and expr.func.id in {"len", "min", "max"}:
            return True
        return any(_is_bounded_limit_expr(arg, scale_names) for arg in expr.args)
    if isinstance(expr, ast.BinOp):
        return _is_bounded_limit_expr(expr.left, scale_names) or _is_bounded_limit_expr(
            expr.right,
            scale_names,
        )
    return False


def _while_body_has_bounded_break(
    node: ast.While,
    runtime_guard_names: frozenset[str] = frozenset(),
) -> bool:
    for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
        if not isinstance(child, ast.If):
            continue
        if not _contains_break(child.body):
            continue
        if _compare_has_small_constant(child.test) or _mentions_runtime_guard(
            child.test,
            runtime_guard_names,
        ):
            return True
    return False


def _while_body_has_counter_bounded_break(
    node: ast.While,
    scale_names: frozenset[str],
    runtime_guard_names: frozenset[str] = frozenset(),
) -> bool:
    for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
        if not isinstance(child, ast.If):
            continue
        if not _contains_break(child.body):
            continue
        if _compare_has_incrementing_counter_guard(
            child.test,
            node,
            scale_names,
            runtime_guard_names,
        ):
            return True
    return False


def _while_body_has_collection_progress_break(node: ast.While) -> bool:
    if not _contains_break(node.body):
        return False
    return any(_stmt_directly_shrinks_collection(stmt) for stmt in node.body)


def _stmt_directly_shrinks_collection(stmt: ast.stmt) -> bool:
    shrink_methods = {"remove", "discard", "pop", "clear"}
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        func = stmt.value.func
        return (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.attr in shrink_methods
        )
    if isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
        return isinstance(stmt.op, (ast.Sub, ast.BitAnd))
    return False


def _contains_break(body: list[ast.stmt]) -> bool:
    return any(isinstance(child, ast.Break) for stmt in body for child in ast.walk(stmt))


def _uncapped_while_violation(code: str, node: ast.While) -> str:
    line = getattr(node, "lineno", None)
    source = ast.get_source_segment(code, node.test)
    snippet = ""
    if source:
        snippet = " ".join(source.strip().split())
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
    hint = "add an iteration cap, runtime guard, or bounded break"
    if line is None:
        base = "uncapped while loop"
    else:
        base = f"uncapped while loop at line {line}"
    if snippet:
        return f"{base} condition={snippet!r}; hint: {hint}"
    return f"{base}; hint: {hint}"


def _collect_runtime_guard_function_names(tree: ast.AST) -> frozenset[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if (
                isinstance(child, ast.Return)
                and child.value is not None
                and _mentions_runtime_guard(child.value)
            ):
                names.add(node.name)
                break
    return frozenset(names)


def _annotate_ast_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_scion_parent", parent)


def _has_prior_bounded_assignment(
    node: ast.AST,
    name: str,
    scale_names: frozenset[str],
    runtime_guard_names: frozenset[str] = frozenset(),
) -> bool:
    current = node
    parent = getattr(current, "_scion_parent", None)
    while parent is not None:
        found_container = False
        for field_name in ("body", "orelse", "finalbody"):
            body = getattr(parent, field_name, None)
            if not isinstance(body, list) or current not in body:
                continue
            found_container = True
            index = body.index(current)
            for stmt in reversed(body[:index]):
                if _stmt_assigns_bounded_name(
                    stmt,
                    name,
                    scale_names,
                    runtime_guard_names,
                ):
                    return True
            break
        current = parent
        parent = getattr(current, "_scion_parent", None)
        if not found_container:
            continue
    return False


def _stmt_assigns_bounded_name(
    stmt: ast.stmt,
    name: str,
    scale_names: frozenset[str],
    runtime_guard_names: frozenset[str] = frozenset(),
) -> bool:
    if isinstance(stmt, ast.Assign):
        if not any(
            isinstance(target, ast.Name) and target.id == name
            for target in stmt.targets
        ):
            return False
        return _is_bounded_limit_expr(stmt.value, scale_names) or _mentions_runtime_guard(
            stmt.value,
            runtime_guard_names,
        )
    if (
        isinstance(stmt, ast.AnnAssign)
        and isinstance(stmt.target, ast.Name)
        and stmt.target.id == name
        and stmt.value is not None
    ):
        return _is_bounded_limit_expr(stmt.value, scale_names) or _mentions_runtime_guard(
            stmt.value,
            runtime_guard_names,
        )
    return False


def _mentions_runtime_guard(
    node: ast.AST,
    runtime_guard_names: frozenset[str] = frozenset(),
) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr in {
            "remaining_time",
            "elapsed_ms",
        }:
            return True
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name) and func.id in runtime_guard_names:
                return True
            if isinstance(func, ast.Attribute) and func.attr in runtime_guard_names:
                return True
        if isinstance(child, ast.Name) and child.id in {
            "remaining_time",
            "elapsed_ms",
        }:
            return True
    return False


def _expr_references_name(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(child, ast.Name) and child.id == name
        for child in ast.walk(node)
    )


def _compare_has_small_constant(node: ast.AST) -> bool:
    if not isinstance(node, ast.Compare):
        return False
    comparators = [node.left, *node.comparators]
    return any(_is_small_constant(expr) for expr in comparators)


def _is_small_constant(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and 0 <= node.value <= 1000
    )


class _ProblemScaleLoopGuard(ast.NodeVisitor):
    def __init__(self, scale_names: frozenset[str]) -> None:
        self._scale_names = scale_names
        self._depth = 0
        self.violations: list[str] = []

    def visit_For(self, node: ast.For) -> None:
        is_scale = _is_problem_scale_expr(node.iter, self._scale_names)
        if is_scale:
            self._depth += 1
            if self._depth >= 3:
                self.violations.append("three-level problem-scale nested loops")
        self.generic_visit(node)
        if is_scale:
            self._depth -= 1
