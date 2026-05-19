"""Focused tests split from test_protocol.py."""

from .protocol_test_support import *  # noqa: F401,F403

def test_run_experiment_selected_surface_runtime_fields_fail_closed(tmp_path):
    runner = MagicMock()
    champ = _make_run_result(2, 1000, runtime={})
    cand = _make_run_result(
        1,
        900,
        runtime={"dispatch_loaded": True},
    )
    runner.run_solver.side_effect = [champ, cand] * 4
    proto = _make_protocol(
        runner,
        tmp_path,
        problem_spec=_surface_problem_spec(),
    )

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        "/cand",
        "/champ",
        "modify",
        selected_surface="dispatch_policy",
    )

    assert result.gate_outcome == "fail"
    assert result.stats.failed_pairs == 4
    assert result.stats.candidate_failed_pairs == 4
    assert result.candidate_runtime_failure_categories == {
        "surface_contract_error": 4,
    }
    assert result.candidate_first_runtime_failure is not None
    assert result.candidate_first_runtime_failure["surface"] == "dispatch_policy"
    assert "dispatch_errors" in result.candidate_first_runtime_failure["detail_summary"]
    surface_summary = result.candidate_surface_runtime_summary
    assert surface_summary["candidate_pairs"] == 4
    assert surface_summary["fields"]["dispatch_loaded"]["present"] == 4
    assert surface_summary["fields"]["dispatch_errors"]["missing"] == 4
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["selected_surface"] == "dispatch_policy"
    assert raw["candidate_surface_runtime_summary"] == surface_summary


def test_run_experiment_preserves_selected_surface_required_runtime_metrics(
    tmp_path,
):
    runner = MagicMock()
    required_fields = (
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
    candidate_runtime = {
        "algorithm_blueprint_loaded": True,
        "algorithm_blueprint_active": True,
        "algorithm_blueprint_errors": 0,
        "algorithm_plan": {
            "enabled": True,
            "baseline_time_fraction": 0.75,
        },
        "algorithm_phases_executed": [
            "plan_loaded",
            "construction_ensemble",
            "baseline",
            "local_search",
        ],
        "algorithm_construction_methods": ["nearest_neighbor", "demand_descending"],
        "algorithm_baseline_time_fraction": 0.75,
        "algorithm_operator_round_limit": 0,
        "algorithm_post_baseline_operators_enabled": False,
        "algorithm_local_search_components": [
            "intra_route_2opt",
            "inter_route_relocate",
        ],
        "algorithm_local_search_rounds": 2,
        "algorithm_local_search_attempts": 12,
        "algorithm_local_search_accepted": 1,
        "algorithm_restart_enabled": True,
        "algorithm_restart_stagnation_rounds": 8,
        "algorithm_restart_count": 1,
        "algorithm_best_delta_by_phase": {"local_search": 4.0},
        "algorithm_phase_runtime_ms": {"local_search": 7},
        "algorithm_stop_reason": "no_improvement_round",
    }
    pair = [
        _make_run_result(2, 1000, elapsed_ms=100, runtime={}),
        _make_run_result(1, 900, elapsed_ms=125, runtime=candidate_runtime),
    ]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(
        runner,
        tmp_path,
        problem_spec=_surface_problem_spec(
            name="algorithm_blueprint",
            required_runtime_fields=required_fields,
        ),
    )

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        "/cand",
        "/champ",
        "modify",
        selected_surface="algorithm_blueprint",
    )

    assert result.selected_surface == "algorithm_blueprint"
    summary = result.candidate_surface_runtime_summary
    assert summary["selected_surface"] == "algorithm_blueprint"
    assert summary["candidate_pairs"] == 4
    assert summary["fields"]["algorithm_plan"]["present"] == 4
    assert summary["fields"]["algorithm_phases_executed"]["present"] == 4
    assert summary["fields"]["algorithm_blueprint_errors"]["failed"] == 0
    accepted_numeric = summary["fields"]["algorithm_local_search_accepted"][
        "numeric_summary"
    ]["scalar"]
    assert accepted_numeric["observed_count"] == 4
    assert accepted_numeric["weighted_sum"] == 4.0
    assert accepted_numeric["positive_count"] == 4
    delta_numeric = summary["fields"]["algorithm_best_delta_by_phase"][
        "numeric_summary"
    ]["mapping"]["local_search"]
    assert delta_numeric["observed_count"] == 4
    assert delta_numeric["weighted_sum"] == 16.0
    assert delta_numeric["positive_count"] == 4

    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["candidate_surface_runtime_summary"] == summary
    candidate_runtime_metrics = raw["pairs"][0]["candidate_runtime"]
    assert candidate_runtime_metrics["algorithm_plan"] == {
        "baseline_time_fraction": 0.75,
        "enabled": True,
    }
    assert candidate_runtime_metrics["algorithm_phases_executed"] == [
        "plan_loaded",
        "construction_ensemble",
        "baseline",
        "local_search",
    ]
    assert candidate_runtime_metrics["algorithm_local_search_components"] == [
        "intra_route_2opt",
        "inter_route_relocate",
    ]


