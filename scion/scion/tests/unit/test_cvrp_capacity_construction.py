"""Engineering regressions for bounded CVRP packing recovery, not effect tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from scion.problems.cvrp.models import CvrpInstance, CvrpNode
from scion.problems.cvrp.policies.baseline_modules import construction


def _instance(demands, capacity=10, routes=2):
    return CvrpInstance(
        name="synthetic_packing",
        capacity=capacity,
        depot=0,
        nodes=(CvrpNode(0, 0, 0, 0),)
        + tuple(CvrpNode(idx, idx, 0, demand) for idx, demand in enumerate(demands, 1)),
        allowed_routes=routes,
    )


def _assert_valid(instance, solution):
    routes = solution.routes_as_tuples()
    customers = [customer for route in routes for customer in route]
    assert sorted(customers) == sorted(instance.customer_ids)
    assert len(routes) <= instance.allowed_routes
    assert all(instance.route_load(route) <= instance.capacity for route in routes)
    assert solution.total_cost == sum(
        instance.route_distance(route) for route in routes
    )


def test_successful_greedy_path_remains_exact_and_never_starts_recovery(monkeypatch):
    instance = _instance([6, 4, 5, 3])

    def unexpected(*args, **kwargs):
        pytest.fail("successful old path must not use the recovery budget")

    monkeypatch.setattr(construction, "_PackingRepairBudget", unexpected)
    solution = construction._capacity_balanced_construction(
        instance, 2, remaining_time=unexpected
    )
    assert solution.routes_as_tuples() == ((1, 2), (3, 4))
    _assert_valid(instance, solution)


def test_greedy_dead_end_is_repacked_deterministically():
    # BFD reaches loads 9,9 and cannot place the last 2. A witness is
    # (6,2,2), (5,3,2), each of load 10.
    instance = _instance([6, 5, 3, 2, 2, 2])
    first = construction._capacity_balanced_construction(instance, 2)
    second = construction._capacity_balanced_construction(instance, 2)
    assert first.routes_as_tuples() == second.routes_as_tuples()
    _assert_valid(instance, first)


def test_fragmented_slack_requires_at_least_three_bins():
    # Each old bin has slack 2; no pair can admit demand 5. Witness:
    # (5,3,2), (3,3,2,2), (3,3,3), with loads 10,10,9.
    bins = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    demands = dict(enumerate([3, 3, 2] * 3 + [5], 1))
    loads = [8, 8, 8]
    construction._repair_capacity_packing(
        bins, loads, 10, demands, 10, construction._PackingRepairBudget(None)
    )
    assert sorted(item for bucket in bins for item in bucket) == list(range(1, 11))
    assert loads == [sum(demands[item] for item in bucket) for bucket in bins]
    assert max(loads) <= 10


@pytest.mark.parametrize("demands", [[6, 6, 6], [11, 1], [10, 10, 1]])
def test_infeasible_instances_fail_explicitly(demands):
    with pytest.raises(ValueError):
        construction._capacity_balanced_construction(_instance(demands), 2)


def test_work_limit_does_not_commit_partial_repacking():
    bins, loads = [[1, 3], [2, 4, 5]], [9, 9]
    original = [bucket[:] for bucket in bins]
    with pytest.raises(ValueError, match="work limit exhausted"):
        construction._repair_capacity_packing(
            bins,
            loads,
            6,
            dict(enumerate([6, 5, 3, 2, 2, 2], 1)),
            10,
            construction._PackingRepairBudget(None, max_work=5),
        )
    assert bins == original
    assert loads == [9, 9]


def test_caller_deadline_is_honored_and_errors_propagate():
    instance = _instance([6, 5, 3, 2, 2, 2])
    with pytest.raises(TimeoutError, match="time limit exhausted"):
        construction._capacity_balanced_construction(
            instance, 2, remaining_time=lambda: 0
        )

    def broken_clock():
        raise RuntimeError("unexpected context error")

    with pytest.raises(RuntimeError, match="unexpected context error"):
        construction._capacity_balanced_construction(
            instance, 2, remaining_time=broken_clock
        )


def test_local_wall_clock_limit_is_honored(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(construction.time, "monotonic", lambda: now[0])
    budget = construction._PackingRepairBudget(None, seconds=2)
    now[0] = 2.0
    with pytest.raises(TimeoutError, match="time limit exhausted"):
        budget.tick()


def test_sparse_recovery_does_not_allocate_by_numeric_capacity():
    scale = 10**12
    instance = _instance([value * scale for value in [6, 5, 3, 2, 2, 2]], 10 * scale)
    _assert_valid(instance, construction._capacity_balanced_construction(instance, 2))


def test_scheduler_passes_remaining_time_minus_reserve(monkeypatch):
    from scion.problems.cvrp.policies.baseline_modules import scheduler

    instance = _instance([6, 5, 3, 2, 2, 2])
    context = SimpleNamespace(elapsed_ms=lambda: 0, remaining_time=lambda: 7)
    solver = SimpleNamespace(context=context, cw_threshold=0, max_routes=2)
    monkeypatch.setattr(
        scheduler, "_sweep_construction", lambda _: SimpleNamespace(routes=[[], [], []])
    )

    def check_deadline(instance, max_routes, *, remaining_time):
        assert remaining_time() == 6.5
        raise TimeoutError("test sentinel")

    monkeypatch.setattr(scheduler, "_capacity_balanced_construction", check_deadline)
    with pytest.raises(TimeoutError, match="test sentinel"):
        scheduler._ALNSVNSSolver._initial_solution(solver, instance, reserve=0.5)


def test_route_first_calls_preserve_timeout_instead_of_swallowing_it(monkeypatch):
    from scion.problems.cvrp.policies.baseline_modules import (
        route_first_heuristic,
        route_first_seeding,
    )

    instance = _instance([6, 5, 3, 2, 2, 2])
    remaining = lambda: 7

    def check_deadline(instance, max_routes, *, remaining_time):
        assert remaining_time is remaining
        raise TimeoutError("test sentinel")

    monkeypatch.setattr(
        route_first_seeding, "_clarke_wright_savings", lambda *a, **k: None
    )
    monkeypatch.setattr(route_first_seeding, "_rotated_polar_orders", lambda *a: ())
    monkeypatch.setattr(
        route_first_seeding, "_capacity_balanced_construction", check_deadline
    )
    seeds = route_first_seeding.route_first_seed_candidates(
        instance, max_routes=2, max_starts=1, remaining_time=remaining
    )
    next(seeds)
    with pytest.raises(TimeoutError, match="test sentinel"):
        next(seeds)
    monkeypatch.setattr(
        route_first_heuristic, "_capacity_balanced_construction", check_deadline
    )
    solver = SimpleNamespace(
        max_routes=2, context=SimpleNamespace(remaining_time=remaining)
    )
    with pytest.raises(TimeoutError, match="test sentinel"):
        route_first_heuristic.RouteFirstHeuristicSolver._capacity_guard(
            solver, instance
        )
