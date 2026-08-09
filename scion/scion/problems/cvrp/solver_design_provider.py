"""Direct CVRP solver-design source and interface guidance."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from scion.problems.cvrp.solver_design.manifest import (
    SOLVER_DESIGN_API_MANIFEST_FILES,
    SOLVER_DESIGN_INTEGRATION_FULL_FILES,
    SOLVER_DESIGN_INTEGRATION_SUMMARY_FILES,
)


class CvrpSolverDesignProvider:
    """Problem-owned guidance for the direct hypothesis-to-code runtime."""

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
                "The `_default_vns_operators()` registry is shared by initial and "
                "embedded VNS. Add a mechanism there only when it is intended for "
                "both phases. For a phase-specific approved hypothesis, keep the "
                "mechanism in its local-search owner and use the smallest complete "
                "scheduler wiring that activates it in the target phase only."
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
                "count, and confidence intervals together. Use MDE only when a "
                "matched calibration exists; R2 has no matched MDE. Runtime "
                "errors may explain failed outcomes but do not replace objective "
                "evidence."
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
