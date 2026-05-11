"""Default CVRP solver-design execution hook.

This singleton policy is intentionally inactive by default. Candidate proposals
can enable it to let the CVRP package own the complete construction, baseline,
improvement-loop, restart/perturbation, and optional registry-operator schedule
without editing solver.py.

Candidate proposals should treat this as a solver-level lifecycle plan, not a
place to force one component recipe. If enabled, the plan should explain how
construction, baseline budget, package-owned improvement components,
acceptance, restart/perturbation, and caps work together, and which
phase-best objective and whole-solver runtime evidence should move. Deep
components such as route_pair_swap and bounded_destroy_repair remain useful
attribution hooks, but they are implementation details of a broader CVRP
solver hypothesis. The checked-in default remains inactive.
"""
from __future__ import annotations


def main_search_plan(instance, time_limit_sec):
    return {
        "enabled": False,
        "construction": {
            "methods": ["nearest_neighbor"],
            "keep_top_k": 1,
            "bias": 0.0,
        },
        "baseline": {
            "time_fraction": 0.8,
            "params": {},
        },
        "improvement": {
            "enabled_components": [],
            "rounds": 0,
            "top_k": 16,
        },
        "acceptance": {
            "min_distance_improvement": 0.0,
        },
        "restart": {
            "enabled": False,
            "stagnation_rounds": 0,
            "max_restarts": 0,
        },
        "perturbation": {
            "enabled": False,
            "strength": 1,
            "max_perturbations": 0,
            "schedule": "after_no_improvement",
        },
        "post_baseline_operators_enabled": False,
        "operator_round_limit": 0,
    }
