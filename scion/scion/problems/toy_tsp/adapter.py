"""ToyTspAdapter — ProblemAdapter implementation for toy TSP MWE."""
from __future__ import annotations

import os
import random
from typing import Any, Mapping, Sequence

from scion.problem.contracts import CheckReport, LowerBoundEstimate, SolverArtifact
from scion.problem.objectives import ObjectiveComparison, compare_lexicographic
from scion.problem.spec import ProblemSpecV1
from scion.problems.toy_tsp.models import TspInstance, TspSolution
from scion.problems.toy_tsp import oracle


class ToyTspAdapter:
    def __init__(self, spec: ProblemSpecV1) -> None:
        self._spec = spec

    @property
    def spec(self) -> ProblemSpecV1:
        return self._spec

    def render_problem_summary(self) -> str:
        return (
            "Toy TSP: find the shortest Hamiltonian cycle through N cities "
            "on a 2D Euclidean plane. Objective: minimize tour_cost."
        )

    def render_operator_interface(self) -> str:
        return (
            "class Operator:\n"
            "    def execute(self, solution: TspSolution, instance: TspInstance, "
            "rng: random.Random) -> TspSolution"
        )

    def load_instance(self, instance_path: str) -> Any:
        return TspInstance.from_json(instance_path)

    def deserialize_solver_output(
        self,
        raw_output: Mapping[str, Any],
        instance: Any,
    ) -> SolverArtifact:
        tour = tuple(raw_output["tour"])
        cost = oracle.compute_tour_cost(tour, instance)
        sol = TspSolution(tour=tour, cost=cost)
        feasible, _ = oracle.check_feasibility(sol, instance)
        return SolverArtifact(
            raw_output=dict(raw_output),
            objective={"tour_cost": cost},
            feasible=feasible,
            normalized_solution=sol,
        )

    def check_solution_consistency(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        sol: TspSolution = artifact.normalized_solution
        if sol is None:
            return CheckReport(passed=False, reasons=("no normalized_solution",))
        recalc = oracle.compute_tour_cost(sol.tour, instance)
        if abs(recalc - artifact.objective["tour_cost"]) > 1e-6:
            return CheckReport(
                passed=False,
                reasons=(f"objective mismatch: stored={artifact.objective['tour_cost']}, recomputed={recalc}",),
            )
        return CheckReport(passed=True)

    def check_feasibility(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        sol: TspSolution = artifact.normalized_solution
        if sol is None:
            return CheckReport(passed=False, reasons=("no normalized_solution",))
        ok, reasons = oracle.check_feasibility(sol, instance)
        return CheckReport(passed=ok, reasons=tuple(reasons))

    def recompute_objective(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> Mapping[str, int | float]:
        return oracle.recompute_objective(artifact.normalized_solution, instance)

    def estimate_lower_bound(
        self,
        metric_name: str,
        instance_paths: Sequence[str],
    ) -> LowerBoundEstimate | None:
        return None
