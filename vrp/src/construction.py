from __future__ import annotations

import math

from .models import Instance, Route, Solution


def clarke_wright_savings(instance: Instance, target_routes: int | None = None) -> Solution:
    """Clarke-Wright parallel savings algorithm."""
    depot = instance.depot
    n = instance.num_customers
    customers = list(range(1, n + 1))

    # Compute savings s(i,j) = d(0,i) + d(0,j) - d(i,j)
    savings = []
    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            s = instance.dist(depot, i) + instance.dist(depot, j) - instance.dist(i, j)
            if s > 0 or target_routes is not None:
                savings.append((s, i, j))
    savings.sort(reverse=True)

    # Each customer starts in its own route
    routes: list[Route] = [Route(instance, [c]) for c in customers]
    route_of: dict[int, int] = {c: idx for idx, c in enumerate(customers)}
    active_routes = len(routes)

    # Track endpoints: first and last customer in each route
    def route_idx(c: int) -> int:
        return route_of[c]

    for _, i, j in savings:
        if target_routes is not None and active_routes <= target_routes:
            break
        ri = route_of.get(i)
        rj = route_of.get(j)
        if ri is None or rj is None or ri == rj:
            continue
        route_i = routes[ri]
        route_j = routes[rj]
        if route_i is None or route_j is None:
            continue

        # i must be at the end of route_i and j at the start of route_j, or vice versa
        i_at_end = route_i.customers[-1] == i
        i_at_start = route_i.customers[0] == i
        j_at_start = route_j.customers[0] == j
        j_at_end = route_j.customers[-1] == j

        merged = None
        if i_at_end and j_at_start:
            # route_i -> route_j
            new_load = route_i.load + route_j.load
            if new_load <= instance.capacity:
                merged_customers = route_i.customers + route_j.customers
                merged = Route(instance, merged_customers)
        elif j_at_end and i_at_start:
            # route_j -> route_i
            new_load = route_i.load + route_j.load
            if new_load <= instance.capacity:
                merged_customers = route_j.customers + route_i.customers
                merged = Route(instance, merged_customers)
        elif i_at_end and j_at_end:
            # route_i -> reversed route_j
            new_load = route_i.load + route_j.load
            if new_load <= instance.capacity:
                merged_customers = route_i.customers + list(reversed(route_j.customers))
                merged = Route(instance, merged_customers)
        elif i_at_start and j_at_start:
            # reversed route_i -> route_j
            new_load = route_i.load + route_j.load
            if new_load <= instance.capacity:
                merged_customers = list(reversed(route_i.customers)) + route_j.customers
                merged = Route(instance, merged_customers)

        if merged is not None:
            # Place merged route at ri, nullify rj
            routes[ri] = merged
            routes[rj] = None  # type: ignore
            active_routes -= 1
            for c in merged.customers:
                route_of[c] = ri

    final_routes = [r for r in routes if r is not None and len(r) > 0]
    return Solution(instance, final_routes)


def nearest_neighbor(instance: Instance) -> Solution:
    """Nearest-neighbor construction heuristic."""
    depot = instance.depot
    unvisited = set(range(1, instance.num_customers + 1))
    routes: list[Route] = []

    while unvisited:
        current_route: list[int] = []
        current_load = 0
        current_node = depot

        while True:
            best_c = None
            best_d = float("inf")
            for c in unvisited:
                if current_load + instance.demands[c] > instance.capacity:
                    continue
                d = instance.dist(current_node, c)
                if d < best_d:
                    best_d = d
                    best_c = c
            if best_c is None:
                break
            current_route.append(best_c)
            current_load += int(instance.demands[best_c])
            unvisited.remove(best_c)
            current_node = best_c

        if current_route:
            routes.append(Route(instance, current_route))
        else:
            # Remaining customers are infeasible individually — shouldn't happen
            break

    return Solution(instance, routes)


def sweep_construction(instance: Instance) -> Solution:
    """Scalable sweep construction for large CVRP instances."""
    depot = instance.depot
    depot_x, depot_y = instance.coords[depot]
    customers = [c for c in range(instance.dimension) if c != depot]
    customers.sort(
        key=lambda c: math.atan2(
            instance.coords[c, 1] - depot_y,
            instance.coords[c, 0] - depot_x,
        )
    )

    routes: list[Route] = []
    current: list[int] = []
    current_load = 0

    for customer in customers:
        demand = int(instance.demands[customer])
        if current and current_load + demand > instance.capacity:
            routes.append(Route(instance, current))
            current = []
            current_load = 0
        current.append(customer)
        current_load += demand

    if current:
        routes.append(Route(instance, current))

    return Solution(instance, routes)


def capacity_balanced_construction(instance: Instance, max_routes: int) -> Solution:
    """Build at most max_routes routes using best-fit capacity packing."""
    if max_routes <= 0:
        raise ValueError("max_routes must be positive")

    customers = [c for c in range(instance.dimension) if c != instance.depot]
    total_demand = sum(int(instance.demands[c]) for c in customers)
    if total_demand > max_routes * instance.capacity:
        raise ValueError("Total demand exceeds max_routes * capacity")

    bins: list[list[int]] = [[] for _ in range(max_routes)]
    loads = [0 for _ in range(max_routes)]

    for customer in sorted(customers, key=lambda c: int(instance.demands[c]), reverse=True):
        demand = int(instance.demands[customer])
        best_idx = -1
        best_remaining = instance.capacity + 1
        for idx in range(max_routes):
            remaining = instance.capacity - loads[idx] - demand
            if remaining >= 0 and remaining < best_remaining:
                best_idx = idx
                best_remaining = remaining
        if best_idx < 0:
            raise ValueError(f"Unable to pack customer {customer} into {max_routes} routes")
        bins[best_idx].append(customer)
        loads[best_idx] += demand

    ordered_routes: list[Route] = []
    depot = instance.depot
    for bucket in bins:
        if not bucket:
            continue
        remaining = set(bucket)
        ordered: list[int] = []
        current = depot
        while remaining:
            nxt = min(remaining, key=lambda c: instance.dist(current, c))
            remaining.remove(nxt)
            ordered.append(nxt)
            current = nxt
        ordered_routes.append(Route(instance, ordered))

    return Solution(instance, ordered_routes)
