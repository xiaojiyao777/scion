from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *

def test_route_pool_recombination_combines_routes_from_solution_pool() -> None:
    instance = CvrpInstance(
        name="route_pool_recombination",
        capacity=3,
        depot=0,
        allowed_routes=3,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 0, 10, 1),
            CvrpNode(2, 0, 11, 1),
            CvrpNode(3, 100, 10, 1),
            CvrpNode(4, 100, 11, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 3), (2, 4)))
    pool_a = CvrpSolution(routes=((1, 2), (3,), (4,)))
    pool_b = CvrpSolution(routes=((3, 4), (1,), (2,)))
    current_objective = cvrp_solver._objective_for_solution(
        adapter,
        instance,
        current,
    )

    candidate, calls, telemetry = cvrp_solver._route_pool_recombination_from_solutions(
        current,
        [current, pool_a, pool_b],
        instance,
        adapter=adapter,
        current_objective=current_objective,
        top_k=32,
    )

    assert candidate is not None
    assert {frozenset(route) for route in candidate.routes} == {
        frozenset({1, 2}),
        frozenset({3, 4}),
    }
    assert calls > 0
    assert telemetry["route_pool_size"] >= 6
    assert telemetry["route_pool_recombined_routes"] == 2
    assert cvrp_solver._objective_for_solution(
        adapter,
        instance,
        candidate,
    )["total_distance"] < current_objective["total_distance"]


def test_route_pool_samples_multiple_distinct_baseline_seeds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    instance = CvrpInstance(
        name="route_pool_sample_seeds",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 2),))
    current_objective = cvrp_solver._objective_for_solution(
        adapter,
        instance,
        current,
    )
    seen_seeds: list[int] = []

    def fake_baseline_root() -> Path:
        return tmp_path

    def fake_solve_with_vrp_baseline(*args: Any, **kwargs: Any) -> tuple[CvrpSolution, dict[str, Any]]:
        del args
        seen_seeds.append(int(kwargs["seed"]))
        return current, {}

    monkeypatch.setattr(cvrp_solver, "_find_vrp_baseline_root", fake_baseline_root)
    monkeypatch.setattr(
        cvrp_solver,
        "_solve_with_vrp_baseline",
        fake_solve_with_vrp_baseline,
    )
    rng = random.Random(11)

    for _call in range(2):
        cvrp_solver._best_route_pool_recombination(
            current,
            instance,
            adapter=adapter,
            current_objective=current_objective,
            top_k=32,
            rng=rng,
            time_limit_sec=20.0,
            start_time=time.perf_counter(),
            instance_path=tmp_path / "sample.vrp",
            seed=29,
        )

    assert len(seen_seeds) == 8
    assert len(set(seen_seeds)) == len(seen_seeds)
    assert cvrp_solver._route_pool_sample_cap(32) == 4


def test_route_pool_sampling_keeps_exit_time_reserve(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    instance = CvrpInstance(
        name="route_pool_time_reserve",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 2),))
    current_objective = cvrp_solver._objective_for_solution(
        adapter,
        instance,
        current,
    )
    budgets: list[float] = []

    def fake_baseline_root() -> Path:
        return tmp_path

    def fake_solve_with_vrp_baseline(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[CvrpSolution, dict[str, Any]]:
        del args
        budgets.append(float(kwargs["time_limit_sec"]))
        return current, {}

    monkeypatch.setattr(cvrp_solver, "_find_vrp_baseline_root", fake_baseline_root)
    monkeypatch.setattr(
        cvrp_solver,
        "_solve_with_vrp_baseline",
        fake_solve_with_vrp_baseline,
    )

    cvrp_solver._best_route_pool_recombination(
        current,
        instance,
        adapter=adapter,
        current_objective=current_objective,
        top_k=32,
        rng=random.Random(11),
        time_limit_sec=20.0,
        start_time=time.perf_counter() - 16.0,
        instance_path=tmp_path / "sample.vrp",
        seed=29,
    )

    assert len(budgets) == 4
    assert max(budgets) < 0.5

    budgets.clear()
    cvrp_solver._best_route_pool_recombination(
        current,
        instance,
        adapter=adapter,
        current_objective=current_objective,
        top_k=32,
        rng=random.Random(11),
        time_limit_sec=20.0,
        start_time=time.perf_counter() - 17.4,
        instance_path=tmp_path / "sample.vrp",
        seed=29,
    )

    assert budgets == []


def test_route_pool_recombination_stops_before_exit_reserve() -> None:
    instance = CvrpInstance(
        name="route_pool_recombination_time_guard",
        capacity=3,
        depot=0,
        allowed_routes=2,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 0, 10, 1),
            CvrpNode(2, 0, 11, 1),
            CvrpNode(3, 100, 10, 1),
            CvrpNode(4, 100, 11, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 3), (2, 4)))
    current_objective = cvrp_solver._objective_for_solution(
        adapter,
        instance,
        current,
    )

    candidate, calls, telemetry = cvrp_solver._route_pool_recombination_from_solutions(
        current,
        [current],
        instance,
        adapter=adapter,
        current_objective=current_objective,
        top_k=32,
        start_time=time.perf_counter() - 9.0,
        time_limit_sec=10.0,
        exit_reserve_sec=2.0,
    )

    assert candidate is None
    assert calls == 0
    assert telemetry["skip_reason"] == "route_pool_time_limit"


