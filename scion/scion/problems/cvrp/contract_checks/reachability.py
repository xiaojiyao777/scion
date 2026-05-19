"""Call-graph reachability checks for CVRP solver-design helpers."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from scion.problems.cvrp.contract_checks.ast_discovery import (
    _class_method_defs,
    _class_method_defs_from_source,
    _module_call_references,
    _module_level_class_defs_from_source,
    _module_level_function_defs,
    _module_level_function_defs_from_source,
    _new_class_method_names,
    _reachable_class_method_calls,
    _solver_design_runtime_class_roots,
)


@dataclass
class ReachabilityState:
    new_functions: set[str] = field(default_factory=set)
    new_functions_by_file: dict[str, set[str]] = field(default_factory=dict)
    call_graph: dict[str, set[str]] = field(default_factory=dict)
    root_calls: set[str] = field(default_factory=set)
    changed_paths: list[str] = field(default_factory=list)
    changed_files: int = 0

    def record_file(
        self, file_rel: str, tree: ast.AST, champion_code: str | None
    ) -> None:
        self.changed_files += 1
        self.changed_paths.append(file_rel)

        current_defs = _module_level_function_defs(tree)
        champion_defs = _module_level_function_defs_from_source(champion_code)
        local_new = current_defs - champion_defs
        current_methods = _class_method_defs(tree)
        champion_methods = _class_method_defs_from_source(champion_code)
        local_new_methods = _new_class_method_names(current_methods, champion_methods)
        if local_new:
            self.new_functions.update(local_new)
            self.new_functions_by_file[file_rel] = set(local_new)
        if local_new_methods:
            self.new_functions.update(local_new_methods)
            self.new_functions_by_file.setdefault(file_rel, set()).update(
                local_new_methods
            )
        local_existing = current_defs - local_new

        module_calls, function_calls, class_method_calls = _module_call_references(tree)
        self.root_calls.update(module_calls)
        if (
            file_rel
            == "policies/baseline_algorithm.py"
            and "solve" in current_defs
        ):
            self.root_calls.add("solve")
        for root in local_existing:
            self.root_calls.update(function_calls.get(root, set()))
        class_roots = _solver_design_runtime_class_roots(
            tree,
            champion_classes=_module_level_class_defs_from_source(champion_code),
        )
        for class_name in class_roots:
            self.root_calls.update(
                _reachable_class_method_calls(
                    class_method_calls.get(class_name, {}),
                    root_method="solve",
                )
            )
            self.root_calls.add("solve")
        for name, calls in function_calls.items():
            self.call_graph.setdefault(name, set()).update(calls)
        for method_calls in class_method_calls.values():
            for name, calls in method_calls.items():
                self.call_graph.setdefault(name, set()).update(calls)

    def no_helper_detail(self) -> str | None:
        if self.changed_files == 0 or not self.new_functions:
            return "no new solver_design helper functions"
        return None

    def inert_helper_detail(self) -> str | None:
        reachable = set(self.root_calls)
        queue = list(self.root_calls)
        seen = set(queue)
        while queue:
            name = queue.pop()
            for called in self.call_graph.get(name, set()):
                if called in reachable:
                    continue
                reachable.add(called)
                if called not in seen:
                    seen.add(called)
                    queue.append(called)

        inert = sorted(self.new_functions - reachable)
        if not inert:
            return None
        inert_by_file = {
            path: sorted(names & set(inert))
            for path, names in sorted(self.new_functions_by_file.items())
            if names & set(inert)
        }
        guidance = (
            "Solver-design helper functions must be reachable from an existing "
            "module function, baseline_algorithm.py::solve, "
            "or the runtime solver class _ALNSVNSSolver.solve call chain. If a helper "
            "is added in a helper-only module such as local_search.py, include the "
            "scheduler.py or baseline_algorithm.py import/call-site edit in "
            "additional_changes. Do not add a legacy top-level run(...) entrypoint "
            "unless the current target already uses that entrypoint."
        )
        return (
            "new solver_design helper functions are not integrated. "
            f"inert_helpers={inert}; changed_files={self.changed_paths}; "
            f"recognized_roots={sorted(self.root_calls)}; inert_helpers_by_file={inert_by_file}. "
            + guidance
        )
