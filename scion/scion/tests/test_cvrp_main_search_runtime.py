from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *

def test_enabled_main_search_strategy_runs_owned_main_loop_and_disables_registry_by_default(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    solver_before = (workspace / "solver.py").read_text(encoding="utf-8")
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor', 'sequential'], 'keep_top_k': 2, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.5, 'params': {'destroy_ratio': (0.05, 0.20), 'use_vns': False, 'max_destroy_customers': 16}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair', 'intra_route_2opt'], 'rounds': 3, 'top_k': 64},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': True, 'stagnation_rounds': 1, 'max_restarts': 1},",
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

    assert (workspace / "solver.py").read_text(encoding="utf-8") == solver_before
    assert raw["objective"]["total_distance"] == 12.0
    assert runtime["main_search_strategy_loaded"] is True
    assert runtime["main_search_strategy_active"] is True
    assert runtime["main_search_strategy_errors"] == 0
    assert runtime["main_search_plan"]["enabled"] is True
    assert runtime["baseline_time_fraction"] == 0.5
    assert runtime["main_search_baseline_time_fraction_effective"] == 0.5
    assert runtime["main_search_baseline_quality_guard_applied"] is False
    assert runtime["main_search_baseline_params_clamped"] is False
    assert runtime["main_search_baseline_param_clamps"] == {
        "applied": False,
        "status": "no_clamps",
        "count": 0,
        "fields": [],
        "clamps": {},
    }
    assert runtime["baseline_policy_params"]["destroy_ratio"] == [0.05, 0.2]
    assert runtime["baseline_use_vns"] is False
    assert runtime["post_baseline_operators_enabled"] is False
    assert runtime["operator_round_limit"] == 0
    assert runtime["main_search_components"] == [
        "bounded_destroy_repair",
        "intra_route_2opt",
    ]
    assert runtime["main_search_selected_components"] == [
        "bounded_destroy_repair",
        "intra_route_2opt",
    ]
    assert runtime["main_search_deep_components_selected"] == [
        "bounded_destroy_repair",
        "intra_route_2opt",
    ]
    assert runtime["main_search_component_coverage_status"]["status"] == (
        "partial_problem_components_attempted"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == [
        "inter_route_relocate",
        "route_pair_swap",
        "route_pool_recombination",
    ]
    assert runtime["main_search_attempted_components"] == [
        "bounded_destroy_repair",
        "intra_route_2opt",
    ]
    assert runtime["main_search_component_attempts"]["intra_route_2opt"] > 0
    assert sum(runtime["main_search_component_accepted"].values()) == 1
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
    assert (
        runtime["main_search_component_min_distance_improvement"][
            "bounded_destroy_repair"
        ]
        == 1.0
    )
    assert runtime["main_search_component_removed_counts"]["bounded_destroy_repair"] >= 2
    assert (
        runtime["main_search_component_reinserted_counts"]["bounded_destroy_repair"]
        == runtime["main_search_component_removed_counts"]["bounded_destroy_repair"]
    )
    assert set(runtime["main_search_skipped_components"]) == {
        "bounded_destroy_repair",
        "intra_route_2opt",
    }
    assert "no_improving_candidate" in json.dumps(
        runtime["main_search_component_skip_reasons"]
    )
    assert runtime["main_search_restart_enabled"] is True
    assert runtime["main_search_restart_count"] == 1
    assert "construction" in runtime["main_search_phases"]
    assert "baseline" in runtime["main_search_phases"]
    assert "improvement_loop" in runtime["main_search_phases"]
    assert runtime["main_search_objective_delta_by_phase"]["improvement_loop"] == 4.0
    assert runtime["main_search_component_phase_delta_sum"]["bounded_destroy_repair"] == 4.0
    assert runtime["main_search_component_phase_best_delta"]["bounded_destroy_repair"] == 4.0
    assert (
        runtime["main_search_component_phase_improvement_counts"][
            "bounded_destroy_repair"
        ]
        == 1
    )
    assert runtime["main_search_best_returned"] is True
    assert runtime["main_search_objective_trace"]["status"] == "returned_best"
    assert runtime["main_search_objective_trace"]["phase_delta"] == 4.0
    assert (
        runtime["main_search_objective_trace"]["phase_delta_sum_by_component"][
            "bounded_destroy_repair"
        ]
        == 4.0
    )
    assert runtime["main_search_objective_trace"]["accepted_but_zero_phase_delta"] == {}
    assert runtime["operator_attempts"] == 0
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="main_search_strategy",
        )
        is None
    )
    v5 = check_state_mutation(
        legacy_spec,
        _runner(),
        str(workspace),
        adapter=CvrpAdapter(_Spec()),  # type: ignore[arg-type]
        selected_surface="main_search_strategy",
    )
    assert v5.passed, v5.detail
    missing_field_raw = json.loads(json.dumps(raw))
    del missing_field_raw["runtime"]["main_search_baseline_param_clamps"]
    missing_issue = runtime_audit_failure_from_raw(
        missing_field_raw,
        problem_spec=legacy_spec,
        selected_surface="main_search_strategy",
    )
    assert missing_issue is not None
    assert missing_issue["error_category"] == "surface_runtime_contract_error"
    assert "main_search_baseline_param_clamps" in (
        missing_issue["missing_runtime_fields"]
    )


