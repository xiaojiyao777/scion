"""Construction heuristics for the CVRP solver-design subject."""
from __future__ import annotations

import math
import time

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


class _PackingRepairBudget:
    """A shared bound for all recovery work in one construction call."""

    def __init__(self, remaining_time, max_work=1_000_000, seconds=2.0):
        self.remaining_time = remaining_time
        self.work_left = max_work
        self.deadline = time.monotonic() + seconds

    def tick(self):
        if self.work_left <= 0:
            raise ValueError("capacity packing repair work limit exhausted")
        self.work_left -= 1
        if time.monotonic() >= self.deadline or (
            self.remaining_time is not None and self.remaining_time() <= 0
        ):
            raise TimeoutError("capacity packing repair time limit exhausted")


def _repair_capacity_packing(bins, loads, customer, demands, capacity, budget):
    """Repack progressively more bins to recover fragmented spare capacity.

    Start with the least-loaded bins. Within each attempted group, sparse
    subset sum fills one bin at a time to its greatest reachable load. This
    is a bounded heuristic, not a proof of global infeasibility on failure.
    No recursion or allocation indexed by numeric capacity is needed.
    """
    indices = sorted(range(len(bins)), key=lambda idx: (loads[idx], idx))
    items = [customer]
    total = demands[customer]
    for width, idx in enumerate(indices, 1):
        budget.tick()
        items.extend(bins[idx])
        total += loads[idx]
        if total > width * capacity:
            continue
        remaining = list(items)
        remaining_load = total
        packed = []
        for _ in range(width):
            if remaining_load <= capacity:
                packed.append(remaining)
                remaining = []
                break
            parents = {0: None}
            target = 0
            for item in remaining:
                if target == capacity:
                    break
                for old_sum in tuple(parents):
                    budget.tick()
                    new_sum = old_sum + demands[item]
                    if new_sum > capacity or new_sum in parents:
                        continue
                    parents[new_sum] = (old_sum, item)
                    target = max(target, new_sum)
                    if target == capacity:
                        break
            selected = set()
            value = target
            while value:
                budget.tick()
                value, item = parents[value]
                selected.add(item)
            if not selected:
                break
            packed.append([item for item in remaining if item in selected])
            remaining = [item for item in remaining if item not in selected]
            remaining_load -= target
        if remaining:
            continue
        # Commit only a complete packing; failed attempts never mutate bins.
        for position, bin_idx in enumerate(indices[:width]):
            bins[bin_idx] = packed[position] if position < len(packed) else []
            loads[bin_idx] = sum(demands[item] for item in bins[bin_idx])
        return
    raise ValueError(
        f"unable to pack customer {customer} into {len(bins)} routes: "
        "bounded subset-sum repair found no packing"
    )


def _capacity_balanced_construction(instance, max_routes, *, remaining_time=None):
    if max_routes <= 0:
        raise ValueError("max_routes must be positive")
    customers = list(instance.customer_ids)
    total_demand = sum(_demand(instance, c) for c in customers)
    if total_demand > max_routes * instance.capacity:
        raise ValueError("total demand exceeds max_routes * capacity")
    bins = [[] for _ in range(max_routes)]
    loads = [0 for _ in range(max_routes)]
    repair_budget = None
    demands = None
    for customer in sorted(customers, key=lambda c: _demand(instance, c), reverse=True):
        if repair_budget is not None:
            repair_budget.tick()
        demand = _demand(instance, customer)
        best_idx = -1
        best_remaining = instance.capacity + 1
        for idx in range(max_routes):
            remaining = instance.capacity - loads[idx] - demand
            if 0 <= remaining < best_remaining:
                best_idx = idx
                best_remaining = remaining
        if best_idx < 0:
            if repair_budget is None:
                repair_budget = _PackingRepairBudget(remaining_time)
                demands = {c: _demand(instance, c) for c in customers}
            _repair_capacity_packing(
                bins, loads, customer, demands, instance.capacity, repair_budget
            )
            continue
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
            if repair_budget is not None:
                repair_budget.tick()
            next_customer = min(
                remaining,
                key=lambda customer: (instance.distance(current, customer), customer),
            )
            remaining.remove(next_customer)
            ordered.append(next_customer)
            current = next_customer
        routes.append(_Route(instance, ordered))
    if repair_budget is not None:
        repair_budget.tick()
    return _Solution(instance, routes)
