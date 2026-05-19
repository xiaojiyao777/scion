from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *

def test_algorithm_blueprint_surface_declares_runtime_fields_and_default_is_inactive(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "algorithm_blueprint"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert required_fields == (
        "algorithm_blueprint_loaded",
        "algorithm_blueprint_active",
        "algorithm_blueprint_errors",
        "algorithm_plan",
        "algorithm_phases_executed",
        "algorithm_construction_methods",
        "algorithm_baseline_time_fraction",
        "algorithm_operator_round_limit",
        "algorithm_post_baseline_operators_enabled",
        "algorithm_local_search_components",
        "algorithm_local_search_rounds",
        "algorithm_local_search_attempts",
        "algorithm_local_search_accepted",
        "algorithm_restart_enabled",
        "algorithm_restart_stagnation_rounds",
        "algorithm_restart_count",
        "algorithm_best_delta_by_phase",
        "algorithm_phase_runtime_ms",
        "algorithm_stop_reason",
    )
    assert set(required_fields).issubset(runtime)
    assert runtime["algorithm_blueprint_loaded"] is True
    assert runtime["algorithm_blueprint_active"] is False
    assert runtime["algorithm_plan"]["enabled"] is False
    assert runtime["algorithm_phases_executed"] == ["inactive"]
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="algorithm_blueprint",
    )
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"