def test_route_pool_can_complete_pool_route_with_incumbent_residual() -> None:
    instance = CvrpInstance(
        name="route_pool_residual_completion",
        capacity=10,
        depot=0,
        allowed_routes=3,
        use_integer_cost=False,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 100, 0, 1),
            CvrpNode(2, 101, 0, 1),
            CvrpNode(3, 100, 1, 1),
            CvrpNode(4, 101, 1, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 4), (2,), (3,)))
    partial_pool = CvrpSolution(routes=((1, 2),))
    current_objective = cvrp_solver._objective_for_solution(
        adapter,
        instance,
        current,
    )

    candidate, calls, telemetry = cvrp_solver._route_pool_recombination_from_solutions(
        current,
        [current, partial_pool],
        instance,
        adapter=adapter,
        current_objective=current_objective,
        top_k=16,
    )

    assert candidate is not None
    assert calls > 0
    assert (1, 2) in candidate.routes
    assert telemetry["route_pool_recombined_routes"] == 3
    assert cvrp_solver._objective_for_solution(
        adapter,
        instance,
        candidate,
    )["total_distance"] < current_objective["total_distance"]


def test_main_search_strategy_auto_adds_route_pool_for_old_deep_pair() -> None:
    instance = CvrpInstance(
        name="auto_route_pool",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
        ),
    )
    audit = cvrp_solver._main_search_strategy_defaults()

    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "problem_adaptation": {
                "strategy_family": "baseline_intensification",
                "instance_profile": {},
                "phase_objective": "phase_best_distance",
                "component_roles": {
                    "route_pair_swap": "primary",
                    "bounded_destroy_repair": "support",
                },
                "fallback_order": ["route_pair_swap", "bounded_destroy_repair"],
                "evidence_targets": [
                    "main_search_component_phase_delta_sum",
                    "main_search_objective_delta_by_phase",
                ],
            },
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pair_swap", "bounded_destroy_repair"],
                "rounds": 1,
                "top_k": 16,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )

    assert audit["main_search_strategy_errors"] == 0
    assert audit["main_search_components"] == [
        "route_pool_recombination",
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert audit["main_search_route_pool_auto_added"] is True
    assert audit["main_search_route_pool_activation"] == "adaptive"
    assert audit["main_search_route_pool_min_customers"] == 80
    assert audit["main_search_route_pool_max_rounds"] == 8
    assert audit["main_search_algorithm_body_source"] == "declared"
    assert (
        audit["main_search_component_roles"]["route_pool_recombination"]
        == "support"
    )


def test_main_search_strategy_algorithm_body_controls_route_pool_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    instance = CvrpInstance(
        name="algorithm_body_scope",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    current = CvrpSolution(routes=((1, 2),))
    audit = cvrp_solver._main_search_strategy_defaults()

    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": {
                "phase_sequence": [
                    "construction",
                    "baseline",
                    "global_recombination",
                    "route_structure_repair",
                    "local_cleanup",
                ],
                "route_pool_activation": "adaptive",
                "route_pool_min_customers": 80,
                "route_pool_max_rounds": 8,
                "local_cleanup_after_recombination": False,
                "adaptive_component_budget": True,
            },
            "problem_adaptation": {
                "strategy_family": "baseline_intensification",
                "instance_profile": {},
                "phase_objective": "phase_best_distance",
                "component_roles": {
                    "route_pair_swap": "primary",
                    "bounded_destroy_repair": "support",
                },
                "fallback_order": ["route_pair_swap", "bounded_destroy_repair"],
                "evidence_targets": [
                    "main_search_component_phase_delta_sum",
                    "main_search_objective_delta_by_phase",
                ],
            },
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pair_swap", "bounded_destroy_repair"],
                "rounds": 1,
                "top_k": 16,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": False,
                "strength": 1,
                "max_perturbations": 0,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )

    def fail_route_pool(*args: Any, **kwargs: Any) -> tuple[None, int, dict[str, Any]]:
        del args, kwargs
        raise AssertionError("route_pool_recombination should be scoped out")

    monkeypatch.setattr(
        cvrp_solver,
        "_best_route_pool_recombination",
        fail_route_pool,
    )

    _, runtime = cvrp_solver.improve_with_main_search_strategy(
        current,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
        instance_path=tmp_path / "tiny.vrp",
    )

    assert runtime["main_search_route_pool_auto_added"] is True
    assert runtime["main_search_route_pool_invocations"] == 0
    assert runtime["main_search_attempted_components"][0] == "route_pool_recombination"
    assert runtime["main_search_component_skip_reasons"]["route_pool_recombination"] == {
        "algorithm_body_route_pool_scope": 1,
    }
