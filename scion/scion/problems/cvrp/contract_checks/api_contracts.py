"""CVRP baseline/scheduler solver-design API compatibility checks."""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass

from scion.problems.cvrp.contract_checks.ast_discovery import (
    _alnsvns_solver_instance_names,
    _call_reference_names,
    _class_method_defs,
    _class_method_node,
    _function_keyword_parameter_names,
    _function_positional_parameter_names,
    _function_signature_text,
    _is_alnsvns_constructor_call,
    _load_names,
    _module_level_class_defs_from_source,
    _module_level_function_defs,
    _scheduler_entrypoint_imports,
    _solver_design_runtime_class_roots,
)


@dataclass(frozen=True)
class _LoopSignature:
    kind: str
    detail: str
    line: int | None


_STABLE_SOLVER_CONSTRUCTOR_KEYWORDS = (
    "time_limit",
    "destroy_ratio",
    "segment_length",
    "reaction_factor",
    "vns_max_no_improve",
    "use_vns",
    "cw_threshold",
    "vns_threshold",
    "alns_threshold",
    "max_destroy_customers",
    "max_routes",
    "context",
)
_STABLE_SOLVER_CONSTRUCTOR_KEYWORD_SET = set(_STABLE_SOLVER_CONSTRUCTOR_KEYWORDS)
_STABLE_SOLVER_SOLVE_SIGNATURE = ("self", "instance", "rng")


def _additional_wiring_edit_error(
    *,
    file_rel: str,
    primary_path: str,
    champion_code: str | None,
    candidate_code: str,
) -> str | None:
    if file_rel == primary_path:
        return None
    if file_rel == "policies/baseline_algorithm.py":
        return _baseline_algorithm_integration_error(
            primary_path=primary_path,
            candidate_code=candidate_code,
        )
    if file_rel == "policies/baseline_modules/scheduler.py":
        return _scheduler_integration_contract_error(
            primary_path=primary_path,
            champion_code=champion_code,
            candidate_code=candidate_code,
        )
    return None


def _baseline_algorithm_integration_error(
    *,
    primary_path: str,
    candidate_code: str,
) -> str | None:
    try:
        tree = ast.parse(candidate_code)
    except SyntaxError:
        return None
    bad_imports = _scheduler_entrypoint_imports(tree)
    call_refs = _call_reference_names(tree)
    load_names = _load_names(tree)
    if bad_imports:
        return (
            "baseline_algorithm.py integration edits must keep the stable "
            "scheduler class API when they are not the approved primary target. "
            f"primary_target={primary_path}; bad_scheduler_imports={bad_imports}. "
            "Import _ALNSVNSSolver, instantiate it, and call solver.solve(instance, rng)."
        )
    if "solve_with_context" in call_refs:
        return (
            "baseline_algorithm.py integration edits must not introduce a new "
            "scheduler runtime API when they are not the approved primary target. "
            f"primary_target={primary_path}; found solve_with_context call. "
            "Keep _ALNSVNSSolver.solve(instance, rng) as the stable branch entrypoint."
        )
    if "_ALNSVNSSolver" not in load_names or "solve" not in call_refs:
        return (
            "baseline_algorithm.py integration edits must remain a stable wiring "
            "wrapper when they are not the approved primary target. "
            f"primary_target={primary_path}; expected _ALNSVNSSolver and solve(...)."
        )
    constructor_error = _baseline_algorithm_constructor_call_error(
        tree,
        primary_path=primary_path,
    )
    if constructor_error is not None:
        return constructor_error
    solve_call_error = _baseline_algorithm_solver_solve_call_error(
        tree,
        primary_path=primary_path,
    )
    if solve_call_error is not None:
        return solve_call_error
    return None


