from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *

def test_acceptance_restart_policy_can_reject_recovery_only_moves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="reject_recovery_only",
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
    objective_by_routes = {
        best_solution.routes: 10.0,
        worse_solution.routes: 20.0,
        recovered_solution.routes: 15.0,
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
                "enabled_components": ["route_pair_swap"],
                "rounds": 1,
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
    acceptance_policy = cvrp_solver._acceptance_restart_policy_defaults()
    cvrp_solver._normalize_acceptance_restart_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "min_distance_improvement": 0.0,
            "recovery_only_policy": "reject_recovery_only",
            "restart": {"enabled": False, "stagnation_rounds": 0, "max_restarts": 0},
            "perturbation": {
                "enabled": True,
                "schedule": "before_first_round",
                "strength": 1,
                "max_perturbations": 1,
            },
        },
        audit=acceptance_policy,
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
    ) -> tuple[CvrpSolution | None, int, dict[str, Any]]:
        del component, adapter, current_objective, top_k, mechanism_policies
        if solution.routes == worse_solution.routes:
            return recovered_solution, 1, {}
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
        acceptance_restart_policy=acceptance_policy,
    )

    assert returned.routes == best_solution.routes
    assert runtime["acceptance_restart_active"] is True
    assert runtime["recovery_only_policy"] == "reject_recovery_only"
    assert runtime["accepted_recovery_only_count"] == 0
    assert runtime["main_search_component_recovery_counts"]["route_pair_swap"] == 0
    assert runtime["main_search_component_skip_reasons"]["route_pair_swap"] == {
        "recovery_only_rejected": 1,
    }


