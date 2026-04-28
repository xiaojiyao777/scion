"""Toy TSP solver — nearest-neighbor + 2-opt."""
from __future__ import annotations

import random

from scion.problems.toy_tsp.models import TspInstance, TspSolution
from scion.problems.toy_tsp.oracle import compute_tour_cost


def nearest_neighbor(instance: TspInstance, rng: random.Random) -> tuple[int, ...]:
    start = rng.randint(0, instance.n - 1)
    visited = {start}
    tour = [start]
    for _ in range(instance.n - 1):
        cur = tour[-1]
        best, best_d = -1, float("inf")
        for j in range(instance.n):
            if j not in visited:
                d = instance.distance(cur, j)
                if d < best_d:
                    best, best_d = j, d
        tour.append(best)
        visited.add(best)
    return tuple(tour)


def two_opt_improve(tour: tuple[int, ...], instance: TspInstance, max_iter: int = 100) -> tuple[int, ...]:
    best = list(tour)
    n = len(best)
    improved = True
    iters = 0
    while improved and iters < max_iter:
        improved = False
        iters += 1
        for i in range(n - 1):
            for j in range(i + 2, n):
                if j == n - 1 and i == 0:
                    continue
                d_old = instance.distance(best[i], best[i + 1]) + instance.distance(best[j], best[(j + 1) % n])
                d_new = instance.distance(best[i], best[j]) + instance.distance(best[i + 1], best[(j + 1) % n])
                if d_new < d_old - 1e-10:
                    best[i + 1:j + 1] = best[i + 1:j + 1][::-1]
                    improved = True
    return tuple(best)


def solve(instance: TspInstance, rng: random.Random) -> TspSolution:
    tour = nearest_neighbor(instance, rng)
    tour = two_opt_improve(tour, instance)
    cost = compute_tour_cost(tour, instance)
    return TspSolution(tour=tour, cost=cost)
