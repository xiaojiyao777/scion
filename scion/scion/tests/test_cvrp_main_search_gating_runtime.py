from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *

def test_main_search_strategy_does_not_gate_bdr_after_non_phase_route_pair_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="phase_best_guard",
        capacity=10,
        depot=0,
        allowed_routes=1,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 1, 0, 1),
            CvrpNode(2, 2, 0, 1),
            CvrpNode(3, 3, 0, 1),
        ),
    )
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    best_solution = CvrpSolution(routes=((1,),))
    worse_solution = CvrpSolution(routes=((2,),))
    recovered_solution = CvrpSolution(routes=((3,),))
    improved_solution = CvrpSolution(routes=((1, 2, 3),))
    objective_by_routes = {
        best_solution.routes: 10.0,
        worse_solution.routes: 20.0,
        recovered_solution.routes: 15.0,
        improved_solution.routes: 8.0,
    }
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
                "enabled_components": [
                    "route_pair_swap",
                    "bounded_destroy_repair",
                ],
                "rounds": 2,
                "top_k": 8,
            },
            "acceptance": {"min_distance_improvement": 0.0},
            "restart": {
                "enabled": False,
                "stagnation_rounds": 0,
                "max_restarts": 0,
            },
            "perturbation": {
                "enabled": True,
                "strength": 1,
                "max_perturbations": 1,
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )

    def fake_objective(
        _adapter: CvrpAdapter,
        _instance: CvrpInstance,
        solution: CvrpSolution,
    ) -> dict[str, int | float]:
        return {
            "fleet_violation": 0,
            "total_distance": objective_by_routes[solution.routes],
        }

    def fake_component_candidate(
        component: str,
        solution: CvrpSolution,
        _instance: CvrpInstance,
        *,
        adapter: CvrpAdapter,
        current_objective: dict[str, int | float],
        top_k: int,
        mechanism_policies: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
        del adapter, current_objective, top_k, mechanism_policies, kwargs
        if solution.routes == best_solution.routes:
            return None, 1, {}
        if component == "route_pair_swap" and solution.routes == worse_solution.routes:
            return recovered_solution, 1, {}
        if (
            component == "bounded_destroy_repair"
            and solution.routes == recovered_solution.routes
        ):
            return improved_solution, 1, {
                "removed_count": 2,
                "reinserted_count": 2,
                "repair_fallback_count": 0,
            }
        return None, 1, {}

    monkeypatch.setattr(cvrp_solver, "_objective_for_solution", fake_objective)
    monkeypatch.setattr(cvrp_solver, "_solution_is_valid", lambda *args: (True, ""))
    monkeypatch.setattr(
        cvrp_solver,
        "_perturb_solution",
        lambda *args, **kwargs: worse_solution,
    )
    monkeypatch.setattr(
        cvrp_solver,
        "_main_search_component_candidate",
        fake_component_candidate,
    )

    returned, runtime = cvrp_solver.improve_with_main_search_strategy(
        best_solution,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.perf_counter(),
        main_search_strategy=audit,
    )

    assert returned.routes == improved_solution.routes
    assert runtime["main_search_component_accepted"]["route_pair_swap"] == 1
    assert runtime["main_search_component_accepted"]["bounded_destroy_repair"] == 1
    assert (
        runtime["main_search_component_skip_reasons"]["bounded_destroy_repair"].get(
            "route_pair_phase_improved",
            0,
        )
        == 0
    )
    assert runtime["main_search_component_phase_delta_sum"]["route_pair_swap"] == 0.0
    assert runtime["main_search_component_recovery_counts"]["route_pair_swap"] == 1
    assert runtime["main_search_component_recovery_delta_sum"]["route_pair_swap"] == 5.0
    assert runtime["main_search_component_recovery_best_delta"]["route_pair_swap"] == 5.0
    assert (
        runtime["main_search_component_phase_delta_sum"]["bounded_destroy_repair"]
        == 2.0
    )
    assert (
        runtime["main_search_component_recovery_counts"]["bounded_destroy_repair"]
        == 0
    )
    assert (
        runtime["main_search_component_phase_improvement_counts"][
            "bounded_destroy_repair"
        ]
        == 1
    )
    assert runtime["main_search_objective_delta_by_phase"]["improvement_loop"] == 2.0
    assert runtime["main_search_objective_trace"]["accepted_but_zero_phase_delta"] == {
        "route_pair_swap": 1,
    }
    assert runtime["main_search_objective_trace"]["recovery_count_by_component"][
        "route_pair_swap"
    ] == 1


