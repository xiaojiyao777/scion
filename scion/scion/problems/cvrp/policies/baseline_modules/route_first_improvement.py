"""Bounded deterministic cleanup for the CVRP route-first comparison variant."""
from __future__ import annotations

from .config import _EPS
from .state import _demand, _route_distance

_MAX_MOVE_CHECKS_PER_PASS = 20000


def improve_route_first_solution(
    solution,
    *,
    context,
    phase,
    max_passes,
    within_budget,
):
    """Apply first-improvement local cleanup without ALNS or VNS control."""

    accepted = 0
    for _ in range(max(1, int(max_passes))):
        if not within_budget():
            break
        context.record_iteration(phase, 1)
        move = (
            _first_two_opt(solution)
            or _first_relocate(solution)
            or _first_swap(solution)
        )
        if move is None:
            context.record_move(phase, attempted=1, accepted=0)
            break
        delta = float(move[1])
        solution.rebuild_index()
        context.record_move(
            phase,
            attempted=1,
            accepted=1,
            delta=delta,
            best_improved=False,
        )
        accepted += 1
    return accepted


def _first_two_opt(solution):
    checks = 0
    for route in solution.routes:
        customers = route.customers
        for left in range(len(customers) - 1):
            for right in range(left + 1, len(customers)):
                checks += 1
                if checks > _MAX_MOVE_CHECKS_PER_PASS:
                    return None
                trial = customers[:left] + list(reversed(customers[left : right + 1]))
                trial += customers[right + 1 :]
                delta = route.cost - _route_distance(solution.instance, trial)
                if delta > _EPS:
                    route.customers = trial
                    route.recalculate()
                    return ("two_opt_intra", delta)
    return None


def _first_relocate(solution):
    checks = 0
    routes = solution.routes
    for src_idx, src in enumerate(routes):
        for pos, customer in enumerate(list(src.customers)):
            demand = _demand(solution.instance, customer)
            src_without = src.customers[:pos] + src.customers[pos + 1 :]
            src_cost_after = (
                _route_distance(solution.instance, src_without) if src_without else 0.0
            )
            for dst_idx, dst in enumerate(routes):
                if dst_idx == src_idx or dst.load + demand > solution.instance.capacity:
                    continue
                for insert_pos in range(len(dst.customers) + 1):
                    checks += 1
                    if checks > _MAX_MOVE_CHECKS_PER_PASS:
                        return None
                    trial_dst = (
                        dst.customers[:insert_pos]
                        + [customer]
                        + dst.customers[insert_pos:]
                    )
                    delta = (
                        src.cost
                        + dst.cost
                        - src_cost_after
                        - _route_distance(solution.instance, trial_dst)
                    )
                    if delta > _EPS:
                        src.customers = src_without
                        dst.customers = trial_dst
                        src.recalculate()
                        dst.recalculate()
                        solution.remove_empty_routes()
                        return ("cross_route_relocate", delta)
    return None


def _first_swap(solution):
    checks = 0
    routes = solution.routes
    for left_idx in range(len(routes) - 1):
        left = routes[left_idx]
        for right_idx in range(left_idx + 1, len(routes)):
            right = routes[right_idx]
            for left_pos, left_customer in enumerate(left.customers):
                left_demand = _demand(solution.instance, left_customer)
                for right_pos, right_customer in enumerate(right.customers):
                    checks += 1
                    if checks > _MAX_MOVE_CHECKS_PER_PASS:
                        return None
                    right_demand = _demand(solution.instance, right_customer)
                    if left.load - left_demand + right_demand > solution.instance.capacity:
                        continue
                    if right.load - right_demand + left_demand > solution.instance.capacity:
                        continue
                    trial_left = list(left.customers)
                    trial_right = list(right.customers)
                    trial_left[left_pos] = right_customer
                    trial_right[right_pos] = left_customer
                    delta = (
                        left.cost
                        + right.cost
                        - _route_distance(solution.instance, trial_left)
                        - _route_distance(solution.instance, trial_right)
                    )
                    if delta > _EPS:
                        left.customers = trial_left
                        right.customers = trial_right
                        left.recalculate()
                        right.recalculate()
                        return ("cross_route_swap", delta)
    return None
