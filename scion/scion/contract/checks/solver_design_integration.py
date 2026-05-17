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
from collections.abc import Callable
from dataclasses import dataclass

from scion.core.models import PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path


@dataclass(frozen=True)
class SolverDesignIntegrationResult:
    passed: bool
    detail: str


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
_FORBIDDEN_SOLUTION_BRIDGE_METHODS = frozenset(
    {"from_routes", "from_public", "from_cvrp_solution", "to_public"}
)


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
    candidate_sources: dict[str, str] = {}
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
        candidate_sources[file_rel] = change.code_content
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
        state_model_error = _state_model_bridge_api_error(
            file_rel=file_rel,
            tree=tree,
        )
        if state_model_error is not None:
            return SolverDesignIntegrationResult(False, state_model_error)

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

    import_error = _solver_design_import_export_error(
        candidate_sources,
        champion_file_content=champion_file_content,
        primary_path=primary_path,
    )
    if import_error is not None:
        return SolverDesignIntegrationResult(False, import_error)

    solve_structure_error = _scheduler_additional_solve_structure_error(
        candidate_sources,
        champion_file_content=champion_file_content,
        primary_path=primary_path,
    )
    if solve_structure_error is not None:
        return SolverDesignIntegrationResult(False, solve_structure_error)

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
        "context.make_solution(solution.routes_as_tuples()). "
        + "; ".join(parts)
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
        if not (
            isinstance(value.func, ast.Name)
            and value.func.id in solution_aliases
        ):
            continue
        for target in targets:
            names.update(_assigned_name_targets(target))
    return names


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
    if not any("solve" in method_defs.get(class_name, set()) for class_name in runtime_classes):
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
        elif isinstance(func.value, ast.Call) and _is_alnsvns_constructor_call(func.value):
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
        accepted_keywords = _function_keyword_parameter_names(init_node, skip_first=True)
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
            targets = list(child.targets) if isinstance(child, ast.Assign) else [child.target]
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
