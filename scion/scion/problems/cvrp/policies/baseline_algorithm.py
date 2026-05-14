"""Scion-controlled CVRP baseline algorithm subject.

This file is the preferred ``solver_design`` research target. It mirrors the
repo-local ALNS+VNS baseline structure inside the Scion problem package so a
candidate branch can modify the algorithm body itself while the original
``vrp/`` source tree remains frozen.

The checked-in champion keeps this subject inactive. Candidate proposals should
enable and materially rework this algorithm body, not wrap ``context.baseline``
as a post-processing oracle.
"""
from __future__ import annotations

import math


ENABLE_BASELINE_ALGORITHM = False

_SIGMA_BEST = 33.0
_SIGMA_BETTER = 9.0
_SIGMA_ACCEPTED = 13.0
_MAX_INITIAL_ROUTES = 500
_MAX_VNS_PASSES = 16
_MAX_ALNS_ITERATIONS = 400
_MAX_DESTROY_CUSTOMERS = 24
_MAX_REPAIR_POSITIONS = 48
_EXIT_RESERVE_FRACTION = 0.05


def solve(instance, rng, time_limit_sec, context):
    """Run the editable ALNS+VNS-style subject, or return None when inactive."""
    if not ENABLE_BASELINE_ALGORITHM:
        return None
    return _solve_subject(instance, rng, time_limit_sec, context)


def _solve_subject(instance, rng, time_limit_sec, context):
    reserve = max(0.05, float(time_limit_sec) * _EXIT_RESERVE_FRACTION)
    start_ms = context.elapsed_ms()
    routes = _clarke_wright_seed(instance)
    seed = _valid_or_nearest(routes, instance, context)
    context.record_phase("construction", context.elapsed_ms() - start_ms)

    best = seed
    current = seed
    best_key = context.objective_key(best)
    current_key = best_key

    phase_start = context.elapsed_ms()
    improved_routes, attempts, accepted, delta = _vns_improve(
        [list(route) for route in current.routes],
        instance,
        context,
        reserve,
    )
    context.record_phase("vns_initial", context.elapsed_ms() - phase_start)
    if attempts:
        candidate = context.make_solution(improved_routes)
        if context.is_valid(candidate) and context.is_better(candidate, best):
            old_key = best_key
            new_key = context.objective_key(candidate)
            best = candidate
            current = candidate
            best_key = new_key
            current_key = new_key
            context.record_move(
                "vns_initial",
                attempted=attempts,
                accepted=max(1, accepted),
                delta=max(delta, _distance_gain(old_key, new_key)),
                best_improved=True,
            )
        else:
            context.record_move("vns_initial", attempted=attempts, accepted=0)

    temperature = max(1.0, float(current_key[1]) * 0.05)
    cooling = 0.995
    segment_scores: dict[str, float] = {}
    max_iterations = min(
        _MAX_ALNS_ITERATIONS,
        max(40, int(float(time_limit_sec) * 40)),
    )
    customers = list(instance.customer_ids)

    for iteration in range(max_iterations):
        if context.remaining_time() <= reserve:
            context.set_stop_reason("time_limit")
            break
        context.record_iteration("alns", 1)
        candidate_routes = [list(route) for route in current.routes]
        destroy_name = "worst" if iteration % 3 else "random"
        q = _destroy_count(len(customers), iteration)
        removed = _destroy(candidate_routes, instance, rng, q, destroy_name)
        if not removed:
            _cool(segment_scores, destroy_name, 0.0)
            temperature *= cooling
            continue
        repaired = _repair(candidate_routes, removed, instance, rng)
        if not repaired:
            _cool(segment_scores, destroy_name, 0.0)
            temperature *= cooling
            continue

        phase_start = context.elapsed_ms()
        candidate_routes, attempts, accepted, _phase_delta = _vns_improve(
            candidate_routes,
            instance,
            context,
            reserve,
        )
        context.record_phase("vns_embedded", context.elapsed_ms() - phase_start)
        context.record_move("vns_embedded", attempted=attempts, accepted=accepted)

        candidate = context.make_solution(candidate_routes)
        if not context.is_valid(candidate):
            _cool(segment_scores, destroy_name, 0.0)
            temperature *= cooling
            continue

        candidate_key = context.objective_key(candidate)
        score = 0.0
        accepted_move = False
        best_improved = False
        delta = 0.0
        if candidate_key < best_key:
            delta = _distance_gain(best_key, candidate_key)
            best = candidate
            current = candidate
            best_key = candidate_key
            current_key = candidate_key
            score = _SIGMA_BEST
            accepted_move = True
            best_improved = True
        elif candidate_key < current_key:
            current = candidate
            current_key = candidate_key
            score = _SIGMA_BETTER
            accepted_move = True
        elif _accept_worse(current_key, candidate_key, temperature, rng):
            current = candidate
            current_key = candidate_key
            score = _SIGMA_ACCEPTED
            accepted_move = True

        context.record_move(
            "alns",
            attempted=1,
            accepted=1 if accepted_move else 0,
            delta=delta,
            best_improved=best_improved,
        )
        _cool(segment_scores, destroy_name, score)
        temperature *= cooling
    else:
        context.set_stop_reason("max_iterations")

    return best