def test_run_experiment_fails_closed_on_declared_zero_activity_probe(tmp_path):
    runner = MagicMock()
    candidate_runtime = {
        "generic_solver_loaded": True,
        "generic_solver_active": True,
        "generic_solver_errors": 0,
        "generic_solver_search_iterations": 0,
    }
    champion_runtime = {
        "generic_solver_search_iterations": 8,
    }
    pair = [
        _make_run_result(2, 1000, elapsed_ms=100, runtime=champion_runtime),
        _make_run_result(1, 900, elapsed_ms=125, runtime=candidate_runtime),
    ]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(
        runner,
        tmp_path,
        problem_spec=_surface_problem_spec(
            name="generic_solver",
            required_runtime_fields=(
                "generic_solver_loaded",
                "generic_solver_active",
                "generic_solver_errors",
                "generic_solver_search_iterations",
            ),
        ),
    )

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        "/cand",
        "/champ",
        "modify",
        selected_surface="generic_solver",
        expected_telemetry={"activity": ["generic_solver_search_iterations"]},
    )

    assert result.gate_outcome == "fail"
    assert "TELEMETRY_GUARD_FAILED" in result.reason_codes
    assert "TELEMETRY_ACTIVITY_NOT_OBSERVED" in result.reason_codes
    guard = result.candidate_surface_runtime_summary["telemetry_guard"]
    assert guard["passed"] is False
    assert guard["failures"][0]["field"] == "generic_solver_search_iterations"
    assert "telemetry_guard=" in result.exposed_summary


def test_run_experiment_fails_closed_on_declared_zero_activation_probe(tmp_path):
    runner = MagicMock()
    candidate_runtime = {
        "generic_solver_loaded": True,
        "generic_solver_active": True,
        "generic_solver_errors": 0,
        "mechanism_activation": {"target_probe": 0, "other_probe": 1},
        "mechanism_effect": {"target_probe": 3.0},
    }
    champion_runtime = {
        "mechanism_activation": {"target_probe": 1},
        "mechanism_effect": {"target_probe": 4.0},
    }
    pair = [
        _make_run_result(2, 1000, elapsed_ms=100, runtime=champion_runtime),
        _make_run_result(1, 900, elapsed_ms=125, runtime=candidate_runtime),
    ]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(
        runner,
        tmp_path,
        problem_spec=SimpleNamespace(
            research_surfaces=[
                SimpleNamespace(
                    name="generic_solver",
                    evidence=SimpleNamespace(
                        required_runtime_fields=[
                            "generic_solver_loaded",
                            "generic_solver_active",
                            "generic_solver_errors",
                        ],
                        activation_runtime_fields={
                            "{mechanism}": ["mechanism_activation"]
                        },
                        effect_probe_runtime_fields={
                            "{mechanism}": ["mechanism_effect"]
                        },
                    ),
                )
            ]
        ),
    )

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        "/cand",
        "/champ",
        "modify",
        selected_surface="generic_solver",
        mechanism_changes=(
            MechanismChange(id="target_probe", change_type="modify"),
        ),
    )

    assert result.gate_outcome == "fail"
    assert "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED" in result.reason_codes
    guard = result.candidate_surface_runtime_summary["telemetry_guard"]
    assert guard["passed"] is False
    assert guard["failures"][0]["mechanism"] == "target_probe"
    assert (
        guard["mechanisms"]["target_probe"]["fields"]["mechanism_activation"][
            "candidate_positive"
        ]
        == 0
    )


