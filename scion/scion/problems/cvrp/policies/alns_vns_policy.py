"""Default CVRP ALNS/VNS mechanism policy surface."""
from __future__ import annotations


def alns_vns_plan(instance, time_limit_sec):
    return {
        "enabled": False,
        "components": ["alns", "vns"],
        "component_weights": {
            "alns": 1.0,
            "vns": 1.0,
        },
        "params": {},
    }

