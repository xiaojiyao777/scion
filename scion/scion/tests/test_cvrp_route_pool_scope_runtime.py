from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *

def test_main_search_strategy_algorithm_body_allows_explicit_small_route_pool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    instance = CvrpInstance(
        name="algorithm_body_always",
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
                "phase_sequence": ["construction", "baseline", "global_recombination"],
                "route_pool_activation": "always",
                "route_pool_min_customers": 80,
                "route_pool_max_rounds": 1,
                "local_cleanup_after_recombination": False,
                "adaptive_component_budget": True,
            },
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pool_recombination"],
                "rounds": 2,
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

    def no_candidate_route_pool(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[None, int, dict[str, Any]]:
        del args, kwargs
        return None, 1, {
            "route_pool_source_solutions": 1,
            "route_pool_sample_count": 1,
            "route_pool_size": 1,
            "route_pool_branch_calls": 0,
            "route_pool_recombined_routes": 0,
        }

    monkeypatch.setattr(
        cvrp_solver,
        "_best_route_pool_recombination",
        no_candidate_route_pool,
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

    assert runtime["main_search_route_pool_activation"] == "always"
    assert runtime["main_search_route_pool_invocations"] == 1
    assert runtime["main_search_component_attempts"]["route_pool_recombination"] == 1
    assert runtime["main_search_component_skip_reasons"]["route_pool_recombination"] == {
        "no_improving_candidate": 1,
    }


def test_main_search_strategy_phase_sequence_controls_component_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="phase_order",
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
                    "route_structure_repair",
                    "global_recombination",
                    "local_cleanup",
                ],
                "baseline_budget_policy": "declared",
                "route_pool_activation": "always",
                "route_pool_min_customers": 0,
                "route_pool_max_rounds": 1,
                "local_cleanup_after_recombination": False,
                "adaptive_component_budget": True,
            },
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.5, "params": {}},
            "improvement": {
                "enabled_components": [
                    "route_pool_recombination",
                    "route_pair_swap",
                    "intra_route_2opt",
                ],
                "rounds": 1,
                "top_k": 128,
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
    calls: list[tuple[str, int]] = []

    def no_candidate(
        component: str,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[None, int, dict[str, Any]]:
        del args
        calls.append((component, int(kwargs["top_k"])))
        return None, 1, {}

    monkeypatch.setattr(cvrp_solver, "_main_search_component_candidate", no_candidate)

    _, runtime = cvrp_solver.improve_with_main_search_strategy(
        current,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
    )

    assert [component for component, _top_k in calls] == [
        "route_pair_swap",
        "route_pool_recombination",
        "intra_route_2opt",
    ]
    assert runtime["main_search_phase_component_order"] == {
        "route_structure_repair": ["route_pair_swap"],
        "global_recombination": ["route_pool_recombination"],
        "local_cleanup": ["intra_route_2opt"],
    }
    assert runtime["main_search_component_top_k_effective"][
        "route_pool_recombination"
    ] == 24


