"""CVRP problem-object and active solver-design surface rendering."""
from __future__ import annotations

from scion.problems.cvrp.surface_schema import _POLICY_INSTANCE_API_TEXT


def render_problem_summary() -> str:
    return (
        "Capacitated Vehicle Routing Problem: build ordered vehicle routes "
        "from a depot to visit each customer exactly once while respecting "
        "vehicle capacity. Promotion objective is lexicographic: minimize "
        "fleet_violation first, then total_distance. fleet_violation is "
        "max(0, len(routes) - route_limit), where route_limit is "
        "allowed_routes or bks_routes; route capacity overload is infeasible, "
        "not a soft fleet_violation state."
    )


def render_problem_object() -> str:
    return (
        "CVRP problem object for solver-level research.\n\n"
        "Instance model:\n"
        "- One depot and a fixed set of customers with coordinates and integer demands.\n"
        "- Vehicle capacity is a hard route constraint; every non-depot customer "
        "must be served exactly once.\n"
        "- Safe APIs: `instance.customer_ids`, `instance.customer_count`, "
        "`instance.capacity`, `instance.demands[customer_id]`, "
        "`instance.allowed_routes`, `instance.bks_routes`, "
        "`instance.demand(...)`, `instance.distance(i, j)`, "
        "`instance.route_load(route)`, and `instance.route_distance(route)`. "
        "Do not use `instance.customers`.\n\n"
        "Solution model:\n"
        "- `CvrpSolution(routes=...)` uses implicit-depot customer sequences.\n"
        "- A valid solution preserves each customer exactly once, has no depot ids "
        "inside routes, respects capacity on every route, and reports a finite "
        "adapter-recomputed objective.\n\n"
        "Objective policy:\n"
        "- The promotion order is fleet_violation first, then total_distance.\n"
        "- fleet_violation = max(0, len(routes) - route_limit), where "
        "route_limit is instance.allowed_routes or instance.bks_routes.\n"
        "- Capacity overload, duplicate customers, missing customers, and depot "
        "ids inside routes are hard infeasibilities; do not model them as "
        "fleet_violation improvements.\n\n"
        "Runtime evidence for problem-level hypotheses:\n"
        "- Active solver_design candidates must produce solver_algorithm_* "
        "telemetry for load state, errors, solution validity, search effort, "
        "move acceptance, phase timing, and stop reason.\n\n"
        "Research boundary:\n"
        "- The active algorithm package is policies/baseline_algorithm.py plus "
        "policies/baseline_modules/*.py.\n"
        "- The package owns construction, ALNS scheduling, destroy/repair, "
        "adaptive weights, simulated annealing acceptance, VNS/local-search, "
        "state, runtime-budget polling, and telemetry calls.\n"
        "- Legacy operator/component-policy/lifecycle-config surfaces have been "
        "removed from the active research path."
    )


def render_solver_mechanics() -> str:
    return (
        "The CVRP campaign solver is a runtime shell around the active "
        "`solver_design` algorithm package. It loads "
        "`policies/baseline_algorithm.py::solve(instance, rng, time_limit_sec, "
        "context)`, validates the returned solution through the fixed adapter, "
        "and writes solver_algorithm_* telemetry. If the active package fails to "
        "load or returns invalid output, the shell emits a nearest-neighbor "
        "fallback solution with solver_algorithm_errors > 0 so selected-surface "
        "validation fails closed while downstream objective checks can still run.\n"
        "- New optimization work belongs in policies/baseline_algorithm.py or "
        "policies/baseline_modules/*.py.\n"
        "- Deleted legacy hooks, component-policy surfaces, and operators are "
        "not active research context.\n"
        "- The adapter/solver remains the authority for parsing, feasibility, "
        "objective recomputation, runtime limits, seeds, and protocol evaluation."
    )


def render_research_surface_interface(surface_name: str) -> str:
    if surface_name != "solver_design":
        return (
            f"{surface_name} is not an active CVRP research surface. Use "
            "solver_design and target policies/baseline_algorithm.py or "
            "policies/baseline_modules/*.py."
        )
    return (
        "Active CVRP solver_design surface.\n\n"
        "Targets:\n"
        "- policies/baseline_algorithm.py\n"
        "- policies/baseline_modules/*.py\n\n"
        "Declared signature:\n"
        "solve(instance, rng, time_limit_sec, context)\n\n"
        "Return contract:\n"
        "Return CvrpSolution, an object with routes, or {'routes': ...}. Routes "
        "are implicit-depot customer sequences. The adapter recomputes objective "
        "and rejects malformed, infeasible, duplicate/missing-customer, "
        "capacity-violating, or route-count-violating outputs.\n\n"
        "Objective semantics:\n"
        "- fleet_violation = max(0, len(routes) - route_limit), where "
        "route_limit is instance.allowed_routes or instance.bks_routes.\n"
        "- Capacity overload is a hard invalid-output condition, not "
        "fleet_violation evidence.\n\n"
        "Context helpers:\n"
        "- context.make_solution(routes)\n"
        "- context.nearest_neighbor()\n"
        "- context.objective(solution), context.objective_key(solution), "
        "context.is_better(candidate, incumbent), context.is_valid(solution)\n"
        "- context.remaining_time(), context.remaining_time_ms(), context.elapsed_ms()\n"
        "- context.record_phase(name, elapsed_ms)\n"
        "- context.record_iteration(phase='search', count=1)\n"
        "- context.record_move(phase='search', attempted=1, accepted=0, "
        "delta=None, best_improved=0)\n"
        "- context.set_stop_reason(reason)\n"
        "Do not pass arbitrary keyword arguments such as extra=... to these "
        "helpers.\n\n"
        + _POLICY_INSTANCE_API_TEXT
    )


def render_operator_interface() -> str:
    return (
        "There is no active CVRP operator interface. Routes still use "
        "implicit depot customer sequences, but the former operators/*.py "
        "surface has been removed. Use solver_design and edit the active "
        "algorithm package instead."
    )
