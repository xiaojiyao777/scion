"""Default CVRP construction policy surface."""
from __future__ import annotations


def construction_mode(instance, time_limit_sec):
    return "nearest_neighbor"


def construction_bias(instance, time_limit_sec):
    return 0.0
