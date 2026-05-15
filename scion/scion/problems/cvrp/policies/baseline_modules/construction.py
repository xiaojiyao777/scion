"""Construction heuristics for the CVRP solver-design subject."""
from __future__ import annotations

import math

from .state import _Route, _Solution, _demand, _node


def _clarke_wright_savings(instance, target_routes=None):
    customers = list(instance.customer_ids)
    routes = [_Route(instance, [customer]) for customer in customers]
    route_of = {customer: idx for idx, customer in enumerate(customers)}
    active_routes = len(routes)
    depot = instance.depot
    savings = []
    for idx, left in enumerate(customers):
        for right in customers[idx + 1 :]:
            saving = (
                instance.distance(depot, left)
                + instance.distance(depot, right)
                - instance.distance(left, right)
            )
            if saving > 0 or target_routes is not None:
                savings.append((saving, left, right))
    savings.sort(reverse=True)

    for _saving, left, right in savings:
        if target_routes is not None and active_routes <= target_routes:
            break
        left_idx = route_of.get(left)
        right_idx = route_of.get(right)
        if left_idx is None or right_idx is None or left_idx == right_idx:
            continue
        left_route = routes[left_idx]
        right_route = routes[right_idx]
        if left_route is None or right_route is None:
            continue
        merged = None
        if left_route.customers[-1] == left and right_route.customers[0] == right:
            merged = left_route.customers + right_route.customers
        elif right_route.customers[-1] == right and left_route.customers[0] == left:
            merged = right_route.customers + left_route.customers
        elif left_route.customers[-1] == left and right_route.customers[-1] == right:
            merged = left_route.customers + list(reversed(right_route.customers))
        elif left_route.customers[0] == left and right_route.customers[0] == right:
            merged = list(reversed(left_route.customers)) + right_route.customers
        if merged is None:
            continue
        if sum(_demand(instance, c) for c in merged) > instance.capacity:
            continue
        new_route = _Route(instance, merged)
        routes[left_idx] = new_route
        routes[right_idx] = None
        active_routes -= 1
        for customer in new_route.customers:
            route_of[customer] = left_idx

    return _Solution(instance, [route for route in routes if route is not None and route.customers])


def _nearest_neighbor(instance):
    unvisited = set(instance.customer_ids)
    routes = []
    depot = instance.depot
    while unvisited:
        route = []
        load = 0
        current = depot
        while True:
            feasible = [
                customer
                for customer in unvisited
                if load + _demand(instance, customer) <= instance.capacity
            ]
            if not feasible:
                break
            next_customer = min(
                feasible,
                key=lambda customer: (instance.distance(current, customer), customer),
            )
            route.append(next_customer)
            load += _demand(instance, next_customer)
            unvisited.remove(next_customer)
            current = next_customer
        if not route:
            break
        routes.append(_Route(instance, route))
    return _Solution(instance, routes)


def _sweep_construction(instance):
    depot_node = _node(instance, instance.depot)
    customers = list(instance.customer_ids)
    customers.sort(
        key=lambda customer: math.atan2(
            _node(instance, customer).y - depot_node.y,
            _node(instance, customer).x - depot_node.x,
        )
    )
    routes = []
    current = []
    load = 0
    for customer in customers:
        demand = _demand(instance, customer)
        if current and load + demand > instance.capacity:
            routes.append(_Route(instance, current))
            current = []
            load = 0
        current.append(customer)
        load += demand
    if current:
        routes.append(_Route(instance, current))
    return _Solution(instance, routes)


def _capacity_balanced_construction(instance, max_routes):
    if max_routes <= 0:
        raise ValueError("max_routes must be positive")
    customers = list(instance.customer_ids)
    total_demand = sum(_demand(instance, c) for c in customers)
    if total_demand > max_routes * instance.capacity:
        raise ValueError("total demand exceeds max_routes * capacity")
    bins = [[] for _ in range(max_routes)]
    loads = [0 for _ in range(max_routes)]
    for customer in sorted(customers, key=lambda c: _demand(instance, c), reverse=True):
        demand = _demand(instance, customer)
        best_idx = -1
        best_remaining = instance.capacity + 1
        for idx in range(max_routes):
            remaining = instance.capacity - loads[idx] - demand
            if 0 <= remaining < best_remaining:
                best_idx = idx
                best_remaining = remaining
        if best_idx < 0:
            raise ValueError(f"unable to pack customer {customer} into {max_routes} routes")
        bins[best_idx].append(customer)
        loads[best_idx] += demand
    routes = []
    depot = instance.depot
    for bucket in bins:
        if not bucket:
            continue
        remaining = set(bucket)
        ordered = []
        current = depot
        while remaining:
            next_customer = min(
                remaining,
                key=lambda customer: (instance.distance(current, customer), customer),
            )
            remaining.remove(next_customer)
            ordered.append(next_customer)
            current = next_customer
        routes.append(_Route(instance, ordered))
    return _Solution(instance, routes)
