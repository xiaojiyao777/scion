"""Solution coercion and objective helpers for CVRP runtime."""
from __future__ import annotations

from typing import Any, Mapping

from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.models import CvrpInstance, CvrpSolution
from scion.problems.cvrp.solver_runtime.constants import _OBJECTIVE_TOLERANCE


def _coerce_solution(candidate: Any) -> CvrpSolution | None:
    """Accept canonical or structurally equivalent CvrpSolution objects.

    Generated operators commonly import ``CvrpSolution`` from workspace-local
    ``models.py`` while the solver imports the package model. Those are distinct
    class objects in Python, but the solution contract is structural: a routes
    tuple of customer-id sequences. Coercing here preserves the adapter boundary
    while still rejecting genuinely invalid outputs fail-closed.
    """

    if isinstance(candidate, CvrpSolution):
        return candidate
    if isinstance(candidate, Mapping):
        routes = candidate.get("routes")
        if routes is None:
            return None
        try:
            return CvrpSolution(
                routes=tuple(
                    tuple(int(customer) for customer in route) for route in routes
                )
            )
        except (TypeError, ValueError):
            return None
    routes = getattr(candidate, "routes", None)
    if routes is None:
        return None
    try:
        normalized = tuple(
            tuple(int(customer) for customer in route)
            for route in routes
        )
    except (TypeError, ValueError):
        return None
    return CvrpSolution(routes=normalized)


def _solution_is_valid(
    adapter: CvrpAdapter,
    instance: CvrpInstance,
    solution: CvrpSolution,
) -> tuple[bool, str]:
    raw = {"routes": [list(route) for route in solution.routes], "feasible": True}
    try:
        artifact = adapter.deserialize_solver_output(raw, instance)
        raw["objective"] = dict(adapter.recompute_objective(artifact, instance))
        artifact = adapter.deserialize_solver_output(raw, instance)
        consistency = adapter.check_solution_consistency(artifact, instance)
        if not consistency.passed:
            return False, "; ".join(consistency.reasons[:3])
        feasibility = adapter.check_feasibility(artifact, instance)
        if not feasibility.passed:
            return False, "; ".join(feasibility.reasons[:3])
    except Exception as exc:
        return False, str(exc)
    return True, ""


def _objective_for_solution(
    adapter: CvrpAdapter,
    instance: CvrpInstance,
    solution: CvrpSolution,
) -> dict[str, int | float]:
    raw = {"routes": [list(route) for route in solution.routes], "feasible": True}
    artifact = adapter.deserialize_solver_output(raw, instance)
    return dict(adapter.recompute_objective(artifact, instance))


def _lexicographic_improves(
    candidate: Mapping[str, int | float],
    current: Mapping[str, int | float],
) -> bool:
    candidate_fleet = float(candidate.get("fleet_violation", 0))
    current_fleet = float(current.get("fleet_violation", 0))
    if candidate_fleet < current_fleet:
        return True
    if candidate_fleet > current_fleet:
        return False
    candidate_distance = float(candidate.get("total_distance", 0.0))
    current_distance = float(current.get("total_distance", 0.0))
    return candidate_distance < current_distance - _OBJECTIVE_TOLERANCE


def _objective_distance_delta(
    before: Mapping[str, int | float],
    after: Mapping[str, int | float],
) -> float:
    if float(after.get("fleet_violation", 0)) != float(before.get("fleet_violation", 0)):
        return float(before.get("fleet_violation", 0)) - float(
            after.get("fleet_violation", 0)
        )
    return float(before.get("total_distance", 0.0)) - float(
        after.get("total_distance", 0.0)
    )