def test_enabled_algorithm_blueprint_runs_package_owned_local_search_without_solver_edit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    solver_before = (workspace / "solver.py").read_text(encoding="utf-8")
    (workspace / "policies" / "algorithm_blueprint.py").write_text(
        "\n".join(
            [
                "def algorithm_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'construction_methods': ['nearest_neighbor'],",
                "        'construction_keep_top_k': 1,",
                "        'construction_bias': 0.0,",
                "        'baseline_time_fraction': 0.8,",
                "        'operator_round_limit': 0,",
                "        'post_baseline_operators_enabled': False,",
                "        'local_search': {",
                "            'enabled_components': ['intra_route_2opt'],",
                "            'rounds': 2,",
                "            'top_k': 32,",
                "        },",
                "        'restart': {'enabled': True, 'stagnation_rounds': 1},",
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
    assert raw["routes"] == [[1, 2, 3, 5, 4]]
    assert raw["objective"]["total_distance"] == 12.0
    assert runtime["algorithm_blueprint_loaded"] is True
    assert runtime["algorithm_blueprint_active"] is True
    assert runtime["algorithm_blueprint_errors"] == 0
    assert runtime["algorithm_plan"]["enabled"] is True
    assert runtime["post_baseline_operators_enabled"] is False
    assert runtime["operator_round_limit"] == 0
    assert runtime["algorithm_local_search_components"] == ["intra_route_2opt"]
    assert runtime["algorithm_local_search_attempts"] > 0
    assert runtime["algorithm_local_search_accepted"] == 1
    assert runtime["algorithm_restart_enabled"] is True
    assert runtime["algorithm_restart_stagnation_rounds"] == 1
    assert runtime["algorithm_restart_count"] == 1
    assert "construction_ensemble" in runtime["algorithm_phases_executed"]
    assert "baseline" in runtime["algorithm_phases_executed"]
    assert "local_search" in runtime["algorithm_phases_executed"]
    assert runtime["algorithm_best_delta_by_phase"]["local_search"] == 4.0
    assert runtime["operator_attempts"] == 0
    assert (
        runtime_audit_failure_from_raw(
            raw,
            problem_spec=legacy_spec,
            selected_surface="algorithm_blueprint",
        )
        is None
    )


def test_invalid_algorithm_blueprint_output_is_runtime_audit_failure(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "algorithm_blueprint.py").write_text(
        "\n".join(
            [
                "def algorithm_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'construction_methods': ['nearest_neighbor'],",
                "        'construction_keep_top_k': 1,",
                "        'construction_bias': 0.0,",
                "        'baseline_time_fraction': 0.8,",
                "        'operator_round_limit': 0,",
                "        'post_baseline_operators_enabled': False,",
                "        'local_search': {'enabled_components': ['unknown_move'], 'rounds': 1, 'top_k': 8},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0},",
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
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="algorithm_blueprint",
    )

    assert raw["runtime"]["algorithm_blueprint_errors"] == 1
    assert raw["runtime"]["algorithm_blueprint_active"] is False
    assert raw["runtime"]["algorithm_stop_reason"] == "invalid_plan"
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"
    assert "algorithm_blueprint_errors" in issue["detail"]
    assert "unknown_move" in json.dumps(raw["runtime"]["algorithm_blueprint_events"])


def test_default_main_search_strategy_policy_matches_contract_gate_interface() -> None:
    spec = load_problem_spec_v1_from_yaml(CVRP_DIR / "problem-v1.yaml")
    gate = ContractGate(legacy_problem_spec_from_v1(spec))
    policy_path = CVRP_DIR / "policies" / "main_search_strategy.py"

    result = gate.validate_patch(
        PatchProposal(
            file_path="policies/main_search_strategy.py",
            action="modify",
            code_content=policy_path.read_text(encoding="utf-8"),
        )
    )

    c7 = next(check for check in result.checks if check.name == "C7_interface")
    assert c7.passed, c7.detail


def test_main_search_strategy_surface_declares_runtime_fields_and_default_is_inactive(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "main_search_strategy"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert "main_search_strategy_loaded" in required_fields
    assert "main_search_strategy_errors" in required_fields
    assert "main_search_problem_adaptation" in required_fields
    assert "main_search_algorithm_body" in required_fields
    assert "main_search_algorithm_body_source" in required_fields
    assert "main_search_strategy_family" in required_fields
    assert "main_search_instance_profile" in required_fields
    assert "main_search_component_roles" in required_fields
    assert "main_search_component_order" in required_fields
    assert "main_search_phase_component_order" in required_fields
    assert "main_search_evidence_targets" in required_fields
    assert "main_search_selected_components" in required_fields
    assert "main_search_attempted_components" in required_fields
    assert "main_search_component_coverage_status" in required_fields
    assert "main_search_deep_components_selected" in required_fields
    assert "main_search_component_attempts" in required_fields
    assert "main_search_component_skip_reasons" in required_fields
    assert "main_search_component_repair_fallback_counts" in required_fields
    assert "main_search_baseline_time_fraction_effective" in required_fields
    assert "main_search_baseline_budget_policy" in required_fields
    assert "main_search_baseline_quality_guard_applied" in required_fields
    assert "main_search_baseline_params_clamped" in required_fields
    assert "main_search_baseline_param_clamps" in required_fields
    assert "main_search_component_min_distance_improvement" in required_fields
    assert "main_search_bounded_destroy_repair_accept_limit" in required_fields
    assert "main_search_best_returned" in required_fields
    assert "main_search_objective_trace" in required_fields
    assert "main_search_component_accepted_delta_sum" in required_fields
    assert "main_search_component_accepted_best_delta" in required_fields
    assert "main_search_component_accepted_positive_counts" in required_fields
    assert "main_search_component_recovery_delta_sum" in required_fields
    assert "main_search_component_recovery_best_delta" in required_fields
    assert "main_search_component_recovery_counts" in required_fields
    assert "main_search_component_phase_delta_sum" in required_fields
    assert "main_search_component_phase_best_delta" in required_fields
    assert "main_search_component_phase_improvement_counts" in required_fields
    assert "main_search_component_top_k_effective" in required_fields
    assert "main_search_construction_pool_size" in required_fields
    assert "main_search_construction_pool_distances" in required_fields
    assert "main_search_route_pool_source_solutions" in required_fields
    assert "main_search_route_pool_sample_count" in required_fields
    assert "main_search_route_pool_size" in required_fields
    assert "main_search_route_pool_branch_calls" in required_fields
    assert "main_search_route_pool_recombined_routes" in required_fields
    assert "main_search_route_pool_auto_added" in required_fields
    assert "main_search_route_pool_invocations" in required_fields
    assert "main_search_route_pool_activation" in required_fields
    assert "main_search_route_pool_min_customers" in required_fields
    assert "main_search_route_pool_max_rounds" in required_fields
    assert "main_search_local_cleanup_after_recombination" in required_fields
    assert "main_search_adaptive_component_budget" in required_fields
    assert "main_search_perturbation_schedule" in required_fields
    assert set(required_fields).issubset(runtime)
    assert runtime["main_search_strategy_loaded"] is True
    assert runtime["main_search_strategy_active"] is False
    assert runtime["main_search_plan"]["enabled"] is False
    assert runtime["main_search_strategy_family"] == "balanced_lifecycle"
    assert runtime["main_search_problem_adaptation_source"] == "declared"
    assert runtime["main_search_algorithm_body_source"] == "declared"
    assert runtime["main_search_algorithm_body"]["route_pool_activation"] == "adaptive"
    assert runtime["main_search_route_pool_auto_added"] is False
    assert runtime["main_search_route_pool_invocations"] == 0
    assert runtime["main_search_route_pool_min_customers"] == 80
    assert runtime["main_search_route_pool_max_rounds"] == 8
    assert runtime["main_search_phases"] == ["inactive"]
    assert runtime["main_search_component_coverage_status"]["status"] == "inactive"
    assert runtime["main_search_deep_components_selected"] == []
    assert runtime["main_search_baseline_quality_guard_applied"] is False
    assert runtime["main_search_baseline_params_clamped"] is False
    assert runtime["main_search_baseline_param_clamps"]["applied"] is False
    assert runtime["main_search_baseline_param_clamps"]["status"] == "no_clamps"
    assert runtime["main_search_best_returned"] is False
    assert runtime["main_search_objective_trace"]["status"] == "inactive"
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="main_search_strategy",
    )
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"
    assert "main_search_strategy_active" in issue["failed_runtime_fields"]


def test_solver_algorithm_surface_declares_runtime_fields_and_default_is_inactive(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(workspace, "data/operator_case.json")
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "solver_design"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)

    assert "solver_algorithm_loaded" in required_fields
    assert "solver_algorithm_active" in required_fields
    assert "solver_algorithm_phase_runtime_ms" in required_fields
    assert set(required_fields).issubset(runtime)
    assert runtime["solver_algorithm_path"] == "policies/solver_algorithm.py"
    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is False
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_stop_reason"] == "inactive"
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    )
    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"
    assert "solver_algorithm_active" in issue["failed_runtime_fields"]


def test_selected_solver_design_runs_checked_in_baseline_algorithm(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]

    assert runtime["solver_algorithm_path"] == "policies/baseline_algorithm.py"
    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_solution_valid"] is True
    assert runtime["solver_algorithm_solution_routes"] >= 1
    assert raw["feasible"] is True


def test_solver_algorithm_exception_surfaces_runtime_audit_error(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "solver_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    raise RuntimeError('candidate solver failed')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(workspace, "data/operator_case.json")
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is False
    assert runtime["solver_algorithm_errors"] == 1
    assert "candidate solver failed" in json.dumps(
        runtime["solver_algorithm_events"]
    )
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    )
    assert issue is not None
    assert issue["error_category"] == "solver_algorithm_runtime_error"
    assert issue["solver_algorithm_errors"] == 1
    assert "candidate solver failed" in json.dumps(
        issue["solver_algorithm_events"]
    )


def test_solver_design_baseline_algorithm_exception_reports_actual_policy_path(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "ENABLE_BASELINE_ALGORITHM = True",
                "",
                "def solve(instance, rng, time_limit_sec, context):",
                "    raise RuntimeError('baseline body failed')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]

    assert runtime["solver_algorithm_errors"] == 1
    assert runtime["solver_algorithm_events"][0]["policy"] == (
        "policies/baseline_algorithm.py"
    )
    assert "baseline body failed" in runtime["solver_algorithm_events"][0]["detail"]


def test_enabled_solver_algorithm_returns_valid_solution_and_skips_legacy_loop(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "solver_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    start = context.elapsed_ms()",
                "    solution = context.nearest_neighbor()",
                "    context.record_phase('construct', context.elapsed_ms() - start)",
                "    return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "search_policy.py").write_text(
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    raise RuntimeError('legacy search policy should not run')\n",
        encoding="utf-8",
    )
    (workspace / "policies" / "construction_policy.py").write_text(
        "def construction_mode(instance, time_limit_sec):\n"
        "    raise RuntimeError('legacy construction policy should not run')\n",
        encoding="utf-8",
    )

    raw = _run_solver(workspace, "data/operator_case.json")
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_solution_valid"] is True
    assert runtime["solver_algorithm_solution_routes"] >= 1
    assert runtime["solver_algorithm_total_distance"] > 0
    assert runtime["solver_algorithm_stop_reason"] == "completed"
    assert "construct" in runtime["solver_algorithm_phase_runtime_ms"]
    assert "inactive" not in runtime["solver_algorithm_phase_runtime_ms"]
    assert runtime["policy_loaded"] is False
    assert runtime["construction_surface_loaded"] is False
    assert runtime["main_search_strategy_active"] is False
    assert runtime["algorithm_blueprint_active"] is False
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    ) is None


def test_enabled_baseline_algorithm_is_preferred_over_legacy_solver_hook(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "ENABLE_BASELINE_ALGORITHM = True",
                "",
                "def solve(instance, rng, time_limit_sec, context):",
                "    solution = context.nearest_neighbor()",
                "    context.record_iteration('preferred_body', 1)",
                "    context.record_move('preferred_body', attempted=1, accepted=1)",
                "    context.set_stop_reason('preferred_completed')",
                "    return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "policies" / "solver_algorithm.py").write_text(
        "def solve(instance, rng, time_limit_sec, context):\n"
        "    raise RuntimeError('legacy solver hook should not run')\n",
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]

    assert runtime["solver_algorithm_path"] == "policies/baseline_algorithm.py"
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_solution_valid"] is True
    assert runtime["solver_algorithm_stop_reason"] == "preferred_completed"
    assert runtime["solver_algorithm_search_iterations"] == 1
    assert runtime["solver_algorithm_accepted_moves"] == 1
    assert runtime["solver_algorithm_neutral_accepted_moves"] == 1
    assert runtime["solver_algorithm_improving_moves"] == 0
    assert "legacy solver hook should not run" not in json.dumps(
        runtime["solver_algorithm_events"]
    )


def test_solver_algorithm_context_accepts_baseline_alias_and_objective_comparison(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "solver_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    seed = context.nearest_neighbor()",
                "    baseline = context.baseline(seed, time_limit_sec=0.1)",
                "    seed_obj = context.objective(seed)",
                "    baseline_obj = context.objective(baseline)",
                "    context.record_iteration('baseline_probe', 1)",
                "    context.record_move('baseline_probe', attempted=1, accepted=0)",
                "    if baseline_obj <= seed_obj and baseline_obj[0] <= seed_obj[0]:",
                "        context.record_phase('baseline_alias', 1)",
                "        return baseline",
                "    return seed",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(workspace, "data/operator_case.json")
    runtime = raw["runtime"]

    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_baseline_calls"] == 1
    assert runtime["solver_algorithm_search_iterations"] == 1
    assert runtime["solver_algorithm_move_attempts"] == 1
    assert runtime["solver_algorithm_accepted_moves"] == 0
    assert runtime["solver_algorithm_neutral_accepted_moves"] == 0
    assert runtime["solver_algorithm_improving_moves"] == 0
    assert runtime["solver_algorithm_phase_improvement_counts"]["baseline_probe"] == 0
    assert runtime["solver_algorithm_solution_valid"] is True
    assert "baseline_alias" in runtime["solver_algorithm_phase_runtime_ms"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    ) is None


