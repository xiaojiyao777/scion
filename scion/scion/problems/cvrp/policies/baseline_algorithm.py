"""Scion-controlled CVRP baseline algorithm subject.

This file is the preferred ``solver_design`` research target. It is a
self-contained, branch-owned port of the repo-local ALNS+VNS CVRP solver.
Candidate branches should modify this algorithm body directly. The original
``vrp/`` source tree remains frozen and is not imported here.
"""
from __future__ import annotations

import math


ENABLE_BASELINE_ALGORITHM = True

SIGMA_BEST = 33.0
SIGMA_BETTER = 9.0
SIGMA_ACCEPTED = 13.0

BASELINE_TIME_FRACTION = 0.80
DESTROY_RATIO = (0.10, 0.40)
SEGMENT_LENGTH = 100
REACTION_FACTOR = 0.1
VNS_MAX_NO_IMPROVE = 5000
USE_VNS = True
CW_THRESHOLD = 1500
VNS_THRESHOLD = 1200
ALNS_THRESHOLD = 2000
MAX_DESTROY_CUSTOMERS = 200
EXIT_RESERVE_FRACTION = 0.03

_EPS = 1e-9


def solve(instance, rng, time_limit_sec, context):
    """Run the controlled champion baseline algorithm."""
    if not ENABLE_BASELINE_ALGORITHM:
        return None
    solver = _ALNSVNSSolver(
        time_limit=max(0.05, float(time_limit_sec) * BASELINE_TIME_FRACTION),
        destroy_ratio=DESTROY_RATIO,
        segment_length=SEGMENT_LENGTH,
        reaction_factor=REACTION_FACTOR,
        vns_max_no_improve=VNS_MAX_NO_IMPROVE,
        use_vns=USE_VNS,
        cw_threshold=CW_THRESHOLD,
        vns_threshold=VNS_THRESHOLD,
        alns_threshold=ALNS_THRESHOLD,
        max_destroy_customers=MAX_DESTROY_CUSTOMERS,
        max_routes=instance.allowed_routes or instance.bks_routes,
        context=context,
    )
    solution = solver.solve(instance, rng)
    context.set_stop_reason(solution.stop_reason)
    return context.make_solution(solution.routes_as_tuples())


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


class _AdaptiveWeights:
    def __init__(self, names, reaction_factor=0.1, min_weight=0.1):
        if not names:
            raise ValueError("at least one operator is required")
        self.names = list(names)
        self.weights = [1.0 for _ in self.names]
        self.scores = [0.0 for _ in self.names]
        self.usages = [0 for _ in self.names]
        self.reaction_factor = reaction_factor
        self.min_weight = min_weight

    def choose(self, rng):
        total = sum(self.weights)
        pick = rng.random() * total
        acc = 0.0
        for idx, weight in enumerate(self.weights):
            acc += weight
            if pick <= acc:
                return idx
        return len(self.weights) - 1

    def record(self, idx, score):
        self.usages[idx] += 1
        self.scores[idx] += float(score)

    def update(self):
        r = self.reaction_factor
        for idx, weight in enumerate(self.weights):
            if self.usages[idx] > 0:
                observed = self.scores[idx] / self.usages[idx]
                self.weights[idx] = max(
                    self.min_weight,
                    (1.0 - r) * weight + r * observed,
                )
        self.scores = [0.0 for _ in self.names]
        self.usages = [0 for _ in self.names]


class _SimulatedAnnealing:
    def __init__(self, initial_cost, estimated_iterations, start_ratio=0.05, end_ratio=0.0001):
        base = max(float(initial_cost), 1.0)
        self.start_temp = max(base * start_ratio, 1e-9)
        self.end_temp = max(base * end_ratio, 1e-12)
        self.temperature = self.start_temp
        estimated_iterations = max(1, int(estimated_iterations))
        self.cooling_rate = (self.end_temp / self.start_temp) ** (1.0 / estimated_iterations)

    def accept(self, current_cost, candidate_cost, rng):
        delta = float(candidate_cost) - float(current_cost)
        if delta <= 0:
            return True
        if self.temperature <= 0:
            return False
        return rng.random() < math.exp(-delta / self.temperature)

    def cool(self):
        self.temperature = max(self.end_temp, self.temperature * self.cooling_rate)


