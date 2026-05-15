"""ALNS destroy and repair operators for the CVRP solver-design subject."""
from __future__ import annotations

import math

from .state import _Route, _demand, _distance_scale


def _random_removal(solution, q, rng):
    customers = _customers_in_solution(solution)
    if not customers:
        return []
    q = min(max(1, q), len(customers))
    removed = rng.sample(customers, q)
    for customer in removed:
        _remove_customer(solution, customer)
    return removed


def _worst_removal(solution, q, rng, p=3.0):
    removed = []
    q = max(0, min(q, len(_customers_in_solution(solution))))
    while len(removed) < q:
        candidates = []
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


def _shaw_removal(solution, q, rng, p=6.0, phi_dist=9.0, phi_demand=3.0, phi_route=2.0):
    customers = _customers_in_solution(solution)
    if not customers:
        return []
    q = min(max(1, q), len(customers))
    max_distance = _distance_scale(solution.instance)
    max_demand = max(float(max(_demand(solution.instance, c) for c in customers)), 1.0)
    original_route = {
        customer: idx
        for idx, route in enumerate(solution.routes)
        for customer in route.customers
    }
    seed = rng.choice(customers)
    removed = [seed]
    _remove_customer(solution, seed)
    while len(removed) < q:
        candidates = _customers_in_solution(solution)
        if not candidates:
            break
        related = []
        for customer in candidates:
            best = float("inf")
            for ref in removed:
                same_route = original_route.get(customer) == original_route.get(ref)
                score = (
                    phi_dist * (solution.instance.distance(customer, ref) / max_distance)
                    + phi_demand
                    * (abs(_demand(solution.instance, customer) - _demand(solution.instance, ref)) / max_demand)
                    + (0.0 if same_route else phi_route)
                )
                best = min(best, score)
            related.append((best, customer))
        related.sort(key=lambda item: item[0])
        idx = min(len(related) - 1, int(math.floor((rng.random() ** p) * len(related))))
        customer = related[idx][1]
        if _remove_customer(solution, customer):
            removed.append(customer)
    return removed


def _route_removal(solution, q, rng):
    route_indexes = [idx for idx, route in enumerate(solution.routes) if route.customers]
    if not route_indexes:
        return []
    q = min(max(1, q), len(_customers_in_solution(solution)))
    rng.shuffle(route_indexes)
    removed = []
    for route_idx in route_indexes:
        if route_idx >= len(solution.routes):
            continue
        route = solution.routes[route_idx]
        if not route.customers:
            continue
        removed.extend(route.customers)
        route.customers = []
        route.recalculate()
        if len(removed) >= q:
            break
    solution.remove_empty_routes()
    return removed


def _greedy_insertion(solution, removed, rng):
    pending = list(removed)
    rng.shuffle(pending)
    while pending:
        best_idx = -1
        best_move = None
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
        _delta, route_idx, pos = best_move
        _insert_existing(solution, customer, route_idx, pos)


def _regret2_insertion(solution, removed, rng):
    _regret_insertion(solution, removed, rng, 2)


def _regret3_insertion(solution, removed, rng):
    _regret_insertion(solution, removed, rng, 3)


def _regret_insertion(solution, removed, rng, k):
    pending = list(removed)
    rng.shuffle(pending)
    k = max(2, int(k))
    while pending:
        best_idx = -1
        best_score = float("-inf")
        best_delta = float("inf")
        best_move = None
        for idx, customer in enumerate(pending):
            insertions = _best_insertions(solution, customer)
            if not insertions:
                score = float("inf")
                delta = _new_route_cost(solution, customer)
                move = None
            else:
                delta = insertions[0][0]
                considered = insertions[:k]
                score = sum(move_delta - delta for move_delta, _route_idx, _pos in considered[1:])
                if len(considered) < k:
                    score += (k - len(considered)) * max(
                        0.0,
                        _new_route_cost(solution, customer) - delta,
                    )
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
            _delta, route_idx, pos = best_move
            _insert_existing(solution, customer, route_idx, pos)


def _best_insertions(solution, customer):
    insertions = []
    for route_idx, route in enumerate(solution.routes):
        if not route.can_insert(customer):
            continue
        for pos in range(len(route.customers) + 1):
            insertions.append((route.cost_of_insert(customer, pos), route_idx, pos))
    insertions.sort(key=lambda item: item[0])
    return insertions


def _insert_existing(solution, customer, route_idx, pos):
    solution.routes[route_idx].insert(customer, pos)
    solution.rebuild_index()


def _insert_new_route(solution, customer):
    route = _Route(solution.instance, [customer])
    if route.load > solution.instance.capacity:
        raise ValueError(f"customer {customer} demand exceeds capacity")
    solution.routes.append(route)
    solution.rebuild_index()


def _new_route_cost(solution, customer):
    depot = solution.instance.depot
    return solution.instance.distance(depot, customer) + solution.instance.distance(customer, depot)


def _customers_in_solution(solution):
    return [customer for route in solution.routes for customer in route.customers]


def _remove_customer(solution, customer):
    route_idx = solution.customer_route(customer)
    if route_idx < 0:
        return False
    pos = solution.customer_pos(customer)
    route = solution.routes[route_idx]
    route.remove(pos)
    solution.remove_empty_routes()
    return True