def test_run_experiment_normalizes_solver_algorithm_surface_alias(tmp_path):
    runner = MagicMock()
    candidate_runtime = {
        "solver_algorithm_loaded": True,
        "solver_algorithm_active": True,
        "solver_algorithm_errors": 0,
        "solver_algorithm_stop_reason": "completed",
    }
    pair = [
        _make_run_result(2, 1000, runtime={}),
        _make_run_result(1, 900, runtime=candidate_runtime),
    ]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(
        runner,
        tmp_path,
        problem_spec=_surface_problem_spec(
            name="solver_design",
            required_runtime_fields=(
                "solver_algorithm_loaded",
                "solver_algorithm_active",
                "solver_algorithm_errors",
                "solver_algorithm_stop_reason",
            ),
        ),
    )

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        "/cand",
        "/champ",
        "modify",
        selected_surface="solver_algorithm",
    )

    assert result.selected_surface == "solver_design"
    assert result.candidate_surface_runtime_summary["selected_surface"] == "solver_design"
    assert result.stats.failed_pairs == 0
    assert {
        call.kwargs["selected_surface"]
        for call in runner.run_solver.call_args_list
    } == {"solver_design"}
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["selected_surface"] == "solver_design"


def test_solver_algorithm_surface_declaration_fails_closed(tmp_path):
    runner = MagicMock()
    pair = [
        _make_run_result(2, 1000, runtime={}),
        _make_run_result(
            1,
            900,
            runtime={
                "solver_algorithm_loaded": True,
                "solver_algorithm_active": True,
                "solver_algorithm_errors": 0,
            },
        ),
    ]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(
        runner,
        tmp_path,
        problem_spec=_surface_problem_spec(
            name="solver_algorithm",
            required_runtime_fields=("solver_algorithm_loaded",),
        ),
    )

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        "/cand",
        "/champ",
        "modify",
        selected_surface="solver_algorithm",
    )

    assert result.selected_surface == "solver_design"
    assert result.stats.candidate_failed_pairs == 4
    assert result.candidate_runtime_failure_categories == {
        "surface_contract_error": 4,
    }
    assert result.candidate_first_runtime_failure is not None
    assert result.candidate_first_runtime_failure["surface"] == "solver_design"
    assert "not declared" in result.candidate_first_runtime_failure["detail_summary"]


def test_runtime_summary_includes_solver_algorithm_telemetry_without_selected_surface(
    tmp_path,
):
    runner = MagicMock()
    candidate_runtime = {
        "solver_algorithm_stop_reason": "no_improvement",
        "solver_algorithm_search_iterations": 7,
        "solver_algorithm_move_attempts": 42,
        "solver_algorithm_accepted_moves": 5,
        "solver_algorithm_improving_moves": 3,
        "solver_algorithm_neutral_accepted_moves": 2,
        "solver_algorithm_baseline_calls": 1,
        "solver_algorithm_errors": 0,
    }
    pair = [
        _make_run_result(2, 1000, elapsed_ms=100, runtime={}),
        _make_run_result(1, 900, elapsed_ms=110, runtime=candidate_runtime),
    ]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        "/cand",
        "/champ",
        "modify",
    )

    assert result.candidate_runtime_stop_reasons == {"no_improvement": 4}
    assert "candidate_solver_algorithm_iterations=28" in result.exposed_summary
    assert "candidate_solver_algorithm_move_attempts=168" in result.exposed_summary
    raw = json.loads(open(result.raw_metrics_ref).read())
    candidate_runtime_summary = raw["pairs"][0]["candidate_runtime"]
    assert candidate_runtime_summary["solver_algorithm_stop_reason"] == "no_improvement"
    assert candidate_runtime_summary["solver_algorithm_search_iterations"] == 7
    assert candidate_runtime_summary["solver_algorithm_move_attempts"] == 42
    assert candidate_runtime_summary["solver_algorithm_accepted_moves"] == 5
    assert candidate_runtime_summary["solver_algorithm_improving_moves"] == 3
    assert candidate_runtime_summary["solver_algorithm_neutral_accepted_moves"] == 2
    assert candidate_runtime_summary["solver_algorithm_baseline_calls"] == 1


@pytest.mark.parametrize(
    "champion_result",
    [
        _make_run_failure("crash"),
        _make_run_result(
            2,
            1000,
            runtime={
                "operator_errors": 1,
                "operator_events": [{"detail": "champion operator failed"}],
            },
        ),
    ],
)
def test_champion_failure_branches_emit_progress_callback(
    tmp_path,
    champion_result,
):
    runner = MagicMock()
    candidate = _make_run_result(1, 900)
    runner.run_solver.side_effect = [champion_result, candidate] * 4
    proto = _make_protocol(runner, tmp_path)
    progress_events = []
    proto.set_progress_callback(lambda **payload: progress_events.append(payload))

    result = proto.run_experiment(
        ExperimentStage.VALIDATION,
        "/cand",
        "/champ",
        "modify",
    )

    assert result.stats.champion_failed_pairs == 4
    assert len(progress_events) == 9
    assert progress_events[-1]["attempted_pairs"] == 4
    assert progress_events[-1]["completed_pairs"] == 0
