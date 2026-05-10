"""Default CVRP destroy/repair mechanism policy surface."""
from __future__ import annotations


def destroy_repair_plan(instance, time_limit_sec):
    return {
        "enabled": False,
        "destroy_selectors": ["worst_removal"],
        "repair_selectors": ["regret_2"],
        "subset_strategy": "prefix_shifted_route_diverse",
        "max_destroy_customers": 6,
        "repair_budget_per_customer": 4,
        "fallback_to_smaller_subsets": True,
        "phase_best_preference": True,
    }