def _scheduler_integration_contract_error(
    *,
    primary_path: str,
    champion_code: str | None,
    candidate_code: str,
) -> str | None:
    try:
        tree = ast.parse(candidate_code)
    except SyntaxError:
        return None
    top_level_functions = _module_level_function_defs(tree)
    legacy_entrypoints = sorted(
        top_level_functions & {"solve", "run", "main", "_run", "_run_scheduler"}
    )
    if legacy_entrypoints:
        return (
            "scheduler.py integration edits must keep the class-based solver "
            "runtime entrypoint when they are not the approved primary target. "
            f"primary_target={primary_path}; legacy_entrypoints={legacy_entrypoints}. "
            "Wire the mechanism through _ALNSVNSSolver.solve instead of adding "
            "top-level solve/run/main functions."
        )

    champion_classes = _module_level_class_defs_from_source(champion_code)
    runtime_classes = _solver_design_runtime_class_roots(
        tree,
        champion_classes=champion_classes,
    )
    method_defs = _class_method_defs(tree)
    if not runtime_classes:
        return (
            "scheduler.py integration edits must preserve an active runtime "
            "solver class when they are not the approved primary target. "
            f"primary_target={primary_path}; expected _ALNSVNSSolver or a "
            "_ALNSVNSSolver class alias."
        )
    if not any(
        "solve" in method_defs.get(class_name, set()) for class_name in runtime_classes
    ):
        return (
            "scheduler.py integration edits must preserve "
            "_ALNSVNSSolver.solve(instance, rng) when they are not the approved "
            f"primary target. primary_target={primary_path}; "
            f"runtime_classes={sorted(runtime_classes)}."
        )
    constructor_error = _scheduler_constructor_contract_error(
        tree,
        runtime_classes=runtime_classes,
        primary_path=primary_path,
    )
    if constructor_error is not None:
        return constructor_error
    solve_signature_error = _scheduler_solve_signature_contract_error(
        tree,
        runtime_classes=runtime_classes,
        primary_path=primary_path,
    )
    if solve_signature_error is not None:
        return solve_signature_error
    return None


def _baseline_algorithm_constructor_call_error(
    tree: ast.AST,
    *,
    primary_path: str,
) -> str | None:
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _is_alnsvns_constructor_call(node)
    ]
    if not calls:
        return (
            "baseline_algorithm.py integration edits must instantiate "
            "_ALNSVNSSolver with the stable constructor keyword arguments "
            "when they are not the approved primary target. "
            f"primary_target={primary_path}; no constructor call found."
        )
    for call in calls:
        if call.args:
            return (
                "baseline_algorithm.py integration edits must instantiate "
                "_ALNSVNSSolver with explicit stable keyword arguments, not "
                "positional arguments, when they are not the approved primary "
                f"target. primary_target={primary_path}; line={call.lineno}; "
                f"expected_keywords={list(_STABLE_SOLVER_CONSTRUCTOR_KEYWORDS)}."
            )
        if any(keyword.arg is None for keyword in call.keywords):
            return (
                "baseline_algorithm.py integration edits must list the stable "
                "_ALNSVNSSolver constructor keywords explicitly instead of "
                "using **kwargs when they are not the approved primary target. "
                f"primary_target={primary_path}; line={call.lineno}; "
                f"expected_keywords={list(_STABLE_SOLVER_CONSTRUCTOR_KEYWORDS)}."
            )
        keyword_names = {str(keyword.arg) for keyword in call.keywords}
        missing = sorted(_STABLE_SOLVER_CONSTRUCTOR_KEYWORD_SET - keyword_names)
        extra = sorted(keyword_names - _STABLE_SOLVER_CONSTRUCTOR_KEYWORD_SET)
        if missing or extra:
            return (
                "baseline_algorithm.py integration edits must preserve the "
                "stable _ALNSVNSSolver constructor API when they are not the "
                f"approved primary target. primary_target={primary_path}; "
                f"line={call.lineno}; missing_keywords={missing}; "
                f"unexpected_keywords={extra}; "
                f"expected_keywords={list(_STABLE_SOLVER_CONSTRUCTOR_KEYWORDS)}."
            )
    return None


def _baseline_algorithm_solver_solve_call_error(
    tree: ast.AST,
    *,
    primary_path: str,
) -> str | None:
    solver_names = _alnsvns_solver_instance_names(tree)
    solve_calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "solve":
            continue
        if isinstance(func.value, ast.Name) and func.value.id in solver_names:
            solve_calls.append(node)
        elif isinstance(func.value, ast.Call) and _is_alnsvns_constructor_call(
            func.value
        ):
            solve_calls.append(node)
    if not solve_calls:
        return (
            "baseline_algorithm.py integration edits must call "
            "solver.solve(instance, rng) on the stable _ALNSVNSSolver instance "
            "when they are not the approved primary target. "
            f"primary_target={primary_path}; no stable solver.solve call found."
        )
    for call in solve_calls:
        if len(call.args) != 2 or call.keywords:
            return (
                "baseline_algorithm.py integration edits must keep the stable "
                "solver.solve(instance, rng) call without extra positional or "
                "keyword arguments when they are not the approved primary "
                f"target. primary_target={primary_path}; line={call.lineno}; "
                f"positional_args={len(call.args)}; "
                f"keyword_args={[keyword.arg for keyword in call.keywords]}."
            )
    return None


