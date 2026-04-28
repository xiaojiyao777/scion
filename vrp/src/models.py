from __future__ import annotations

import math
from typing import Optional

import numpy as np


class Instance:
    """Parsed CVRP instance."""

    __slots__ = (
        "name",
        "dimension",
        "capacity",
        "depot",
        "coords",
        "demands",
        "dist_matrix",
        "use_integer_cost",
    )

    def __init__(
        self,
        name: str,
        dimension: int,
        capacity: int,
        coords: np.ndarray,
        demands: np.ndarray,
        dist_matrix: Optional[np.ndarray] = None,
        use_integer_cost: bool = True,
        depot: int = 0,
    ):
        self.name = name
        self.dimension = dimension
        self.capacity = capacity
        self.depot = depot
        self.coords = coords
        self.demands = demands
        self.dist_matrix = dist_matrix
        self.use_integer_cost = use_integer_cost

    @property
    def num_customers(self) -> int:
        return self.dimension - 1

    def dist(self, i: int, j: int) -> float:
        if self.dist_matrix is not None:
            return self.dist_matrix[i, j]
        dx = self.coords[i, 0] - self.coords[j, 0]
        dy = self.coords[i, 1] - self.coords[j, 1]
        d = math.sqrt(dx * dx + dy * dy)
        return math.floor(d + 0.5) if self.use_integer_cost else d


class Route:
    """A single vehicle route: depot -> customers -> depot."""

    __slots__ = ("customers", "load", "cost", "_inst")

    def __init__(self, inst: Instance, customers: Optional[list[int]] = None):
        self._inst = inst
        self.customers: list[int] = list(customers) if customers else []
        self.load: int = 0
        self.cost: float = 0.0
        if self.customers:
            self._recalculate()

    def _recalculate(self) -> None:
        inst = self._inst
        self.load = sum(int(inst.demands[c]) for c in self.customers)
        depot = inst.depot
        cost = 0.0
        prev = depot
        for c in self.customers:
            cost += inst.dist(prev, c)
            prev = c
        cost += inst.dist(prev, depot)
        self.cost = cost

    def cost_of_insert(self, customer: int, position: int) -> float:
        """Delta cost of inserting customer at the given position."""
        inst = self._inst
        depot = inst.depot
        prev = depot if position == 0 else self.customers[position - 1]
        nxt = depot if position == len(self.customers) else self.customers[position]
        return inst.dist(prev, customer) + inst.dist(customer, nxt) - inst.dist(prev, nxt)

    def cost_of_remove(self, position: int) -> float:
        """Delta cost of removing customer at position (negative = savings)."""
        inst = self._inst
        depot = inst.depot
        c = self.customers[position]
        prev = depot if position == 0 else self.customers[position - 1]
        nxt = depot if position == len(self.customers) - 1 else self.customers[position + 1]
        return inst.dist(prev, nxt) - inst.dist(prev, c) - inst.dist(c, nxt)

    def insert(self, customer: int, position: int) -> None:
        delta = self.cost_of_insert(customer, position)
        self.customers.insert(position, customer)
        self.cost += delta
        self.load += int(self._inst.demands[customer])

    def remove(self, position: int) -> int:
        delta = self.cost_of_remove(position)
        customer = self.customers.pop(position)
        self.cost += delta
        self.load -= int(self._inst.demands[customer])
        return customer

    def can_insert(self, customer: int) -> bool:
        return self.load + int(self._inst.demands[customer]) <= self._inst.capacity

    def __len__(self) -> int:
        return len(self.customers)

    def __getitem__(self, idx: int) -> int:
        return self.customers[idx]

    def copy(self) -> Route:
        r = Route.__new__(Route)
        r._inst = self._inst
        r.customers = list(self.customers)
        r.load = self.load
        r.cost = self.cost
        return r


class Solution:
    """Complete CVRP solution: set of routes covering all customers."""

    __slots__ = ("instance", "routes", "total_cost", "_cust_route", "_cust_pos")

    def __init__(self, instance: Instance, routes: Optional[list[Route]] = None):
        self.instance = instance
        self.routes: list[Route] = routes if routes is not None else []
        self.total_cost: float = 0.0
        self._cust_route: np.ndarray = np.full(instance.dimension, -1, dtype=np.int32)
        self._cust_pos: np.ndarray = np.full(instance.dimension, -1, dtype=np.int32)
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._cust_route[:] = -1
        self._cust_pos[:] = -1
        self.total_cost = 0.0
        for ri, route in enumerate(self.routes):
            self.total_cost += route.cost
            for pos, c in enumerate(route.customers):
                self._cust_route[c] = ri
                self._cust_pos[c] = pos

    def customer_route(self, customer: int) -> int:
        return int(self._cust_route[customer])

    def customer_pos(self, customer: int) -> int:
        return int(self._cust_pos[customer])

    def is_feasible(self) -> bool:
        visited = set()
        for route in self.routes:
            if route.load > self.instance.capacity:
                return False
            for c in route.customers:
                if c in visited:
                    return False
                visited.add(c)
        return len(visited) == self.instance.num_customers

    def remove_empty_routes(self) -> None:
        self.routes = [r for r in self.routes if len(r) > 0]
        self._rebuild_index()

    def copy(self) -> Solution:
        new_routes = [r.copy() for r in self.routes]
        sol = Solution.__new__(Solution)
        sol.instance = self.instance
        sol.routes = new_routes
        sol.total_cost = self.total_cost
        sol._cust_route = self._cust_route.copy()
        sol._cust_pos = self._cust_pos.copy()
        return sol
