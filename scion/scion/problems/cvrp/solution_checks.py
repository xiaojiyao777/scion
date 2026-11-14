"""CVRP adapter-owned solver output and solution validation helpers."""
from __future__ import annotations

import math
from typing import Any, Mapping

from scion.problem.contracts import CheckReport, SolverArtifact
from scion.problems.cvrp.models import CvrpSolution


def deserialize_solver_output(
    raw_output: Mapping[str, Any],
    instance: Any,
) -> SolverArtifact:
    payload = raw_output.get("solution", raw_output)
    if not isinstance(payload, Mapping):
        raise ValueError("solver output must be a mapping")
    raw_routes = payload.get("routes")
    if not isinstance(raw_routes, list):
        raise ValueError("solver output missing routes list")

    routes = tuple(_normalize_route(route, instance.depot) for route in raw_routes)
    solution = CvrpSolution(routes=routes)
    raw_objective = raw_output.get("objective", payload.get("objective", {}))
    if not isinstance(raw_objective, Mapping):
        raw_objective = {}
    objective = _extract_reported_objective(raw_objective)
    feasible = bool(raw_output.get("feasible", payload.get("feasible", False)))
    return SolverArtifact(
        raw_output=dict(raw_output),
        objective=objective,
        feasible=feasible,
        normalized_solution=solution,
    )


def check_solution_consistency(
    artifact: SolverArtifact,
    instance: Any,
) -> CheckReport:
    sol = _as_solution(artifact)
    reasons: list[str] = []
    valid_customers = set(instance.customer_ids)
    valid_nodes = set(instance.node_ids)
    seen: dict[int, int] = {}

    if not sol.routes:
        reasons.append("solution has no routes")

    for route_idx, route in enumerate(sol.routes):
        if not route:
            reasons.append(f"route {route_idx} is empty")
        for customer in route:
            if customer == instance.depot:
                reasons.append(f"route {route_idx} contains depot inside customer route")
                continue
            if customer not in valid_nodes:
                reasons.append(f"route {route_idx} contains unknown customer {customer}")
                continue
            if customer not in valid_customers:
                reasons.append(f"route {route_idx} contains non-customer node {customer}")
                continue
            if customer in seen:
                reasons.append(
                    f"customer {customer} appears in multiple routes: "
                    f"{seen[customer]} and {route_idx}"
                )
            seen[customer] = route_idx

    missing = sorted(valid_customers - set(seen))
    if missing:
        reasons.append(f"missing customers: {missing}")

    for key in ("fleet_violation", "total_distance"):
        value = artifact.objective.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            reasons.append(f"objective field {key} missing or non-finite")

    return CheckReport(passed=not reasons, reasons=tuple(reasons))


def check_feasibility(
    artifact: SolverArtifact,
    instance: Any,
) -> CheckReport:
    consistency = check_solution_consistency(artifact, instance)
    reasons = list(consistency.reasons)
    if consistency.passed:
        sol = _as_solution(artifact)
        for route_idx, route in enumerate(sol.routes):
            load = instance.route_load(route)
            if load > instance.capacity:
                reasons.append(
                    f"route {route_idx} load {load} exceeds capacity {instance.capacity}"
                )
    return CheckReport(passed=not reasons, reasons=tuple(reasons))


def recompute_objective(
    artifact: SolverArtifact,
    instance: Any,
) -> Mapping[str, int | float]:
    sol = _as_solution(artifact)
    total_distance = sum(instance.route_distance(route) for route in sol.routes)
    routes = len(sol.routes)
    allowed_routes = instance.allowed_routes
    if allowed_routes is None:
        allowed_routes = instance.bks_routes
    fleet_violation = max(0, routes - allowed_routes) if allowed_routes is not None else 0
    return {
        "fleet_violation": int(fleet_violation),
        "total_distance": float(total_distance),
        "routes": int(routes),
    }


def _normalize_route(route: Any, depot: int) -> tuple[int, ...]:
    if not isinstance(route, list):
        raise ValueError("each route must be a list")
    customers = [int(item) for item in route]
    if customers and customers[0] == depot:
        customers = customers[1:]
    if customers and customers[-1] == depot:
        customers = customers[:-1]
    return tuple(customers)


def _extract_reported_objective(raw_objective: Mapping[str, Any]) -> dict[str, int | float]:
    result: dict[str, int | float] = {}
    if "cost" in raw_objective and "total_distance" not in raw_objective:
        result["total_distance"] = float(raw_objective["cost"])
    for key in ("fleet_violation", "total_distance", "routes", "route_gap"):
        if key not in raw_objective:
            continue
        value = raw_objective[key]
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            result[key] = value
    return result


def _as_solution(artifact: SolverArtifact) -> CvrpSolution:
    sol = artifact.normalized_solution
    if not isinstance(sol, CvrpSolution):
        raise TypeError("artifact.normalized_solution is not CvrpSolution")
    return sol
