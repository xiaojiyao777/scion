from __future__ import annotations

import random
from typing import Callable

from ..models import Route, Solution

RepairOperator = Callable[[Solution, list[int], random.Random], None]


def _best_insertions(solution: Solution, customer: int) -> list[tuple[float, int, int]]:
    """Return feasible insertions sorted by delta cost."""
    insertions: list[tuple[float, int, int]] = []
    for ri, route in enumerate(solution.routes):
        if not route.can_insert(customer):
            continue
        for pos in range(len(route) + 1):
            insertions.append((route.cost_of_insert(customer, pos), ri, pos))
    insertions.sort(key=lambda x: x[0])
    return insertions


def _new_route_cost(solution: Solution, customer: int) -> float:
    inst = solution.instance
    depot = inst.depot
    return inst.dist(depot, customer) + inst.dist(customer, depot)


def _insert_existing(solution: Solution, customer: int, route_idx: int, pos: int) -> None:
    route = solution.routes[route_idx]
    before = route.cost
    route.insert(customer, pos)
    solution.total_cost += route.cost - before
    solution._rebuild_index()


def _insert_new_route(solution: Solution, customer: int) -> None:
    route = Route(solution.instance, [customer])
    if route.load > solution.instance.capacity:
        raise ValueError(
            f"Customer {customer} demand {route.load} exceeds vehicle capacity "
            f"{solution.instance.capacity}"
        )
    solution.routes.append(route)
    solution._rebuild_index()


def greedy_insertion(solution: Solution, removed: list[int], rng: random.Random) -> None:
    """Insert the customer with the cheapest feasible insertion each step."""
    pending = list(removed)
    rng.shuffle(pending)

    while pending:
        best_idx = -1
        best_move: tuple[float, int, int] | None = None

        for idx, customer in enumerate(pending):
            insertions = _best_insertions(solution, customer)
            if not insertions:
                continue
            if best_move is None or insertions[0][0] < best_move[0]:
                best_idx = idx
                best_move = insertions[0]

        if best_move is None:
            customer = pending.pop()
            _insert_new_route(solution, customer)
            continue

        customer = pending.pop(best_idx)
        _, route_idx, pos = best_move
        _insert_existing(solution, customer, route_idx, pos)


def regret_insertion(solution: Solution, removed: list[int], rng: random.Random, k: int = 2) -> None:
    """Regret-k insertion. Higher regret customers are inserted first."""
    pending = list(removed)
    rng.shuffle(pending)
    k = max(2, k)

    while pending:
        best_idx = -1
        best_score = float("-inf")
        best_delta = float("inf")
        best_move: tuple[float, int, int] | None = None

        for idx, customer in enumerate(pending):
            insertions = _best_insertions(solution, customer)
            if not insertions:
                score = float("inf")
                delta = _new_route_cost(solution, customer)
                move = None
            else:
                delta = insertions[0][0]
                considered = insertions[:k]
                score = sum(move_delta - delta for move_delta, _, _ in considered[1:])
                if len(considered) < k:
                    score += (k - len(considered)) * max(0.0, _new_route_cost(solution, customer) - delta)
                move = insertions[0]

            if score > best_score or (score == best_score and delta < best_delta):
                best_idx = idx
                best_score = score
                best_delta = delta
                best_move = move

        customer = pending.pop(best_idx)
        if best_move is None:
            _insert_new_route(solution, customer)
        else:
            _, route_idx, pos = best_move
            _insert_existing(solution, customer, route_idx, pos)


def regret2_insertion(solution: Solution, removed: list[int], rng: random.Random) -> None:
    regret_insertion(solution, removed, rng, k=2)


def regret3_insertion(solution: Solution, removed: list[int], rng: random.Random) -> None:
    regret_insertion(solution, removed, rng, k=3)


REPAIR_OPERATORS: list[tuple[str, RepairOperator]] = [
    ("greedy", greedy_insertion),
    ("regret2", regret2_insertion),
    ("regret3", regret3_insertion),
]