class _ALNSVNSSolver:
    def __init__(
        self,
        *,
        time_limit,
        destroy_ratio,
        segment_length,
        reaction_factor,
        vns_max_no_improve,
        use_vns,
        cw_threshold,
        vns_threshold,
        alns_threshold,
        max_destroy_customers,
        max_routes,
        context,
    ):
        self.time_limit = float(time_limit)
        self.destroy_ratio = destroy_ratio
        self.segment_length = max(1, int(segment_length))
        self.reaction_factor = float(reaction_factor)
        self.vns_max_no_improve = int(vns_max_no_improve)
        self.use_vns = bool(use_vns)
        self.cw_threshold = int(cw_threshold)
        self.vns_threshold = int(vns_threshold)
        self.alns_threshold = int(alns_threshold)
        self.max_destroy_customers = max(1, int(max_destroy_customers))
        self.max_routes = int(max_routes) if max_routes is not None else None
        self.context = context

    def solve(self, instance, rng):
        start_ms = self.context.elapsed_ms()
        reserve = max(0.05, self.time_limit * EXIT_RESERVE_FRACTION)

        phase_ms = self.context.elapsed_ms()
        current = self._initial_solution(instance, reserve)
        self.context.record_phase("construction", self.context.elapsed_ms() - phase_ms)
        best = current.copy()

        destroy_ops = [
            ("random", _random_removal),
            ("worst", _worst_removal),
            ("shaw", _shaw_removal),
            ("route", _route_removal),
        ]
        repair_ops = [
            ("greedy", _greedy_insertion),
            ("regret2", _regret2_insertion),
            ("regret3", _regret3_insertion),
        ]
        destroy_weights = _AdaptiveWeights([name for name, _ in destroy_ops], self.reaction_factor)
        repair_weights = _AdaptiveWeights([name for name, _ in repair_ops], self.reaction_factor)
        estimated_iterations = max(100, int(self.time_limit * 50))
        annealing = _SimulatedAnnealing(current.total_cost, estimated_iterations)

        if instance.customer_count > self.alns_threshold or self.time_limit <= 0:
            best.stop_reason = "alns_threshold"
            return best

        low, high = self.destroy_ratio
        low = max(0.0, min(float(low), float(high)))
        high = max(low, float(high))
        iteration = 0

        while self._within_budget(start_ms, reserve):
            iteration += 1
            self.context.record_iteration("alns", 1)
            candidate = current.copy()
            q_ratio = rng.uniform(low, high)
            q = max(1, int(round(instance.customer_count * q_ratio)))
            q = min(q, self.max_destroy_customers)

            d_idx = destroy_weights.choose(rng)
            r_idx = repair_weights.choose(rng)
            destroy_name, destroy_op = destroy_ops[d_idx]
            _repair_name, repair_op = repair_ops[r_idx]
            score = 0.0
            accepted = False
            best_improved = False
            delta = 0.0

            try:
                removed = destroy_op(candidate, q, rng)
                if not removed:
                    destroy_weights.record(d_idx, 0.0)
                    repair_weights.record(r_idx, 0.0)
                    annealing.cool()
                    self.context.record_move("alns", attempted=1, accepted=0)
                    continue
                repair_op(candidate, removed, rng)
                candidate.remove_empty_routes()
                if self.use_vns and instance.customer_count <= self.vns_threshold:
                    phase_ms = self.context.elapsed_ms()
                    improved = _vns(
                        candidate,
                        _default_vns_operators(),
                        self.vns_max_no_improve,
                        self.context,
                        reserve,
                    )
                    self.context.record_phase("vns_embedded", self.context.elapsed_ms() - phase_ms)
                    candidate.remove_empty_routes()
                    if improved:
                        candidate.rebuild_index()
            except ValueError:
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                self.context.record_move("alns", attempted=1, accepted=0)
                continue

            if not candidate.is_feasible():
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                self.context.record_move("alns", attempted=1, accepted=0)
                continue
            if self.max_routes is not None and len(candidate.routes) > self.max_routes:
                destroy_weights.record(d_idx, 0.0)
                repair_weights.record(r_idx, 0.0)
                annealing.cool()
                self.context.record_move("alns", attempted=1, accepted=0)
                continue

            if candidate.total_cost + _EPS < best.total_cost:
                delta = max(0.0, best.total_cost - candidate.total_cost)
                best = candidate.copy()
                current = candidate
                accepted = True
                best_improved = True
                score = SIGMA_BEST
            elif candidate.total_cost + _EPS < current.total_cost:
                current = candidate
                accepted = True
                score = SIGMA_BETTER
            elif annealing.accept(current.total_cost, candidate.total_cost, rng):
                current = candidate
                accepted = True
                score = SIGMA_ACCEPTED

            destroy_weights.record(d_idx, score)
            repair_weights.record(r_idx, score)
            self.context.record_move(
                "alns",
                attempted=1,
                accepted=1 if accepted else 0,
                delta=delta,
                best_improved=best_improved,
            )
            if iteration % self.segment_length == 0:
                destroy_weights.update()
                repair_weights.update()
            annealing.cool()

        destroy_weights.update()
        repair_weights.update()
        best.stop_reason = "time_limit" if self.context.remaining_time() <= reserve else "completed"
        return best

    def _initial_solution(self, instance, reserve):
        if instance.customer_count > self.cw_threshold:
            solution = _sweep_construction(instance)
        else:
            solution = _clarke_wright_savings(instance, target_routes=self.max_routes)
        if self.max_routes is not None and len(solution.routes) > self.max_routes:
            solution = _capacity_balanced_construction(instance, self.max_routes)
        if not solution.is_feasible():
            solution = _nearest_neighbor(instance)
        if not solution.is_feasible():
            raise ValueError(f"unable to construct feasible solution for {instance.name}")
        if self.max_routes is not None and len(solution.routes) > self.max_routes:
            raise ValueError(
                f"initial solution uses {len(solution.routes)} routes; "
                f"max_routes={self.max_routes}"
            )
        if self.use_vns and self.time_limit > 0 and instance.customer_count <= self.vns_threshold:
            phase_ms = self.context.elapsed_ms()
            _vns(
                solution,
                _default_vns_operators(),
                self.vns_max_no_improve,
                self.context,
                reserve,
            )
            self.context.record_phase("vns_initial", self.context.elapsed_ms() - phase_ms)
            solution.remove_empty_routes()
        return solution

    def _within_budget(self, start_ms, reserve):
        elapsed_s = max(0.0, (self.context.elapsed_ms() - start_ms) / 1000.0)
        return elapsed_s < self.time_limit and self.context.remaining_time() > reserve


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


