"""Default CVRP acceptance/restart mechanism policy surface."""
from __future__ import annotations


def acceptance_restart_plan(instance, time_limit_sec):
    return {
        "enabled": False,
        "min_distance_improvement": 0.0,
        "recovery_only_policy": "allow",
        "restart": {
            "enabled": False,
            "stagnation_rounds": 0,
            "max_restarts": 0,
        },
        "perturbation": {
            "enabled": False,
            "schedule": "after_no_improvement",
            "strength": 1,
            "max_perturbations": 0,
        },
    }

