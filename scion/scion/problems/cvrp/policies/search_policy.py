"""Default CVRP search policy surface."""
from __future__ import annotations


def baseline_time_fraction(instance, time_limit_sec):
    return 0.8


def max_operator_rounds(instance, time_limit_sec):
    return 20


def enable_post_baseline_operators(instance, time_limit_sec):
    return True
