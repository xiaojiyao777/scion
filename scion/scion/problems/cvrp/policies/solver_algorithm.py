"""Compatibility CVRP solver-algorithm research hook.

The preferred solver_design target is now ``policies/baseline_algorithm.py``,
which exposes a Scion-controlled algorithm body. This older hook remains
inactive for backward compatibility with existing snapshots and tests.
"""
from __future__ import annotations


ENABLE_TEMPLATE_SOLVER = False

_MAX_INITIAL_SEEDS = 4
_MAX_SEARCH_ROUNDS = 32
_MAX_ROUTE_CAP = 18
_MAX_POSITION_CAP = 18
_MAX_DESTROY_CUSTOMERS = 10
_STAGNATION_PERTURB_ROUNDS = 5


def solve(instance, rng, time_limit_sec, context):
    """Return None by default; candidates may activate/rework the template."""
    if not ENABLE_TEMPLATE_SOLVER:
        return None
    return _solve_template(instance, rng, time_limit_sec, context)


def _solve_template(instance, rng, time_limit_sec, context):
    reserve_sec = _exit_reserve(time_limit_sec)
    start_ms = context.elapsed_ms()
    routes = _best_initial_routes(instance, rng, context)
    best = context.make_solution(routes)
    current = best
    context.record_phase("construction", context.elapsed_ms() - start_ms)

    max_rounds = min(
        _MAX_SEARCH_ROUNDS,
        max(4, int(instance.customer_count) // 2 + 4),
    )
    no_improve = 0
    stop_reason = "completed"

    for round_idx in range(max_rounds):
        if context.remaining_time() <= reserve_sec:
            stop_reason = "time_limit"
            break
        context.record_iteration("search", 1)
        phase_start = context.elapsed_ms()
        candidate_routes, phase_name, attempts = _search_round(
            [list(route) for route in current.routes],
            instance,
            rng,
            round_idx=round_idx,
        )
        elapsed = context.elapsed_ms() - phase_start
        context.record_phase(phase_name, elapsed)
        if attempts:
            context.record_move(phase_name, attempted=attempts, accepted=0)
        candidate = context.make_solution(candidate_routes)
        if not context.is_valid(candidate):
            no_improve += 1
            continue

        if context.is_better(candidate, best):
            delta = _distance_delta(context, best, candidate)
            best = candidate
            current = candidate
            no_improve = 0
            context.record_move(
                phase_name,
                attempted=0,
                accepted=1,
                delta=delta,
                best_improved=True,
            )
            continue

        if context.is_better(candidate, current):
            delta = _distance_delta(context, current, candidate)
            current = candidate
            no_improve = max(0, no_improve - 1)
            context.record_move(
                phase_name,
                attempted=0,
                accepted=1,
                delta=delta,
                best_improved=False,
            )
            continue

        no_improve += 1
        if no_improve >= _STAGNATION_PERTURB_ROUNDS and context.remaining_time() > reserve_sec:
            perturb_start = context.elapsed_ms()
            perturbed = _perturb_routes([list(route) for route in best.routes], instance, rng)
            perturbed_solution = context.make_solution(perturbed)
            context.record_phase("perturbation", context.elapsed_ms() - perturb_start)
            context.record_move("perturbation", attempted=1, accepted=0)
            if context.is_valid(perturbed_solution):
                current = perturbed_solution
                no_improve = 0

    context.set_stop_reason(stop_reason)
    return best


def _best_initial_routes(instance, rng, context):
    candidates = []
    modes = ("nearest", "demand", "far_first", "mixed")
    for mode in modes[:_MAX_INITIAL_SEEDS]:
        try:
            routes = _construct_routes(instance, rng, mode)
            solution = context.make_solution(routes)
        except Exception:
            continue
        if context.is_valid(solution):
            candidates.append((context.objective_key(solution), routes))
    try:
        seed = context.nearest_neighbor()
        if context.is_valid(seed):
            candidates.append((context.objective_key(seed), [list(route) for route in seed.routes]))
    except Exception:
        pass
    if not candidates:
        raise ValueError("unable to construct a feasible CVRP seed")
    candidates.sort(key=lambda item: item[0])
    return [list(route) for route in candidates[0][1]]


def _construct_routes(instance, rng, mode):
    demands = instance.demands
    unserved = list(instance.customer_ids)
    if mode == "demand":
        unserved.sort(key=lambda customer: (-demands[customer], customer))
    elif mode == "far_first":
        unserved.sort(
            key=lambda customer: (
                -instance.distance(instance.depot, customer),
                -demands[customer],
                customer,
            )
        )
    else:
        unserved.sort()

    routes = []
    for _route_guard in range(max(1, instance.customer_count)):
        if not unserved:
            break
        route = []
        load = 0
        current = instance.depot
        for _customer_guard in range(max(1, instance.customer_count)):
            feasible = [
                customer
                for customer in unserved
                if load + demands[customer] <= instance.capacity
            ]
            if not feasible:
                break
            nxt = _select_next_customer(instance, rng, feasible, current, mode)
            unserved.remove(nxt)
            route.append(nxt)
            load += demands[nxt]
            current = nxt
        if not route:
            raise ValueError("remaining customer demand exceeds capacity")
        routes.append(route)
    if unserved:
        raise ValueError("construction left unserved customers")
    return routes


def _select_next_customer(instance, rng, feasible, current, mode):
    demands = instance.demands
    if mode == "demand":
        return min(
            feasible,
            key=lambda customer: (
                -demands[customer],
                instance.distance(current, customer),
                rng.random(),
            ),
        )
    if mode == "far_first":
        return min(
            feasible,
            key=lambda customer: (
                -instance.distance(instance.depot, customer),
                instance.distance(current, customer),
                rng.random(),
            ),
        )
    if mode == "mixed":
        return min(
            feasible,
            key=lambda customer: (
                instance.distance(current, customer)
                - 0.15 * demands[customer],
                rng.random(),
            ),
        )
    return min(feasible, key=lambda customer: (instance.distance(current, customer), rng.random()))


def _search_round(routes, instance, rng, *, round_idx):
    operators = (
        _best_relocate,
        _best_swap,
        _best_intra_two_opt,
        _destroy_repair,
    )
    operator = operators[round_idx % len(operators)]
    candidate, attempts = operator(routes, instance, rng)
    return candidate, operator.__name__.lstrip("_"), attempts


def _best_intra_two_opt(routes, instance, rng):
    del rng
    best_routes = _copy_routes(routes)
    best_delta = 0.0
    attempts = 0
    for route_idx in _ranked_route_indices(routes, instance):
        route = routes[route_idx]
        positions = _capped_positions(len(route), _MAX_POSITION_CAP)
        for left in positions:
            for right in positions:
                if right <= left + 1:
                    continue
                attempts += 1
                old = instance.route_distance(tuple(route))
                new_route = route[:left] + list(reversed(route[left:right])) + route[right:]
                new = instance.route_distance(tuple(new_route))
                delta = old - new
                if delta > best_delta:
                    best_delta = delta
                    best_routes = _copy_routes(routes)
                    best_routes[route_idx] = new_route
    return _drop_empty_routes(best_routes), attempts


def _best_relocate(routes, instance, rng):
    del rng
    best_routes = _copy_routes(routes)
    best_delta = 0.0
    attempts = 0
    loads = _route_loads(routes, instance)
    source_indices = _ranked_route_indices(routes, instance)
    target_indices = source_indices[:_MAX_ROUTE_CAP]
    for source_idx in source_indices:
        source = routes[source_idx]
        for pos in _capped_positions(len(source), _MAX_POSITION_CAP):
            customer = source[pos]
            demand = instance.demand(customer)
            for target_idx in target_indices:
                target = routes[target_idx]
                if target_idx != source_idx and loads[target_idx] + demand > instance.capacity:
                    continue
                for insert_pos in _capped_insert_positions(len(target), _MAX_POSITION_CAP):
                    if target_idx == source_idx and insert_pos in {pos, pos + 1}:
                        continue
                    attempts += 1
                    trial = _copy_routes(routes)
                    moved = trial[source_idx].pop(pos)
                    adjusted_insert = insert_pos
                    if target_idx == source_idx and insert_pos > pos:
                        adjusted_insert -= 1
                    trial[target_idx].insert(adjusted_insert, moved)
                    trial = _drop_empty_routes(trial)
                    delta = _routes_distance(routes, instance) - _routes_distance(trial, instance)
                    if delta > best_delta:
                        best_delta = delta
                        best_routes = trial
    return _drop_empty_routes(best_routes), attempts


def _best_swap(routes, instance, rng):
    del rng
    best_routes = _copy_routes(routes)
    best_delta = 0.0
    attempts = 0
    loads = _route_loads(routes, instance)
    route_indices = _ranked_route_indices(routes, instance)
    for left_idx in route_indices:
        left_route = routes[left_idx]
        for right_idx in route_indices:
            if right_idx <= left_idx:
                continue
            right_route = routes[right_idx]
            for left_pos in _capped_positions(len(left_route), _MAX_POSITION_CAP):
                left_customer = left_route[left_pos]
                left_demand = instance.demand(left_customer)
                for right_pos in _capped_positions(len(right_route), _MAX_POSITION_CAP):
                    right_customer = right_route[right_pos]
                    right_demand = instance.demand(right_customer)
                    if loads[left_idx] - left_demand + right_demand > instance.capacity:
                        continue
                    if loads[right_idx] - right_demand + left_demand > instance.capacity:
                        continue
                    attempts += 1
                    trial = _copy_routes(routes)
                    trial[left_idx][left_pos] = right_customer
                    trial[right_idx][right_pos] = left_customer
                    delta = _routes_distance(routes, instance) - _routes_distance(trial, instance)
                    if delta > best_delta:
                        best_delta = delta
                        best_routes = trial
    return _drop_empty_routes(best_routes), attempts


def _destroy_repair(routes, instance, rng):
    working = _copy_routes(routes)
    removable = _removal_candidates(working, instance)
    if not removable:
        return working, 0
    remove_count = min(
        _MAX_DESTROY_CUSTOMERS,
        max(2, int(instance.customer_count) // 20),
        len(removable),
    )
    if remove_count <= 0:
        return working, 0
    removable.sort(key=lambda item: (-item[0], rng.random()))
    removed = []
    for _saving, route_idx, pos, customer in removable[:remove_count]:
        if route_idx >= len(working) or pos >= len(working[route_idx]):
            continue
        if working[route_idx][pos] == customer:
            removed.append(working[route_idx].pop(pos))
    working = _drop_empty_routes(working)
    attempts = len(removed)
    for customer in removed:
        inserted = _insert_customer_best_position(working, customer, instance)
        attempts += inserted[1]
        if not inserted[0]:
            working.append([customer])
    return _drop_empty_routes(working), attempts


def _perturb_routes(routes, instance, rng):
    working = _copy_routes(routes)
    removable = _removal_candidates(working, instance)
    if not removable:
        return working
    rng.shuffle(removable)
    remove_count = min(3, len(removable))
    removed = []
    for _saving, route_idx, pos, customer in removable[:remove_count]:
        if route_idx >= len(working) or pos >= len(working[route_idx]):
            continue
        if working[route_idx][pos] == customer:
            removed.append(working[route_idx].pop(pos))
    working = _drop_empty_routes(working)
    rng.shuffle(removed)
    for customer in removed:
        inserted, _attempts = _insert_customer_best_position(working, customer, instance)
        if not inserted:
            working.append([customer])
    return _drop_empty_routes(working)


def _removal_candidates(routes, instance):
    candidates = []
    for route_idx in _ranked_route_indices(routes, instance):
        route = routes[route_idx]
        for pos in _capped_positions(len(route), _MAX_POSITION_CAP):
            prev_customer = instance.depot if pos == 0 else route[pos - 1]
            customer = route[pos]
            next_customer = instance.depot if pos + 1 >= len(route) else route[pos + 1]
            saving = (
                instance.distance(prev_customer, customer)
                + instance.distance(customer, next_customer)
                - instance.distance(prev_customer, next_customer)
            )
            candidates.append((saving, route_idx, pos, customer))
    return candidates


def _insert_customer_best_position(routes, customer, instance):
    best = None
    attempts = 0
    demand = instance.demand(customer)
    loads = _route_loads(routes, instance)
    for route_idx in _ranked_route_indices(routes, instance):
        if loads[route_idx] + demand > instance.capacity:
            continue
        route = routes[route_idx]
        old_distance = instance.route_distance(tuple(route))
        for pos in _capped_insert_positions(len(route), _MAX_POSITION_CAP):
            attempts += 1
            trial_route = route[:pos] + [customer] + route[pos:]
            increase = instance.route_distance(tuple(trial_route)) - old_distance
            key = (increase, len(route), route_idx, pos)
            if best is None or key < best[0]:
                best = (key, route_idx, pos)
    if best is None:
        return False, attempts
    _key, route_idx, pos = best
    routes[route_idx].insert(pos, customer)
    return True, attempts


def _ranked_route_indices(routes, instance):
    indices = list(range(len(routes)))
    indices.sort(
        key=lambda idx: (
            -instance.route_distance(tuple(routes[idx])),
            -len(routes[idx]),
            idx,
        )
    )
    return indices[:_MAX_ROUTE_CAP]


def _capped_positions(length, cap):
    if length <= 0:
        return []
    limit = min(length, cap)
    return list(range(limit))


def _capped_insert_positions(length, cap):
    limit = min(length + 1, cap)
    return list(range(limit))


def _route_loads(routes, instance):
    return [instance.route_load(tuple(route)) for route in routes]


def _routes_distance(routes, instance):
    return sum(instance.route_distance(tuple(route)) for route in routes)


def _drop_empty_routes(routes):
    return [list(route) for route in routes if route]


def _copy_routes(routes):
    return [list(route) for route in routes]


def _distance_delta(context, incumbent, candidate):
    old_key = context.objective_key(incumbent)
    new_key = context.objective_key(candidate)
    if new_key[0] < old_key[0]:
        return max(1.0, old_key[1] - new_key[1])
    if new_key[0] > old_key[0]:
        return 0.0
    return max(0.0, old_key[1] - new_key[1])


def _exit_reserve(time_limit_sec):
    return min(1.0, max(0.05, float(time_limit_sec) * 0.08))