def _valid_or_nearest(routes, instance, context):
    candidate = context.make_solution(routes)
    if context.is_valid(candidate):
        return candidate
    return context.nearest_neighbor()


def _clarke_wright_seed(instance):
    customers = list(instance.customer_ids)
    routes = [[customer] for customer in customers]
    route_of = {customer: idx for idx, customer in enumerate(customers)}
    depot = instance.depot
    savings = []
    for i, left in enumerate(customers):
        for right in customers[i + 1 :]:
            saving = (
                instance.distance(depot, left)
                + instance.distance(depot, right)
                - instance.distance(left, right)
            )
            savings.append((saving, left, right))
    savings.sort(reverse=True)

    for _saving, left, right in savings:
        li = route_of.get(left)
        ri = route_of.get(right)
        if li is None or ri is None or li == ri:
            continue
        lroute = routes[li]
        rroute = routes[ri]
        merged = None
        if lroute and rroute and lroute[-1] == left and rroute[0] == right:
            merged = lroute + rroute
        elif lroute and rroute and rroute[-1] == right and lroute[0] == left:
            merged = rroute + lroute
        elif lroute and rroute and lroute[0] == left and rroute[0] == right:
            merged = list(reversed(lroute)) + rroute
        elif lroute and rroute and lroute[-1] == left and rroute[-1] == right:
            merged = lroute + list(reversed(rroute))
        if merged is None or instance.route_load(tuple(merged)) > instance.capacity:
            continue
        routes[li] = merged
        routes[ri] = []
        for customer in merged:
            route_of[customer] = li
        if len([route for route in routes if route]) <= _MAX_INITIAL_ROUTES:
            continue
    return [route for route in routes if route]


def _vns_improve(routes, instance, context, reserve):
    current = [list(route) for route in routes if route]
    attempts = 0
    accepted = 0
    total_delta = 0.0
    for pass_idx in range(_MAX_VNS_PASSES):
        if context.remaining_time() <= reserve:
            break
        move_name = ("two_opt", "relocate", "swap")[pass_idx % 3]
        if move_name == "two_opt":
            improved, gain = _best_two_opt(current, instance)
        elif move_name == "relocate":
            improved, gain = _best_relocate(current, instance)
        else:
            improved, gain = _best_swap(current, instance)
        attempts += 1
        if not improved:
            continue
        accepted += 1
        total_delta += max(0.0, float(gain))
    return current, attempts, accepted, total_delta


def _best_two_opt(routes, instance):
    best = None
    for ri, route in enumerate(routes):
        limit = min(len(route), 48)
        for i in range(limit):
            for j in range(i + 2, limit):
                trial = list(route)
                trial[i : j + 1] = reversed(trial[i : j + 1])
                gain = instance.route_distance(tuple(route)) - instance.route_distance(
                    tuple(trial)
                )
                if gain > 1e-9 and (best is None or gain > best[0]):
                    best = (gain, ri, trial)
    if best is None:
        return False, 0.0
    gain, ri, trial = best
    routes[ri] = trial
    return True, gain


def _best_relocate(routes, instance):
    loads = [instance.route_load(tuple(route)) for route in routes]
    best = None
    for src_idx, src in enumerate(routes):
        for pos, customer in enumerate(src[:48]):
            demand = instance.demand(customer)
            src_without = src[:pos] + src[pos + 1 :]
            old_src_cost = instance.route_distance(tuple(src))
            new_src_cost = instance.route_distance(tuple(src_without)) if src_without else 0.0
            for dst_idx, dst in enumerate(routes):
                if src_idx != dst_idx and loads[dst_idx] + demand > instance.capacity:
                    continue
                max_pos = min(len(dst) + 1, _MAX_REPAIR_POSITIONS)
                for insert_pos in range(max_pos):
                    if src_idx == dst_idx:
                        if insert_pos == pos or insert_pos == pos + 1:
                            continue
                        trial_dst = list(src_without)
                        adjusted = insert_pos if insert_pos < pos else insert_pos - 1
                        adjusted = max(0, min(adjusted, len(trial_dst)))
                    else:
                        trial_dst = list(dst)
                        adjusted = insert_pos
                    old_dst_cost = 0.0 if src_idx == dst_idx else instance.route_distance(tuple(dst))
                    trial_dst.insert(adjusted, customer)
                    gain = (
                        old_src_cost
                        + old_dst_cost
                        - new_src_cost
                        - instance.route_distance(tuple(trial_dst))
                    )
                    if gain > 1e-9 and (best is None or gain > best[0]):
                        best = (gain, src_idx, dst_idx, pos, adjusted)
    if best is None:
        return False, 0.0
    gain, src_idx, dst_idx, pos, insert_pos = best
    customer = routes[src_idx].pop(pos)
    if src_idx == dst_idx and insert_pos > pos:
        insert_pos -= 1
    routes[dst_idx].insert(max(0, min(insert_pos, len(routes[dst_idx]))), customer)
    routes[:] = [route for route in routes if route]
    return True, gain


