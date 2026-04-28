"""Toy TSP oracle — tour validity and distance computation."""
from __future__ import annotations

from typing import Mapping

from scion.problems.toy_tsp.models import TspInstance, TspSolution


def check_feasibility(solution: TspSolution, instance: TspInstance) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    tour = solution.tour

    if len(tour) != instance.n:
        reasons.append(f"tour length {len(tour)} != {instance.n}")

    if set(tour) != set(range(instance.n)):
        reasons.append("tour does not visit all cities exactly once")

    return (len(reasons) == 0, reasons)


def compute_tour_cost(tour: tuple[int, ...], instance: TspInstance) -> float:
    total = 0.0
    for i in range(len(tour)):
        total += instance.distance(tour[i], tour[(i + 1) % len(tour)])
    return total


def recompute_objective(solution: TspSolution, instance: TspInstance) -> Mapping[str, float]:
    cost = compute_tour_cost(solution.tour, instance)
    return {"tour_cost": cost}
