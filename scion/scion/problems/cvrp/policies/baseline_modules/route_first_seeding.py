"""Route-first construction seeds for the CVRP comparison variant."""
from __future__ import annotations

import math

from .construction import (
    _capacity_balanced_construction,
    _clarke_wright_savings,
    _nearest_neighbor,
)
from .state import _Route, _Solution, _demand, _node


def route_first_seed_candidates(instance, *, max_routes, max_starts):
    """Yield feasible-start attempts for the route-first comparison solver."""

    yield _clarke_wright_savings(instance, target_routes=max_routes)
    for order in _rotated_polar_orders(instance, max_starts):
        yield _capacity_split(instance, order)
    if max_routes is not None:
        try:
            yield _capacity_balanced_construction(instance, max_routes)
        except ValueError:
            pass
    yield _nearest_neighbor(instance)


def _rotated_polar_orders(instance, max_starts):
    order = _polar_order(instance)
    if not order:
        return
    starts = min(max(1, int(max_starts)), len(order))
    offsets = sorted({(idx * len(order)) // starts for idx in range(starts)})
    for offset in offsets:
        yield order[offset:] + order[:offset]


def _polar_order(instance):
    depot = _node(instance, instance.depot)
    customers = list(instance.customer_ids)
    if depot is None:
        return customers
    customers.sort(
        key=lambda customer: (
            math.atan2(
                _node(instance, customer).y - depot.y,
                _node(instance, customer).x - depot.x,
            ),
            math.hypot(
                _node(instance, customer).x - depot.x,
                _node(instance, customer).y - depot.y,
            ),
            customer,
        )
    )
    return customers


def _capacity_split(instance, ordered_customers):
    routes = []
    current = []
    load = 0
    for customer in ordered_customers:
        demand = _demand(instance, customer)
        if demand > instance.capacity:
            raise ValueError(f"customer {customer} demand exceeds capacity")
        if current and load + demand > instance.capacity:
            routes.append(_Route(instance, current))
            current = []
            load = 0
        current.append(customer)
        load += demand
    if current:
        routes.append(_Route(instance, current))
    return _Solution(instance, routes)
