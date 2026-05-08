"""Default CVRP main-search strategy surface.

This singleton policy is intentionally inactive by default. Candidate proposals
can enable it to let the CVRP package own the complete construction, baseline,
improvement-loop, restart/perturbation, and optional registry-operator schedule
without editing solver.py.
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
        },
        "post_baseline_operators_enabled": False,
        "operator_round_limit": 0,
    }