def _scheduler_constructor_contract_error(
    tree: ast.AST,
    *,
    runtime_classes: set[str],
    primary_path: str,
) -> str | None:
    for class_name in sorted(runtime_classes):
        init_node = _class_method_node(tree, class_name, "__init__")
        if init_node is None:
            return (
                "scheduler.py integration edits must preserve the explicit "
                "_ALNSVNSSolver constructor keyword API when they are not the "
                f"approved primary target. primary_target={primary_path}; "
                f"runtime_class={class_name}; no __init__ method found; "
                f"expected_keywords={list(_STABLE_SOLVER_CONSTRUCTOR_KEYWORDS)}."
            )
        accepted_keywords = _function_keyword_parameter_names(
            init_node, skip_first=True
        )
        missing = sorted(_STABLE_SOLVER_CONSTRUCTOR_KEYWORD_SET - accepted_keywords)
        if missing:
            return (
                "scheduler.py integration edits must keep _ALNSVNSSolver "
                "constructor-compatible with baseline_algorithm.py when they "
                f"are not the approved primary target. primary_target={primary_path}; "
                f"runtime_class={class_name}; missing_keywords={missing}; "
                f"expected_keywords={list(_STABLE_SOLVER_CONSTRUCTOR_KEYWORDS)}."
            )
    return None


def _scheduler_solve_signature_contract_error(
    tree: ast.AST,
    *,
    runtime_classes: set[str],
    primary_path: str,
) -> str | None:
    for class_name in sorted(runtime_classes):
        solve_node = _class_method_node(tree, class_name, "solve")
        if solve_node is None:
            continue
        positional = _function_positional_parameter_names(solve_node)
        if (
            tuple(positional) != _STABLE_SOLVER_SOLVE_SIGNATURE
            or solve_node.args.vararg is not None
            or solve_node.args.kwonlyargs
            or solve_node.args.kwarg is not None
        ):
            return (
                "scheduler.py integration edits must keep the stable "
                "_ALNSVNSSolver.solve(self, instance, rng) signature when they "
                f"are not the approved primary target. primary_target={primary_path}; "
                f"runtime_class={class_name}; found_signature="
                f"{_function_signature_text(solve_node)}."
            )
    return None


