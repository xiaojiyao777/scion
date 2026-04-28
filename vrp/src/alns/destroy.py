from __future__ import annotations

import math
import random
from typing import Callable

import numpy as np

from ..models import Solution

DestroyOperator = Callable[[Solution, int, random.Random], list[int]]

_EPS = 1e-9


def _customers_in_solution(solution: Solution) -> list[int]:
    return [
        c
        for route in solution.routes
        for c in route.customers
    ]


def _cap_q(solution: Solution, q: int) -> int:
    return max(0, min(q, len(_customers_in_solution(solution))))


def _remove_customer(solution: Solution, customer: int) -> bool:
    ri = solution.customer_route(customer)
    if ri < 0:
        return False
    pos = solution.customer_pos(customer)
    route = solution.routes[ri]
    before = route.cost
    route.remove(pos)
    solution.total_cost += route.cost - before
    solution.remove_empty_routes()
    return True


def random_removal(solution: Solution, q: int, rng: random.Random) -> list[int]:
    """Remove q random customers."""
    customers = _customers_in_solution(solution)
    if not customers:
        return []
    q = min(max(1, q), len(customers))
    removed = rng.sample(customers, q)
    for customer in removed:
        _remove_customer(solution, customer)
    return removed


def worst_removal(
    solution: Solution,
    q: int,
    rng: random.Random,
    p: float = 3.0,
) -> list[int]:
    """Remove customers with the largest removal savings, randomized by p."""
    removed: list[int] = []
    q = _cap_q(solution, q)

    while len(removed) < q:
        candidates: list[tuple[float, int]] = []
        for route in solution.routes:
            for pos, customer in enumerate(route.customers):
                saving = -route.cost_of_remove(pos)
                candidates.append((saving, customer))
        if not candidates:
            break

        candidates.sort(reverse=True)
        idx = min(len(candidates) - 1, int(math.floor((rng.random() ** p) * len(candidates))))
        customer = candidates[idx][1]
        if _remove_customer(solution, customer):
            removed.append(customer)

    return removed


def _route_lookup(solution: Solution) -> dict[int, int]:
    lookup: dict[int, int] = {}
    for ri, route in enumerate(solution.routes):
        for customer in route.customers:
            lookup[customer] = ri
    return lookup


def _distance_scale(solution: Solution) -> float:
    inst = solution.instance
    if inst.dist_matrix is not None:
        max_dist = float(np.max(inst.dist_matrix))
        return max(max_dist, 1.0)
    coords = inst.coords
    span = coords.max(axis=0) - coords.min(axis=0)
    return max(float(np.hypot(span[0], span[1])), 1.0)


def shaw_removal(
    solution: Solution,
    q: int,
    rng: random.Random,
    p: float = 6.0,
    phi_dist: float = 9.0,
    phi_demand: float = 3.0,
    phi_route: float = 2.0,
) -> list[int]:
    """Remove related customers using Shaw relatedness."""
    customers = _customers_in_solution(solution)
    if not customers:
        return []

    q = min(max(1, q), len(customers))
    inst = solution.instance
    max_dist = _distance_scale(solution)
    max_demand = max(float(np.max(inst.demands)), 1.0)
    original_route = _route_lookup(solution)

    seed = rng.choice(customers)
    removed = [seed]
    _remove_customer(solution, seed)

    while len(removed) < q:
        candidates = _customers_in_solution(solution)
        if not candidates:
            break

        related: list[tuple[float, int]] = []
        for customer in candidates:
            best = float("inf")
            for ref in removed:
                same_route = original_route.get(customer) == original_route.get(ref)
                score = (
                    phi_dist * (inst.dist(customer, ref) / max_dist)
                    + phi_demand * (abs(int(inst.demands[customer]) - int(inst.demands[ref])) / max_demand)
                    + (0.0 if same_route else phi_route)
                )
                if score < best:
                    best = score
            related.append((best, customer))

        related.sort(key=lambda x: x[0])
        idx = min(len(related) - 1, int(math.floor((rng.random() ** p) * len(related))))
        customer = related[idx][1]
        if _remove_customer(solution, customer):
            removed.append(customer)

    return removed


def route_removal(solution: Solution, q: int, rng: random.Random) -> list[int]:
    """Remove whole routes until at least q customers have been removed."""
    non_empty = [idx for idx, route in enumerate(solution.routes) if len(route) > 0]
    if not non_empty:
        return []

    q = min(max(1, q), len(_customers_in_solution(solution)))
    rng.shuffle(non_empty)

    removed: list[int] = []
    for ri in non_empty:
        if ri >= len(solution.routes):
            continue
        route = solution.routes[ri]
        if len(route) == 0:
            continue
        removed.extend(route.customers)
        solution.total_cost -= route.cost
        route.customers = []
        route.load = 0
        route.cost = 0.0
        if len(removed) >= q:
            break

    solution.remove_empty_routes()
    return removed


DESTROY_OPERATORS: list[tuple[str, DestroyOperator]] = [
    ("random", random_removal),
    ("worst", worst_removal),
    ("shaw", shaw_removal),
    ("route", route_removal),
]