def _vns(solution, operators, max_no_improve, context, reserve):
    improved_overall = False
    operator_idx = 0
    no_improve_count = 0
    while (
        operator_idx < len(operators)
        and no_improve_count < max_no_improve
        and context.remaining_time() > reserve
    ):
        before = solution.total_cost
        if operators[operator_idx](solution, context, reserve):
            improved_overall = True
            delta = max(0.0, before - solution.total_cost)
            context.record_move(
                "vns",
                attempted=1,
                accepted=1,
                delta=delta,
                best_improved=delta > 0,
            )
            operator_idx = 0
            no_improve_count = 0
        else:
            context.record_move("vns", attempted=1, accepted=0)
            operator_idx += 1
            no_improve_count += 1
    return improved_overall


def _default_vns_operators():
    return [
        _two_opt_intra,
        _relocate,
        _or_opt_1,
        _or_opt_2,
        _or_opt_3,
        _swap,
        _two_opt_star,
    ]


def _two_opt_intra(solution, context, reserve):
    improved = False
    for route in solution.routes:
        found = True
        while found and context.remaining_time() > reserve:
            found = False
            customers = route.customers
            for i in range(len(customers) - 1):
                for j in range(i + 1, len(customers)):
                    trial = customers[:i] + list(reversed(customers[i : j + 1])) + customers[j + 1 :]
                    delta = _route_distance(solution.instance, trial) - route.cost
                    if delta < -_EPS:
                        route.customers = trial
                        route.recalculate()
                        solution.rebuild_index()
                        improved = True
                        found = True
                        break
                if found:
                    break
    return improved


def _relocate(solution, context, reserve):
    improved = False
    found = True
    while found and context.remaining_time() > reserve:
        found = False
        routes = solution.routes
        for src_idx, src in enumerate(routes):
            for pos, customer in enumerate(list(src.customers)):
                best_gain = _EPS
                best_dst = -1
                best_pos = -1
                for dst_idx, dst in enumerate(routes):
                    if dst_idx == src_idx:
                        continue
                    if not dst.can_insert(customer):
                        continue
                    save = -src.cost_of_remove(pos)
                    for insert_pos in range(len(dst.customers) + 1):
                        gain = save - dst.cost_of_insert(customer, insert_pos)
                        if gain > best_gain:
                            best_gain = gain
                            best_dst = dst_idx
                            best_pos = insert_pos
                if best_dst >= 0:
                    src.remove(pos)
                    routes[best_dst].insert(customer, best_pos)
                    solution.rebuild_index()
                    improved = True
                    found = True
                    break
            if found:
                break
    return improved