def _scheduler_solve_structure_contract_error(
    tree: ast.AST,
    *,
    champion_code: str | None,
    runtime_classes: set[str],
    primary_path: str,
) -> str | None:
    if not champion_code:
        return None
    try:
        champion_tree = ast.parse(champion_code)
    except SyntaxError:
        return None

    champion_solve = _class_method_node(champion_tree, "_ALNSVNSSolver", "solve")
    if champion_solve is None:
        return None
    candidate_solve = _class_method_node(tree, "_ALNSVNSSolver", "solve")
    if candidate_solve is None:
        for class_name in sorted(runtime_classes):
            candidate_solve = _class_method_node(tree, class_name, "solve")
            if candidate_solve is not None:
                break
    if candidate_solve is None:
        return None

    champion_loops = _solve_loop_signatures(champion_solve)
    candidate_loops = _solve_loop_signatures(candidate_solve)
    champion_whiles = [loop for loop in champion_loops if loop.kind == "while"]
    candidate_whiles = [loop for loop in candidate_loops if loop.kind == "while"]
    champion_fors = [loop for loop in champion_loops if loop.kind == "for"]
    candidate_fors = [loop for loop in candidate_loops if loop.kind == "for"]

    violations: list[str] = []
    if len(candidate_whiles) > len(champion_whiles):
        added = _unmatched_candidate_loops(champion_whiles, candidate_whiles)
        violations.append(
            "added_while_loops="
            + repr([{"line": loop.line, "test": loop.detail} for loop in added])
        )
    if len(candidate_whiles) < len(champion_whiles):
        removed = _unmatched_candidate_loops(candidate_whiles, champion_whiles)
        violations.append(
            "removed_while_loops="
            + repr([{"line": loop.line, "test": loop.detail} for loop in removed])
        )
    for index, (champion_loop, candidate_loop) in enumerate(
        zip(champion_whiles, candidate_whiles, strict=False)
    ):
        if champion_loop.detail != candidate_loop.detail:
            violations.append(
                "changed_while_condition="
                + repr(
                    {
                        "index": index,
                        "line": candidate_loop.line,
                        "from": champion_loop.detail,
                        "to": candidate_loop.detail,
                    }
                )
            )
    if len(candidate_fors) > len(champion_fors):
        added = _unmatched_candidate_loops(champion_fors, candidate_fors)
        violations.append(
            "added_for_loops="
            + repr([{"line": loop.line, "iter": loop.detail} for loop in added])
        )
    if len(candidate_fors) < len(champion_fors):
        removed = _unmatched_candidate_loops(candidate_fors, champion_fors)
        violations.append(
            "removed_for_loops="
            + repr([{"line": loop.line, "iter": loop.detail} for loop in removed])
        )
    for index, (champion_loop, candidate_loop) in enumerate(
        zip(champion_fors, candidate_fors, strict=False)
    ):
        if champion_loop.detail != candidate_loop.detail:
            violations.append(
                "changed_for_loop="
                + repr(
                    {
                        "index": index,
                        "line": candidate_loop.line,
                        "from": champion_loop.detail,
                        "to": candidate_loop.detail,
                    }
                )
            )

    if not violations:
        return None
    return (
        "scheduler.py additional_changes for a non-scheduler primary target "
        "may only perform minimal wiring. They must not rewrite "
        "_ALNSVNSSolver.solve's main search loop or add/replace "
        "search-bearing while/for loops. "
        f"primary_target={primary_path}; loop_changes={violations}. "
        "If you need to change scheduler.py's main loop, make "
        "policies/baseline_modules/scheduler.py the approved target; otherwise "
        "limit scheduler.py to import and operator registration wiring."
    )


def _scheduler_additional_solve_structure_error(
    candidate_sources: dict[str, str],
    *,
    champion_file_content: Callable[[str], str | None],
    primary_path: str,
) -> str | None:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    if primary_path == scheduler_path:
        return None
    candidate_code = candidate_sources.get(scheduler_path)
    if candidate_code is None:
        return None
    try:
        tree = ast.parse(candidate_code)
    except SyntaxError:
        return None
    champion_code = champion_file_content(scheduler_path)
    champion_classes = _module_level_class_defs_from_source(champion_code)
    runtime_classes = _solver_design_runtime_class_roots(
        tree,
        champion_classes=champion_classes,
    )
    if not runtime_classes:
        return None
    return _scheduler_solve_structure_contract_error(
        tree,
        champion_code=champion_code,
        runtime_classes=runtime_classes,
        primary_path=primary_path,
    )


def _unmatched_candidate_loops(
    champion_loops: list[_LoopSignature],
    candidate_loops: list[_LoopSignature],
) -> list[_LoopSignature]:
    remaining = [loop.detail for loop in champion_loops]
    unmatched: list[_LoopSignature] = []
    for loop in candidate_loops:
        if loop.detail in remaining:
            remaining.remove(loop.detail)
        else:
            unmatched.append(loop)
    return unmatched


def _solve_loop_signatures(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[_LoopSignature]:
    visitor = _SolveLoopSignatureVisitor()
    for stmt in node.body:
        visitor.visit(stmt)
    return visitor.loops


class _SolveLoopSignatureVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.loops: list[_LoopSignature] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return None

    def visit_While(self, node: ast.While) -> None:
        self.loops.append(
            _LoopSignature(
                kind="while",
                detail=_normalized_ast_detail(node.test),
                line=getattr(node, "lineno", None),
            )
        )
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.loops.append(
            _LoopSignature(
                kind="for",
                detail=_normalized_ast_detail(node.iter),
                line=getattr(node, "lineno", None),
            )
        )
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.loops.append(
            _LoopSignature(
                kind="for",
                detail=_normalized_ast_detail(node.iter),
                line=getattr(node, "lineno", None),
            )
        )
        self.generic_visit(node)


def _normalized_ast_detail(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=True, include_attributes=False)