def test_main_search_strategy_records_clamp_details_in_selected_surface_runtime(
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
                "        'baseline': {'time_fraction': 0.75, 'params': {'destroy_ratio': (0.05, 0.50), 'segment_length': 400, 'reaction_factor': 0.05, 'vns_max_no_improve': 10000, 'max_destroy_customers': 200}},",
                "        'improvement': {'enabled_components': ['bounded_destroy_repair', 'intra_route_2opt'], 'rounds': 3, 'top_k': 64},",
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

    assert runtime["main_search_baseline_params_clamped"] is True
    clamp_evidence = runtime["main_search_baseline_param_clamps"]
    assert clamp_evidence["applied"] is True
    assert clamp_evidence["status"] == "clamped"
    assert set(clamp_evidence["fields"]) == {
        "destroy_ratio",
        "segment_length",
        "reaction_factor",
        "vns_max_no_improve",
        "max_destroy_customers",
    }
    assert clamp_evidence["clamps"]["destroy_ratio"] == {
        "requested": [0.05, 0.5],
        "effective": [0.05, 0.35],
    }
    assert clamp_evidence["clamps"]["max_destroy_customers"] == {
        "requested": 200,
        "effective": 16,
    }
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="main_search_strategy",
        )
        is None
    )


def test_main_search_strategy_runtime_marks_both_deep_components_attempted(
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
                "        'improvement': {'enabled_components': ['route_pair_swap', 'bounded_destroy_repair'], 'rounds': 1, 'top_k': 64},",
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

    assert runtime["main_search_selected_components"] == [
        "route_pool_recombination",
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert runtime["main_search_attempted_components"] == [
        "route_pool_recombination",
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert runtime["main_search_deep_components_selected"] == [
        "route_pool_recombination",
        "route_pair_swap",
        "bounded_destroy_repair",
    ]
    assert runtime["main_search_component_coverage_status"]["status"] == (
        "partial_problem_components_attempted"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == [
        "inter_route_relocate",
        "intra_route_2opt",
    ]
    assert runtime["main_search_component_coverage_status"]["unattempted_deep_components"] == []
    assert runtime["main_search_component_attempts"]["route_pool_recombination"] > 0
    assert runtime["main_search_component_attempts"]["route_pair_swap"] == 0
    assert runtime["main_search_component_attempts"]["bounded_destroy_repair"] > 1
    assert runtime["main_search_component_skip_reasons"].get(
        "route_pool_recombination",
        {},
    ) in ({}, {"route_pool_no_improvement": 1})
    assert runtime["main_search_component_skip_reasons"]["route_pair_swap"] == {
        "no_candidates": 1,
    }
    assert (
        runtime["main_search_component_accepted"]["route_pool_recombination"]
        + runtime["main_search_component_accepted"]["bounded_destroy_repair"]
        >= 1
    )
    assert (
        runtime["main_search_component_accepted_delta_sum"]["route_pool_recombination"]
        + runtime["main_search_component_accepted_delta_sum"]["bounded_destroy_repair"]
        > 0.0
    )


def test_main_search_strategy_route_pair_swap_is_ranked_attempted_and_accepted(
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

    raw = _run_solver(
        workspace,
        "data/route_pair_swap_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert {frozenset(route) for route in raw["routes"]} == {
        frozenset((1, 3)),
        frozenset((2, 4)),
    }
    assert raw["objective"]["total_distance"] == 224.0
    assert runtime["main_search_selected_components"] == ["route_pair_swap"]
    assert runtime["main_search_deep_components_selected"] == ["route_pair_swap"]
    assert runtime["main_search_component_coverage_status"]["status"] == (
        "partial_problem_components_attempted"
    )
    assert runtime["main_search_component_coverage_status"]["missing_deep_components"] == [
        "bounded_destroy_repair",
        "inter_route_relocate",
        "intra_route_2opt",
        "route_pool_recombination",
    ]
    assert runtime["main_search_attempted_components"] == ["route_pair_swap"]
    assert runtime["main_search_accepted_components"] == ["route_pair_swap"]
    assert runtime["main_search_component_attempts"]["route_pair_swap"] == 1
    assert runtime["main_search_component_accepted"]["route_pair_swap"] == 1
    assert runtime["main_search_component_best_delta"]["route_pair_swap"] == 198.0
    assert runtime["main_search_component_accepted_delta_sum"]["route_pair_swap"] == 198.0
    assert runtime["main_search_component_accepted_best_delta"]["route_pair_swap"] == 198.0
    assert runtime["main_search_component_accepted_positive_counts"]["route_pair_swap"] == 1
    assert runtime["main_search_component_improvement_counts"]["route_pair_swap"] == 1
    assert runtime["main_search_component_skip_reasons"]["route_pair_swap"] == {}
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="main_search_strategy",
        )
        is None
    )


def test_main_search_strategy_returns_best_even_after_worse_perturbation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    instance = adapter.load_instance(str(workspace / "data/operator_case.json"))
    best_solution = CvrpSolution(routes=((1, 2, 3, 5, 4),))
    worse_solution = CvrpSolution(routes=((1, 2, 3, 4, 5),))
    (workspace / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'algorithm_body': {'phase_sequence': ['construction', 'baseline', 'global_recombination', 'route_structure_repair', 'local_cleanup'], 'route_pool_activation': 'adaptive', 'route_pool_min_customers': 80, 'route_pool_max_rounds': 8, 'local_cleanup_after_recombination': False, 'adaptive_component_budget': True},",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.75, 'params': {}},",
                "        'improvement': {'enabled_components': ['route_pair_swap'], 'rounds': 2, 'top_k': 8},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': True, 'strength': 1, 'max_perturbations': 1},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    main_search_strategy = cvrp_solver._load_main_search_strategy(
        workspace_root=workspace,
        instance=instance,
        time_limit_sec=2.0,
    )
    monkeypatch.setattr(
        cvrp_solver,
        "_perturb_solution",
        lambda *args, **kwargs: worse_solution,
    )

    returned, audit = cvrp_solver.improve_with_main_search_strategy(
        best_solution,
        instance,
        adapter=adapter,
        rng=random.Random(7),
        time_limit_sec=2.0,
        start_time=time.perf_counter(),
        main_search_strategy=main_search_strategy,
    )

    returned_objective = cvrp_solver._objective_for_solution(adapter, instance, returned)
    best_objective = cvrp_solver._objective_for_solution(adapter, instance, best_solution)
    worse_objective = cvrp_solver._objective_for_solution(adapter, instance, worse_solution)
    assert returned.routes == best_solution.routes
    assert returned_objective == best_objective
    assert worse_objective["total_distance"] > best_objective["total_distance"]
    assert audit["main_search_perturbation_count"] == 1
    assert audit["main_search_best_returned"] is True


def test_main_search_strategy_can_perturb_before_first_round(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    adapter = CvrpAdapter(_Spec())  # type: ignore[arg-type]
    instance = adapter.load_instance(str(workspace / "data/operator_case.json"))
    best_solution = CvrpSolution(routes=((1, 2, 3, 5, 4),))
    perturbed_solution = CvrpSolution(routes=((1, 2, 3, 4, 5),))
    audit = cvrp_solver._main_search_strategy_defaults()
    cvrp_solver._normalize_main_search_strategy_plan(
        {
            "enabled": True,
            "algorithm_body": _default_algorithm_body(),
            "problem_adaptation": {
                "component_roles": {"route_pool_recombination": "disabled"},
            },
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
                "schedule": "before_first_round",
            },
            "post_baseline_operators_enabled": False,
            "operator_round_limit": 0,
        },
        instance=instance,
        audit=audit,
    )
    seen_current: list[CvrpSolution] = []
    monkeypatch.setattr(
        cvrp_solver,
        "_perturb_solution",
        lambda *args, **kwargs: perturbed_solution,
    )

    def fake_candidate_choice(
        component: str,
        _instance: CvrpInstance,
        *,
        current_solution: CvrpSolution,
        best_solution: CvrpSolution,
        adapter: CvrpAdapter,
        current_objective: dict[str, int | float],
        best_objective: dict[str, int | float],
        top_k: int,
        min_distance_improvement: float,
        mechanism_policies: dict[str, Any] | None = None,
    ) -> tuple[None, int, dict[str, Any], dict[str, Any]]:
        del (
            component,
            _instance,
            best_solution,
            adapter,
            current_objective,
            best_objective,
            top_k,
            min_distance_improvement,
            mechanism_policies,
        )
        seen_current.append(current_solution)
        return None, 1, {}, {}

    monkeypatch.setattr(
        cvrp_solver,
        "_main_search_component_candidate_choice",
        fake_candidate_choice,
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

    assert returned.routes == best_solution.routes
    assert seen_current and seen_current[0].routes == perturbed_solution.routes
    assert runtime["main_search_perturbation_schedule"] == "before_first_round"
    assert runtime["main_search_perturbation_count"] == 1
    assert "pre_improvement_perturbation" in runtime["main_search_phases"]
    assert runtime["main_search_best_returned"] is True
