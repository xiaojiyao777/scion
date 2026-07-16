"""Direct CVRP solver-design source and interface guidance."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from scion.problems.cvrp.solver_design.manifest import (
    ACTIVE_SOLVER_DESIGN_PACKAGE,
    BROAD_SCOPE_TERMS,
    SOLVER_DESIGN_API_MANIFEST_FILES,
    SOLVER_DESIGN_INTEGRATION_FULL_FILES,
    SOLVER_DESIGN_INTEGRATION_SUMMARY_FILES,
)


class CvrpSolverDesignProvider:
    """Problem-owned guidance for the direct hypothesis-to-code runtime."""

    def solver_design_broad_scope_terms(self) -> Sequence[str]:
        return BROAD_SCOPE_TERMS

    def solver_design_api_manifest_files(self) -> Sequence[str]:
        return SOLVER_DESIGN_API_MANIFEST_FILES

    def solver_design_integration_full_files(self) -> Sequence[str]:
        return SOLVER_DESIGN_INTEGRATION_FULL_FILES

    def solver_design_integration_summary_files(self) -> Sequence[str]:
        return SOLVER_DESIGN_INTEGRATION_SUMMARY_FILES

    def solver_design_target_api_guidance(self, target_file: str) -> str:
        normalized = str(target_file or "").replace("\\", "/").lstrip("/")
        guidance = {
            "policies/baseline_algorithm.py": (
                "Keep `solve(instance, rng, time_limit_sec, context)` as the "
                "stable entrypoint. It instantiates `_ALNSVNSSolver` and returns "
                "the public solution; algorithm internals belong in the focused "
                "baseline_modules owner."
            ),
            "policies/baseline_modules/construction.py": (
                "Construction helpers return internal `_Solution` objects. "
                "Import an exact new symbol in scheduler.py only when needed to "
                "execute the new construction path."
            ),
            "policies/baseline_modules/destroy_repair.py": (
                "This module owns destroy and repair operators. Scheduler wiring "
                "may import exact symbols defined by the same patch and register "
                "them in the existing destroy or repair collection. Pass the "
                "existing monotonic deadline context and reserve into any "
                "potentially long-running repair; poll remaining_time inside "
                "nested customer, route, position, and recursive searches, and "
                "exit before committing a partial repair when time expires."
            ),
            "policies/baseline_modules/local_search.py": (
                "Integrate local-search moves through `_default_vns_operators()` "
                "or the existing `_vns` call path."
            ),
            "policies/baseline_modules/acceptance.py": (
                "Keep acceptance and adaptive-weight logic in this module. "
                "Scheduler should pass state and consume the decision without "
                "crediting ordinary ALNS improvement to the acceptance policy."
            ),
            "policies/baseline_modules/scheduler.py": (
                "Scheduler owns `_ALNSVNSSolver` orchestration. Put a new "
                "construction, destroy/repair, local-search, or acceptance "
                "mechanism in its owner module and use scheduler only to execute it."
            ),
            "policies/baseline_modules/state.py": (
                "`_Solution` and `_Route` are the internal slotted state model. "
                "Change it only when the hypothesis actually owns a state-model "
                "intervention, never as an adapter for an unrelated mechanism."
            ),
        }
        return guidance.get(normalized, "")

    def solver_design_hypothesis_guidance(self, context: Any) -> Sequence[str]:
        del context
        return (
            (
                "Choose one CVRP-owned causal path from the current algorithm "
                "source and measurement evidence. No prepared file or mechanism "
                "is mandatory."
            ),
            (
                "State the mechanism owner, the generated or selected route-state "
                "change, and the expected causal effect on objective quality or "
                "feasibility."
            ),
            (
                "Use paired and case-level total_distance, feasibility, route "
                "count, confidence interval, and MDE together. Runtime errors "
                "may explain failed outcomes but do not replace objective evidence."
            ),
            (
                "Do not propose generic Scion core, metadata, contract, gate, "
                "helper-only, or telemetry-only work as a solver optimization."
            ),
            (
                "Do not hardcode case ids, reference objectives, seeds, split "
                "membership, Decision rules, or Protocol rules."
            ),
        )

    def active_subject_code_constraints(
        self,
        context: Any = None,
        *,
        surface: str | None = None,
        subject_id: str | None = None,
    ) -> Mapping[str, Any] | None:
        del context, subject_id
        selected = str(surface or "").strip()
        if selected not in {"", "solver_design", "solver_algorithm"}:
            return None
        return {
            "surface": "solver_design",
            "subject_id": "cvrp.solver_design.baseline",
            "version": "cvrp_solver_design_code_constraints.v2",
            "source_interface": (
                {
                    "id": "stable_entrypoint",
                    "constraint": (
                        "Keep policies/baseline_algorithm.py::solve(instance, "
                        "rng, time_limit_sec, context) as the public algorithm entrypoint."
                    ),
                },
                {
                    "id": "owner_module",
                    "constraint": (
                        "Construction, destroy/repair, local-search, acceptance, "
                        "scheduler, and state changes belong in their matching "
                        "policies/baseline_modules owner."
                    ),
                },
                {
                    "id": "source_ledger",
                    "constraint": (
                        "Import only symbols present in the provided source ledger "
                        "and API manifest or defined by the same patch."
                    ),
                },
            ),
            "object_model_hints": (
                {
                    "id": "objective_value_mapping",
                    "constraint": (
                        "`context.objective(solution)` is mapping-like. Use "
                        "`context.objective_key(solution)` for ordering and "
                        "`context.is_better(candidate, incumbent)` for comparisons."
                    ),
                },
                {
                    "id": "internal_solution_route_model",
                    "constraint": (
                        "`_Solution.routes` contains `_Route` objects. `_Route` "
                        "owns customers/load/cost and insert/remove/recalculate; "
                        "`_Solution` owns copy/rebuild_index/remove_empty_routes/"
                        "is_feasible/routes_as_tuples."
                    ),
                },
                {
                    "id": "slotted_state_objects",
                    "constraint": (
                        "`_Solution` and `_Route` are slotted; keep temporary "
                        "search state in local variables or explicit parameters."
                    ),
                },
            ),
            "api_contracts": (
                {
                    "id": "public_internal_solution_bridge",
                    "constraint": (
                        "`context.nearest_neighbor()` takes no arguments and "
                        "returns public `CvrpSolution`. Return internal state with "
                        "`context.make_solution(solution.routes_as_tuples())`."
                    ),
                },
                {
                    "id": "solver_time_limit",
                    "constraint": (
                        "Long-running search must obey the solver-provided time "
                        "limit through the available monotonic remaining-time API."
                    ),
                },
            ),
            "forbidden_patterns": (
                "ObjectiveValue arithmetic",
                "dynamic attributes on slotted `_Solution` or `_Route` objects",
                "invented public/internal bridge methods",
                "case ids, reference objectives, seeds, or split membership in solver code",
            ),
        }

    def solver_design_code_rules(self, context: Any) -> Sequence[str]:
        del context
        return (
            (
                f"The research object is {ACTIVE_SOLVER_DESIGN_PACKAGE}; keep "
                "the stable solve entrypoint and make the selected owner module "
                "contain the algorithmic intervention."
            ),
            (
                "Use the full current target source and the API/source ledger as "
                "authority. Multi-file changes are allowed when each file is "
                "needed for the same executable causal path."
            ),
            (
                "Keep `_Solution` and `_Route` semantics intact unless the "
                "hypothesis explicitly changes the state model. They are slotted "
                "objects, not nested customer lists."
            ),
            (
                "Obey the solver-provided time limit through the available "
                "monotonic remaining-time API."
            ),
            (
                "Do not edit objective semantics, feasibility constraints, "
                "problem parsing, seeds, formal splits, generic Scion core, "
                "Protocol, or DecisionFeatures."
            ),
        )

    def solver_design_scope_guidance(
        self,
        context: Any,
        *,
        mode: str,
        broad_terms: Sequence[str],
    ) -> Sequence[str]:
        del context, mode
        lines = [
            (
                "Implement the complete causal path needed by the hypothesis. "
                "Choose the module boundary from algorithm ownership and keep "
                "scheduler/entrypoint edits as execution wiring."
            ),
            (
                "Do not substitute framework, metadata, telemetry-only, or "
                "configuration-only work for an algorithmic intervention."
            ),
            (
                "Use the current source ledger and object-model API. Do not "
                "invent sibling exports, bridge methods, or detached entrypoints."
            ),
        ]
        if broad_terms:
            lines.append(
                "The hypothesis names several algorithm families "
                f"({', '.join(dict.fromkeys(broad_terms))}); ensure they form "
                "one coherent executable causal path with attributable evidence."
            )
        return tuple(lines)

    def solver_design_user_constraints(self, context: Any) -> Sequence[str]:
        del context
        return (
            (
                "Keep the top-level file_path on the hypothesis owner. Put only "
                "necessary same-mechanism integration in additional_changes."
            ),
            (
                "Inside the policies package, use relative imports and exact "
                "exports visible in the provided source ledger."
            ),
            (
                "`context.nearest_neighbor()` takes no arguments. Internal "
                "`_Solution` is separate from public `CvrpSolution`."
            ),
            (
                "Do not attach dynamic private attributes to `_Solution` or "
                "`_Route`; use local state or explicit parameters."
            ),
            "`additional_changes` must be a JSON array of change objects.",
            (
                "Do not use instance names, case ids, reference objective values, "
                "seeds, or split membership in solver logic."
            ),
        )
