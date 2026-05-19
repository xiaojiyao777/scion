from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *

def test_route_pool_recombination_receives_construction_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="route_pool_uses_construction_pool",
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
    construction_solution = CvrpSolution(routes=((1, 2), (3, 4)))
    seen: dict[str, int] = {}

    def capture_pool(
        solution: CvrpSolution,
        pool_solutions: list[CvrpSolution],
        *args: Any,
        **kwargs: Any,
    ) -> tuple[None, int, dict[str, Any]]:
        del solution, args, kwargs
        seen["pool_size"] = len(pool_solutions)
        return None, 0, {
            "route_pool_source_solutions": len(pool_solutions),
            "route_pool_size": 0,
            "route_pool_branch_calls": 0,
            "route_pool_recombined_routes": 0,
        }

    monkeypatch.setattr(
        cvrp_solver,
        "_route_pool_recombination_from_solutions",
        capture_pool,
    )

    _candidate, _calls, telemetry = cvrp_solver._best_route_pool_recombination(
        current,
        instance,
        adapter=adapter,
        current_objective={"fleet_violation": 0.0, "total_distance": 500.0},
        top_k=16,
        mechanism_policies={
            "_main_search_construction_pool_solutions": [construction_solution],
        },
    )

    assert seen["pool_size"] == 2
    assert telemetry["route_pool_source_solutions"] == 2


def test_local_cleanup_after_recombination_runs_cleanup_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="cleanup_after_recombination",
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
    recombined = CvrpSolution(routes=((1, 2), (3, 4)))
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": {
                "phase_sequence": ["global_recombination"],
                "baseline_budget_policy": "declared",
                "route_pool_activation": "always",
                "route_pool_min_customers": 0,
                "route_pool_max_rounds": 1,
                "local_cleanup_after_recombination": True,
                "adaptive_component_budget": False,
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
                    "intra_route_2opt",
                ],
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
    calls: list[str] = []

    def fake_choice(
        component: str,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[CvrpSolution | None, int, dict[str, Any], dict[str, Any]]:
        del args, kwargs
        calls.append(component)
        if component == "route_pool_recombination":
            return recombined, 1, {}, {
                "objective": {"fleet_violation": 0.0, "total_distance": 202.0},
                "accepted_delta": 198.0,
                "phase_delta": 198.0,
            }
        return None, 1, {}, {}

    monkeypatch.setattr(
        cvrp_solver,
        "_main_search_component_candidate_choice",
        fake_choice,
    )

    returned, runtime = cvrp_solver.improve_with_main_search_strategy(
        current,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
    )

    assert returned.routes == recombined.routes
    assert calls == ["route_pool_recombination", "intra_route_2opt"]
    assert runtime["main_search_phase_component_order"] == {
        "global_recombination": ["route_pool_recombination"],
    }
    assert runtime["main_search_component_skip_reasons"]["intra_route_2opt"] == {
        "no_improving_candidate": 1,
    }


def test_main_search_strategy_respects_explicit_route_pool_disabled_role() -> None:
    instance = CvrpInstance(
        name="disabled_route_pool",
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
                    "route_pool_recombination": "disabled",
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
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert audit["main_search_component_roles"]["route_pool_recombination"] == "disabled"


def test_main_search_strategy_route_pool_recombination_records_phase_improvement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="route_pool_main_search",
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
    recombined = CvrpSolution(routes=((1, 2), (3, 4)))
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "construction": {
                "methods": ["nearest_neighbor"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.75, "params": {}},
            "improvement": {
                "enabled_components": ["route_pool_recombination"],
                "rounds": 1,
                "top_k": 32,
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

    def fake_route_pool_recombination(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[CvrpSolution, int, dict[str, Any]]:
        del args, kwargs
        return recombined, 5, {
            "route_pool_source_solutions": 3,
            "route_pool_sample_count": 2,
            "route_pool_size": 8,
            "route_pool_branch_calls": 4,
            "route_pool_recombined_routes": 2,
        }

    monkeypatch.setattr(
        cvrp_solver,
        "_best_route_pool_recombination",
        fake_route_pool_recombination,
    )

    returned, runtime = cvrp_solver.improve_with_main_search_strategy(
        current,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
    )

    assert returned.routes == recombined.routes
    assert runtime["main_search_component_accepted"]["route_pool_recombination"] == 1
    assert (
        runtime["main_search_component_phase_improvement_counts"][
            "route_pool_recombination"
        ]
        == 1
    )
    assert runtime["main_search_route_pool_source_solutions"] == 3
    assert runtime["main_search_route_pool_sample_count"] == 2
    assert runtime["main_search_route_pool_size"] == 8
    assert runtime["main_search_route_pool_branch_calls"] == 4
    assert runtime["main_search_route_pool_recombined_routes"] == 2


