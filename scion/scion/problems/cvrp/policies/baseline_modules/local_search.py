"""Local-search and VNS neighborhoods for the CVRP solver-design subject."""
from __future__ import annotations

from .config import _EPS
from .state import _demand, _prefix_loads, _route_distance


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
