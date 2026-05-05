"""CVRP ProblemAdapter implementation for Scion v0.4."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from scion.problem.contracts import CheckReport, LowerBoundEstimate, SolverArtifact
from scion.problem.spec import ProblemSpecV1
from scion.problems.cvrp.cvrplib import load_cvrplib_instance
from scion.problems.cvrp.models import CvrpInstance, CvrpSolution


class CvrpAdapter:
    def __init__(self, spec: ProblemSpecV1) -> None:
        self._spec = spec

    @property
    def spec(self) -> ProblemSpecV1:
        return self._spec

    def render_problem_summary(self) -> str:
        return (
            "Capacitated Vehicle Routing Problem: build ordered vehicle routes "
            "from a depot to visit each customer exactly once while respecting "
            "vehicle capacity. Promotion objective is lexicographic: minimize "
            "fleet_violation first, then total_distance."
        )

    def render_solver_mechanics(self) -> str:
        return (
            "The CVRP campaign solver first builds a baseline solution. For real "
            "CVRPLIB .vrp cases, it uses the repo-local vrp/src ALNS+VNS baseline "
            "when SCION_PROBLEM_DATA_ROOT or SCION_CVRP_DATA_ROOT points at the vrp directory; JSON and "
            "synthetic smoke fixtures use a deterministic nearest-neighbor fallback.\n"
            "- The `search_policy` research surface may tune the baseline time "
            "fraction, post-baseline operator round limit, and whether "
            "post-baseline operators run at all.\n"
            "- Operator research surfaces are applied after the baseline in a "
            "bounded improvement loop, up to the policy-controlled round limit "
            "or until the solver time budget is exhausted.\n"
            "- In each operator round, loaded operators are tried in registry "
            "weight order. A returned solution is accepted only if it is feasible "
            "and strictly improves the lexicographic objective.\n"
            "- Not-improving operator outputs are safe no-ops. Exceptions, "
            "infeasible outputs, malformed outputs, invalid solution structures, "
            "and invalid policy returns are runtime audit failures and cannot be "
            "treated as objective ties.\n"
            "- BKS/gap is not used for operator acceptance. Route-count "
            "comparability enters only through fleet_violation when an explicit "
            "allowed route count or reference route count is available."
        )

    def render_research_surface_interface(self, surface_name: str) -> str:
        if surface_name == "search_policy":
            return (
                "policies/search_policy.py is a module-level policy file; no class "
                "is required.\n\n"
                "Required functions:\n"
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return a numeric fraction in [0.2, 0.95]\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return an int in [0, 20]\n\n"
                "def enable_post_baseline_operators(instance, time_limit_sec):\n"
                "    return a bool\n\n"
                "The solver clamps out-of-range numeric values but records them as "
                "policy_errors. Exceptions, missing functions, non-numeric budget "
                "values, and non-bool enable flags are runtime audit failures. "
                "Policy functions must be deterministic and must not read solver "
                "outputs, benchmark answers, or external files."
            )
        return self.render_operator_interface()

    def render_operator_interface(self) -> str:
        return (
            "class CvrpOperator:\n"
            "    def execute(self, solution: CvrpSolution, instance: CvrpInstance, "
            "rng: random.Random) -> CvrpSolution\n\n"
            "Routes use implicit depot format: each route lists customer ids only. "
            "Operators must preserve visit-once and capacity feasibility, and must "
            "use bounded route-local or route-pair neighborhoods.\n\n"
            "CvrpSolution API: solution.routes is a tuple[tuple[int, ...], ...]. "
            "Return CvrpSolution(routes=tuple_of_routes); do not mutate the input "
            "solution in place. Prefer solution.__class__(routes=...) when creating "
            "a new solution; workspace-local models.CvrpSolution is accepted only "
            "when it has the same routes structure.\n\n"
            "CvrpInstance API: instance.capacity, instance.depot, "
            "instance.customer_ids, instance.node_ids, instance.demand(customer_id), "
            "instance.distance(i, j), instance.route_load(route), and "
            "instance.route_distance(route). Do not use nonexistent attributes such "
            "as vehicle_capacity, demands, distance_matrix, customers, or "
            "num_customers."
        )

    def load_instance(self, instance_path: str) -> Any:
        suffix = Path(instance_path).suffix.lower()
        if suffix == ".json":
            return CvrpInstance.from_json(instance_path)
        if suffix == ".vrp":
            return load_cvrplib_instance(instance_path)
        raise ValueError(f"unsupported CVRP instance file extension: {suffix or '<none>'}")

    def deserialize_solver_output(
        self,
        raw_output: Mapping[str, Any],
        instance: Any,
    ) -> SolverArtifact:
        payload = raw_output.get("solution", raw_output)
        if not isinstance(payload, Mapping):
            raise ValueError("solver output must be a mapping")
        raw_routes = payload.get("routes")
        if not isinstance(raw_routes, list):
            raise ValueError("solver output missing routes list")

        routes = tuple(
            _normalize_route(route, instance.depot)
            for route in raw_routes
        )
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
        self,
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
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        consistency = self.check_solution_consistency(artifact, instance)
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
        self,
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

    def estimate_lower_bound(
        self,
        metric_name: str,
        instance_paths: Sequence[str],
    ) -> LowerBoundEstimate | None:
        return None


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
