"""Toy TSP 2-opt operator — for Scion operator pool validation."""
from __future__ import annotations

import random

from scion.problems.toy_tsp.models import TspInstance, TspSolution
from scion.problems.toy_tsp.oracle import compute_tour_cost


class TwoOptOperator:
    name = "two_opt"
    category = "local_search"

    def execute(self, solution: TspSolution, instance: TspInstance, rng: random.Random) -> TspSolution:
        tour = list(solution.tour)
        n = len(tour)
        if n < 4:
            return solution
        i = rng.randint(0, n - 2)
        j = rng.randint(i + 2, n - 1) if i + 2 <= n - 1 else i + 2
        if j >= n:
            return solution
        tour[i + 1:j + 1] = tour[i + 1:j + 1][::-1]
        new_tour = tuple(tour)
        cost = compute_tour_cost(new_tour, instance)
        return TspSolution(tour=new_tour, cost=cost)