def _swap(solution, context, reserve):
    improved = False
    found = True
    while found and context.remaining_time() > reserve:
        found = False
        routes = solution.routes
        for left_idx in range(len(routes) - 1):
            left = routes[left_idx]
            for right_idx in range(left_idx + 1, len(routes)):
                right = routes[right_idx]
                for li, left_customer in enumerate(left.customers):
                    for ri, right_customer in enumerate(right.customers):
                        left_load = (
                            left.load
                            - _demand(solution.instance, left_customer)
                            + _demand(solution.instance, right_customer)
                        )
                        right_load = (
                            right.load
                            - _demand(solution.instance, right_customer)
                            + _demand(solution.instance, left_customer)
                        )
                        if left_load > solution.instance.capacity or right_load > solution.instance.capacity:
                            continue
                        trial_left = list(left.customers)
                        trial_right = list(right.customers)
                        trial_left[li] = right_customer
                        trial_right[ri] = left_customer
                        delta = (
                            _route_distance(solution.instance, trial_left)
                            + _route_distance(solution.instance, trial_right)
                            - left.cost
                            - right.cost
                        )
                        if delta < -_EPS:
                            left.customers = trial_left
                            right.customers = trial_right
                            left.recalculate()
                            right.recalculate()
                            solution.rebuild_index()
                            improved = True
                            found = True
                            break
                    if found:
                        break
                if found:
                    break
            if found:
                break
    return improved


def _or_opt_1(solution, context, reserve):
    return _or_opt(solution, 1, context, reserve)


def _or_opt_2(solution, context, reserve):
    return _or_opt(solution, 2, context, reserve)


def _or_opt_3(solution, context, reserve):
    return _or_opt(solution, 3, context, reserve)


def _or_opt(solution, seg_len, context, reserve):
    improved = False
    found = True
    while found and context.remaining_time() > reserve:
        found = False
        routes = solution.routes
        for src_idx, src in enumerate(routes):
            if len(src.customers) < seg_len:
                continue
            for pos in range(len(src.customers) - seg_len + 1):
                segment = src.customers[pos : pos + seg_len]
                segment_demand = sum(_demand(solution.instance, c) for c in segment)
                src_without = src.customers[:pos] + src.customers[pos + seg_len :]
                old_src = src.cost
                new_src = _route_distance(solution.instance, src_without) if src_without else 0.0
                best_gain = _EPS
                best_dst = -1
                best_pos = -1
                best_rev = False
                for dst_idx, dst in enumerate(routes):
                    if dst_idx == src_idx:
                        continue
                    if dst.load + segment_demand > solution.instance.capacity:
                        continue
                    for insert_pos in range(len(dst.customers) + 1):
                        for reverse in ([False, True] if seg_len > 1 else [False]):
                            moved = list(reversed(segment)) if reverse else list(segment)
                            trial_dst = dst.customers[:insert_pos] + moved + dst.customers[insert_pos:]
                            gain = (
                                old_src
                                + dst.cost
                                - new_src
                                - _route_distance(solution.instance, trial_dst)
                            )
                            if gain > best_gain:
                                best_gain = gain
                                best_dst = dst_idx
                                best_pos = insert_pos
                                best_rev = reverse
                if best_dst >= 0:
                    moved = list(reversed(segment)) if best_rev else list(segment)
                    src.customers = src_without
                    dst = routes[best_dst]
                    dst.customers = dst.customers[:best_pos] + moved + dst.customers[best_pos:]
                    src.recalculate()
                    dst.recalculate()
                    solution.remove_empty_routes()
                    improved = True
                    found = True
                    break
            if found:
                break
    return improved


def _two_opt_star(solution, context, reserve):
    improved = False
    found = True
    while found and context.remaining_time() > reserve:
        found = False
        routes = solution.routes
        for left_idx in range(len(routes) - 1):
            left = routes[left_idx]
            for right_idx in range(left_idx + 1, len(routes)):
                right = routes[right_idx]
                prefix_left = _prefix_loads(solution.instance, left.customers)
                prefix_right = _prefix_loads(solution.instance, right.customers)
                for left_pos in range(len(left.customers) + 1):
                    for right_pos in range(len(right.customers) + 1):
                        new_left = left.customers[:left_pos] + right.customers[right_pos:]
                        new_right = right.customers[:right_pos] + left.customers[left_pos:]
                        if (
                            prefix_left[left_pos]
                            + (prefix_right[-1] - prefix_right[right_pos])
                            > solution.instance.capacity
                        ):
                            continue
                        if (
                            prefix_right[right_pos]
                            + (prefix_left[-1] - prefix_left[left_pos])
                            > solution.instance.capacity
                        ):
                            continue
                        delta = (
                            _route_distance(solution.instance, new_left)
                            + _route_distance(solution.instance, new_right)
                            - left.cost
                            - right.cost
                        )
                        if delta < -_EPS:
                            left.customers = new_left
                            right.customers = new_right
                            left.recalculate()
                            right.recalculate()
                            solution.remove_empty_routes()
                            improved = True
                            found = True
                            break
                    if found:
                        break
                if found:
                    break
            if found:
                break
    return improved


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
    raise KeyError(node_id)
