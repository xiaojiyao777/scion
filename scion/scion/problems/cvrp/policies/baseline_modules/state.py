"""Internal route and solution state for the CVRP solver-design subject."""
from __future__ import annotations

import math


class _Route:
    __slots__ = ("customers", "load", "cost", "_instance")

    def __init__(self, instance, customers=None):
        self._instance = instance
        self.customers = list(customers) if customers else []
        self.load = 0
        self.cost = 0.0
        self.recalculate()

    def recalculate(self):
        self.load = sum(_demand(self._instance, c) for c in self.customers)
        self.cost = _route_distance(self._instance, self.customers)

    def copy(self):
        route = _Route.__new__(_Route)
        route._instance = self._instance
        route.customers = list(self.customers)
        route.load = self.load
        route.cost = self.cost
        return route

    def can_insert(self, customer):
        return self.load + _demand(self._instance, customer) <= self._instance.capacity

    def cost_of_insert(self, customer, position):
        depot = self._instance.depot
        prev_node = depot if position == 0 else self.customers[position - 1]
        next_node = depot if position == len(self.customers) else self.customers[position]
        return (
            self._instance.distance(prev_node, customer)
            + self._instance.distance(customer, next_node)
            - self._instance.distance(prev_node, next_node)
        )

    def cost_of_remove(self, position):
        depot = self._instance.depot
        customer = self.customers[position]
        prev_node = depot if position == 0 else self.customers[position - 1]
        next_node = (
            depot
            if position == len(self.customers) - 1
            else self.customers[position + 1]
        )
        return (
            self._instance.distance(prev_node, next_node)
            - self._instance.distance(prev_node, customer)
            - self._instance.distance(customer, next_node)
        )

    def insert(self, customer, position):
        delta = self.cost_of_insert(customer, position)
        self.customers.insert(position, customer)
        self.cost += delta
        self.load += _demand(self._instance, customer)

    def remove(self, position):
        delta = self.cost_of_remove(position)
        customer = self.customers.pop(position)
        self.cost += delta
        self.load -= _demand(self._instance, customer)
        return customer

    def __len__(self):
        return len(self.customers)


class _Solution:
    __slots__ = ("instance", "routes", "total_cost", "_route_of", "_pos_of", "stop_reason")

    def __init__(self, instance, routes=None):
        self.instance = instance
        self.routes = list(routes) if routes else []
        self.total_cost = 0.0
        self._route_of = {}
        self._pos_of = {}
        self.stop_reason = "completed"
        self.rebuild_index()

    def rebuild_index(self):
        self._route_of = {}
        self._pos_of = {}
        self.total_cost = 0.0
        for route_idx, route in enumerate(self.routes):
            route.recalculate()
            self.total_cost += route.cost
            for pos, customer in enumerate(route.customers):
                self._route_of[customer] = route_idx
                self._pos_of[customer] = pos

    def copy(self):
        solution = _Solution.__new__(_Solution)
        solution.instance = self.instance
        solution.routes = [route.copy() for route in self.routes]
        solution.total_cost = self.total_cost
        solution._route_of = dict(self._route_of)
        solution._pos_of = dict(self._pos_of)
        solution.stop_reason = self.stop_reason
        return solution

    def customer_route(self, customer):
        return self._route_of.get(customer, -1)

    def customer_pos(self, customer):
        return self._pos_of.get(customer, -1)

    def remove_empty_routes(self):
        self.routes = [route for route in self.routes if route.customers]
        self.rebuild_index()

    def is_feasible(self):
        seen = set()
        for route in self.routes:
            if route.load > self.instance.capacity:
                return False
            for customer in route.customers:
                if customer in seen:
                    return False
                seen.add(customer)
        return seen == set(self.instance.customer_ids)

    def routes_as_tuples(self):
        return tuple(tuple(route.customers) for route in self.routes if route.customers)

def _route_distance(instance, customers):
    total = 0.0
    prev = instance.depot
    for customer in customers:
        total += instance.distance(prev, customer)
        prev = customer
    total += instance.distance(prev, instance.depot)
    return total


def _prefix_loads(instance, customers):
    loads = [0]
    total = 0
    for customer in customers:
        total += _demand(instance, customer)
        loads.append(total)
    return loads


def _distance_scale(instance):
    nodes = list(instance.nodes)
    if not nodes:
        return 1.0
    min_x = min(node.x for node in nodes)
    max_x = max(node.x for node in nodes)
    min_y = min(node.y for node in nodes)
    max_y = max(node.y for node in nodes)
    return max(math.hypot(max_x - min_x, max_y - min_y), 1.0)


def _demand(instance, customer):
    return int(instance.demand(customer))


def _node(instance, node_id):
    for node in instance.nodes:
        if node.id == node_id:
            return node