def _best_swap(routes, instance):
    loads = [instance.route_load(tuple(route)) for route in routes]
    best = None
    for left_idx, left in enumerate(routes):
        for right_idx in range(left_idx + 1, len(routes)):
            right = routes[right_idx]
            old_cost = instance.route_distance(tuple(left)) + instance.route_distance(
                tuple(right)
            )
            for li, lc in enumerate(left[:32]):
                for ri, rc in enumerate(right[:32]):
                    left_load = loads[left_idx] - instance.demand(lc) + instance.demand(rc)
                    right_load = loads[right_idx] - instance.demand(rc) + instance.demand(lc)
                    if left_load > instance.capacity or right_load > instance.capacity:
                        continue
                    trial_left = list(left)
                    trial_right = list(right)
                    trial_left[li], trial_right[ri] = trial_right[ri], trial_left[li]
                    gain = old_cost - instance.route_distance(
                        tuple(trial_left)
                    ) - instance.route_distance(tuple(trial_right))
                    if gain > 1e-9 and (best is None or gain > best[0]):
                        best = (gain, left_idx, right_idx, li, ri)
    if best is None:
        return False, 0.0
    gain, left_idx, right_idx, li, ri = best
    routes[left_idx][li], routes[right_idx][ri] = routes[right_idx][ri], routes[left_idx][li]
    return True, gain


def _destroy_count(customer_count, iteration):
    ratio = 0.10 + 0.20 * ((iteration % 7) / 6.0)
    return max(1, min(_MAX_DESTROY_CUSTOMERS, int(round(customer_count * ratio))))


def _destroy(routes, instance, rng, q, mode):
    customers = [(ri, pi, c) for ri, route in enumerate(routes) for pi, c in enumerate(route)]
    if not customers:
        return []
    if mode == "random":
        rng.shuffle(customers)
        selected = customers[:q]
    else:
        selected = sorted(
            customers,
            key=lambda item: _removal_saving(routes[item[0]], item[1], instance),
            reverse=True,
        )[:q]
    removed = []
    for _ri, _pi, customer in selected:
        for route in routes:
            if customer in route:
                route.remove(customer)
                removed.append(customer)
                break
    routes[:] = [route for route in routes if route]
    return removed


def _repair(routes, removed, instance, rng):
    pending = list(removed)
    rng.shuffle(pending)
    for customer in pending:
        best = None
        demand = instance.demand(customer)
        for route_idx, route in enumerate(routes):
            if instance.route_load(tuple(route)) + demand > instance.capacity:
                continue
            old = instance.route_distance(tuple(route))
            max_pos = min(len(route) + 1, _MAX_REPAIR_POSITIONS)
            for pos in range(max_pos):
                trial = route[:pos] + [customer] + route[pos:]
                increase = instance.route_distance(tuple(trial)) - old
                if best is None or increase < best[0]:
                    best = (increase, route_idx, pos)
        if best is None:
            if demand > instance.capacity:
                return False
            routes.append([customer])
        else:
            _increase, route_idx, pos = best
            routes[route_idx].insert(pos, customer)
    return True


def _removal_saving(route, pos, instance):
    customer = route[pos]
    prev_node = instance.depot if pos == 0 else route[pos - 1]
    next_node = instance.depot if pos == len(route) - 1 else route[pos + 1]
    return (
        instance.distance(prev_node, customer)
        + instance.distance(customer, next_node)
        - instance.distance(prev_node, next_node)
    )


def _accept_worse(current_key, candidate_key, temperature, rng):
    if candidate_key[0] > current_key[0]:
        return False
    delta = max(0.0, float(candidate_key[1]) - float(current_key[1]))
    if delta <= 0:
        return True
    threshold = math.exp(-delta / max(temperature, 1e-9))
    return rng.random() < threshold


def _distance_gain(old_key, new_key):
    if new_key[0] < old_key[0]:
        return max(1.0, float(old_key[1]) - float(new_key[1]))
    if new_key[0] > old_key[0]:
        return 0.0
    return max(0.0, float(old_key[1]) - float(new_key[1]))


def _cool(scores, name, score):
    scores[name] = float(scores.get(name, 0.0)) + float(score)