def test_main_search_strategy_gates_destroy_repair_after_route_pair_improvement(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_route_pair_swap_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'problem_adaptation': {'component_roles': {'route_pool_recombination': 'disabled'}},",
                "        'construction': {'methods': ['sequential'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.75, 'params': {}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair', 'route_pair_swap'], 'rounds': 1, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/route_pair_swap_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]

    assert runtime["main_search_components"] == [
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert runtime["main_search_accepted_components"] == ["route_pair_swap"]
    assert runtime["main_search_component_attempts"]["bounded_destroy_repair"] == 0
    assert runtime["main_search_component_skip_reasons"]["bounded_destroy_repair"] == {
        "route_pair_phase_improved": 1,
    }


def test_main_search_strategy_bounded_destroy_repair_removes_subset_and_is_audited(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.5, 'params': {}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair'], 'rounds': 1, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert raw["objective"]["total_distance"] == 12.0
    assert runtime["main_search_selected_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_deep_components_selected"] == ["bounded_destroy_repair"]
    assert runtime["main_search_component_coverage_status"]["status"] == (
        "partial_problem_components_attempted"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == [
        "inter_route_relocate",
        "intra_route_2opt",
        "route_pair_swap",
        "route_pool_recombination",
    ]
    assert runtime["main_search_attempted_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_accepted_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_component_attempts"]["bounded_destroy_repair"] > 1
    assert runtime["main_search_component_accepted"]["bounded_destroy_repair"] == 1
    assert runtime["main_search_component_best_delta"]["bounded_destroy_repair"] == 4.0
    assert (
        runtime["main_search_component_accepted_delta_sum"]["bounded_destroy_repair"]
        == 4.0
    )
    assert (
        runtime["main_search_component_accepted_best_delta"]["bounded_destroy_repair"]
        == 4.0
    )
    assert (
        runtime["main_search_component_accepted_positive_counts"][
            "bounded_destroy_repair"
        ]
        == 1
    )
    assert runtime["main_search_component_improvement_counts"]["bounded_destroy_repair"] == 1
    assert runtime["main_search_component_removed_counts"]["bounded_destroy_repair"] >= 2
    assert (
        runtime["main_search_component_reinserted_counts"]["bounded_destroy_repair"]
        == runtime["main_search_component_removed_counts"]["bounded_destroy_repair"]
    )
    assert runtime["main_search_component_skip_reasons"]["bounded_destroy_repair"] == {}
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="main_search_strategy",
        )
        is None
    )


def test_route_pair_candidate_policy_changes_main_search_candidate_telemetry(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_route_pair_swap_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['sequential'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.5, 'params': {}},",
                "        'improvement': {'enabled_components': ['route_pair_swap'], 'rounds': 1, 'top_k': 1},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "route_pair_candidate_policy.py").write_text(
        "\n".join(
            [
                "def route_pair_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'scoring_terms': ['route_distance', 'removal_saving', 'distance_saving'],",
                "        'move_families': ['customer_swap'],",
                "        'candidate_limits': {'pair_cap': 1, 'position_cap': 2},",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/route_pair_swap_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["route_pair_surface_loaded"] is True
    assert runtime["route_pair_active"] is True
    assert runtime["route_pair_errors"] == 0
    assert runtime["route_pair_candidate_limits"] == {"pair_cap": 1, "position_cap": 2}
    assert runtime["route_pair_candidates_generated"] > 0
    assert runtime["route_pair_attempts"] == 1
    assert runtime["route_pair_accepted_phase_best"] == 1
    assert runtime["route_pair_phase_delta_sum"] == 198.0
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="route_pair_candidate_policy",
        )
        is None
    )


def test_route_pair_policy_can_activate_default_mechanism_main_search(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_route_pair_swap_case(workspace)
    (workspace / "policies" / "route_pair_candidate_policy.py").write_text(
        "\n".join(
            [
                "def route_pair_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'scoring_terms': ['route_distance', 'removal_saving', 'distance_saving'],",
                "        'move_families': ['customer_swap'],",
                "        'candidate_limits': {'pair_cap': 1, 'position_cap': 2},",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/route_pair_swap_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["main_search_strategy_active"] is True
    assert runtime["main_search_components"] == ["route_pair_swap"]
    assert runtime["route_pair_active"] is True
    assert runtime["route_pair_candidates_generated"] > 0
    assert runtime["route_pair_attempts"] > 0
    assert "default mechanism-surface main search activated" in json.dumps(
        runtime["main_search_strategy_events"]
    )
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="route_pair_candidate_policy",
        )
        is None
    )


def test_destroy_repair_policy_changes_main_search_repair_telemetry(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.5, 'params': {}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair'], 'rounds': 1, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "destroy_repair_policy.py").write_text(
        "\n".join(
            [
                "def destroy_repair_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'destroy_selectors': ['worst_removal'],",
                "        'repair_selectors': ['regret_2'],",
                "        'subset_strategy': 'single_worst',",
                "        'max_destroy_customers': 2,",
                "        'repair_budget_per_customer': 8,",
                "        'fallback_to_smaller_subsets': False,",
                "        'phase_best_preference': True,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["destroy_repair_surface_loaded"] is True
    assert runtime["destroy_repair_active"] is True
    assert runtime["destroy_repair_errors"] == 0
    assert runtime["destroy_subset_strategy"] == "single_worst"
    assert runtime["destroy_max_customers"] == 2
    assert runtime["destroy_subset_count"] >= 1
    assert runtime["destroy_repair_attempts"] > 0
    assert runtime["destroy_repair_accepted_phase_best"] == 1
    assert runtime["destroy_repair_phase_delta_sum"] == 4.0
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="destroy_repair_policy",
        )
        is None
    )


def test_destroy_repair_policy_selectors_drive_ranking_and_repair_budget() -> None:
    instance = CvrpInstance(
        name="destroy_repair_selector_semantics",
        capacity=99,
        depot=0,
        allowed_routes=2,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 100, 0, 1),
            CvrpNode(2, 0, 100, 1),
            CvrpNode(3, 100, 100, 1),
            CvrpNode(4, 1, 0, 1),
            CvrpNode(5, 2, 0, 1),
            CvrpNode(6, 3, 0, 1),
            CvrpNode(7, 10, 0, 1),
            CvrpNode(8, 20, 0, 1),
            CvrpNode(9, 30, 0, 1),
        ),
    )
    routes = [[1, 2, 3], [4, 5, 6]]
    worst_policy = {
        "destroy_repair_active": True,
        "destroy_selectors": ["worst_removal"],
    }
    diverse_policy = {
        "destroy_repair_active": True,
        "destroy_selectors": ["route_diverse_worst"],
    }

    worst_ranked = cvrp_solver._rank_destroy_repair_customers(
        routes,
        instance,
        destroy_repair_policy=worst_policy,
    )
    diverse_ranked = cvrp_solver._rank_destroy_repair_customers(
        routes,
        instance,
        destroy_repair_policy=diverse_policy,
    )

    assert [item[1] for item in worst_ranked[:2]] == [0, 0]
    assert [item[1] for item in diverse_ranked[:2]] == [0, 1]

    removed = [7, 8, 9]
    repair_base_routes = [[1, 2, 3], [4, 5, 6]]
    regret_policy = {
        "destroy_repair_active": True,
        "repair_selectors": ["regret_2"],
        "repair_budget_per_customer": 2,
    }
    cheapest_policy = {
        "destroy_repair_active": True,
        "repair_selectors": ["cheapest"],
        "repair_budget_per_customer": 2,
    }
    _routes, _attempts, regret_reinserted, regret_reason = (
        cvrp_solver._repair_destroyed_customers_with_policy(
            repair_base_routes,
            removed,
            instance,
            top_k=4,
            destroy_repair_policy=regret_policy,
        )
    )
    _routes, _attempts, cheapest_reinserted, cheapest_reason = (
        cvrp_solver._repair_destroyed_customers_with_policy(
            repair_base_routes,
            removed,
            instance,
            top_k=4,
            destroy_repair_policy=cheapest_policy,
        )
    )

    assert regret_reason == "repair_budget_exhausted"
    assert cheapest_reason == "repair_budget_exhausted"
    assert cheapest_reinserted > regret_reinserted


def test_bounded_regret_insertions_rank_globally_across_routes() -> None:
    instance = CvrpInstance(
        name="global_repair_insertion",
        capacity=99,
        depot=0,
        allowed_routes=2,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 100, 0, 1),
            CvrpNode(2, 0, 100, 1),
            CvrpNode(3, 0, 101, 1),
        ),
    )

    insertions = cvrp_solver._bounded_regret_insertions(
        [[1], [2]],
        3,
        instance,
        remaining_budget=1,
    )

    assert len(insertions) == 1
    assert insertions[0].route_index == 1
    assert insertions[0].delta == 2.0


def test_bounded_destroy_repair_preserves_budget_for_fallback_subsets() -> None:
    policy = {
        "destroy_repair_active": True,
        "repair_fallback_enabled": True,
        "repair_budget_per_customer": 4,
    }
    disabled_policy = {
        "destroy_repair_active": True,
        "repair_fallback_enabled": False,
        "repair_budget_per_customer": 4,
    }

    reserved_budget = cvrp_solver._bounded_destroy_repair_subset_budget(
        64,
        selected_count=6,
        remaining_subsets=5,
        destroy_repair_policy=policy,
    )
    unreserved_budget = cvrp_solver._bounded_destroy_repair_subset_budget(
        64,
        selected_count=6,
        remaining_subsets=5,
        destroy_repair_policy=disabled_policy,
    )

    assert 6 <= reserved_budget < 64
    assert unreserved_budget == 64


def test_bounded_destroy_repair_fallback_flag_controls_smaller_subsets() -> None:
    removable = [(float(10 - i), 0, i, i + 1) for i in range(6)]

    enabled = cvrp_solver._bounded_destroy_repair_subsets(
        removable,
        6,
        destroy_repair_policy={
            "destroy_repair_active": True,
            "repair_fallback_enabled": True,
            "destroy_subset_strategy": "single_worst",
        },
    )
    disabled = cvrp_solver._bounded_destroy_repair_subsets(
        removable,
        6,
        destroy_repair_policy={
            "destroy_repair_active": True,
            "repair_fallback_enabled": False,
            "destroy_subset_strategy": "single_worst",
        },
    )

    assert [len(subset) for subset in enabled] == [6, 4, 3, 2, 1]
    assert [len(subset) for subset in disabled] == [6]


def test_main_search_strategy_bounded_destroy_repair_accepts_formal_like_budget() -> None:
    instance = CvrpInstance(
        name="bounded_destroy_repair_formal_like",
        capacity=3,
        depot=0,
        allowed_routes=2,
        use_integer_cost=True,
        nodes=(
            CvrpNode(0, 0, 0, 0),
            CvrpNode(1, 0, 10, 1),
            CvrpNode(2, 0, 11, 1),
            CvrpNode(3, 0, 12, 1),
            CvrpNode(4, 100, 10, 1),
            CvrpNode(5, 100, 11, 1),
            CvrpNode(6, 100, 12, 1),
        ),
    )
    solution = CvrpSolution(routes=((1, 4, 2), (5, 3, 6)))
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "construction": {
                "methods": ["sequential"],
                "keep_top_k": 1,
                "bias": 0.0,
            },
            "baseline": {"time_fraction": 0.5, "params": {}},
            "improvement": {
                "enabled_components": ["bounded_destroy_repair"],
                "rounds": 5,
                "top_k": 64,
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

    improved, runtime = cvrp_solver.improve_with_main_search_strategy(
        solution,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=10.0,
        start_time=time.time(),
        main_search_strategy=audit,
    )

    assert improved != solution
    assert runtime["main_search_selected_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_attempted_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_accepted_components"] == ["bounded_destroy_repair"]
    assert runtime["main_search_component_attempts"]["bounded_destroy_repair"] >= 64
    assert runtime["main_search_component_accepted"]["bounded_destroy_repair"] == 1
    assert runtime["main_search_bounded_destroy_repair_accept_limit"] == 1
    assert runtime["main_search_component_best_delta"]["bounded_destroy_repair"] > 0.0
    assert runtime["main_search_component_removed_counts"]["bounded_destroy_repair"] >= 2
    assert (
        runtime["main_search_component_reinserted_counts"]["bounded_destroy_repair"]
        == runtime["main_search_component_removed_counts"]["bounded_destroy_repair"]
    )
    assert (
        runtime["main_search_component_skip_reasons"]["bounded_destroy_repair"].get(
            "bounded_destroy_repair_accept_limit_reached",
            0,
        )
        > 0
    )


