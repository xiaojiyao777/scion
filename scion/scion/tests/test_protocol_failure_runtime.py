"""Focused tests split from test_protocol.py."""

from .protocol_test_support import *  # noqa: F401,F403

def test_run_experiment_screening_fail(tmp_path):
    """Candidate always loses → fail.
    champ=better(splits=1, cost=900), cand=worse(splits=3, cost=1500).
    """
    runner = MagicMock()
    pair = [_make_run_result(1, 900), _make_run_result(3, 1500)]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(runner, tmp_path)
    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )
    assert result.gate_outcome == "fail"


def test_candidate_timeout_counts_as_screening_loss_and_is_recorded(tmp_path):
    runner = MagicMock()
    pair = [_make_run_result(1, 900), _make_run_failure("timeout")]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.gate_outcome == "fail"
    assert result.stats.losses == 2
    assert result.stats.total_pairs == 4
    assert result.stats.attempted_pairs == 4
    assert result.stats.valid_pairs == 0
    assert result.stats.failed_pairs == 4
    assert result.stats.candidate_failed_pairs == 4
    assert "failed_pairs=4" in result.exposed_summary
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["failed_pairs"] == 4
    assert raw["candidate_failed_pairs"] == 4
    assert len(raw["failures"]) == 4
    assert all(p["comparison"] == "loss" for p in raw["pairs"])
    assert all(p["candidate_elapsed_ms"] == 1000 for p in raw["pairs"])
    assert all(p["champion_elapsed_ms"] == 100 for p in raw["pairs"])


def test_shared_process_failure_is_not_recorded_as_candidate_algorithm_failure(tmp_path):
    runner = MagicMock()
    stderr = """Traceback (most recent call last):
  File "solver.py", line 84, in _main
    instance = adapter.load_instance(instance_path)
FileNotFoundError: [Errno 2] No such file or directory: 'cvrplib/A/A-n32-k5.vrp'
"""
    champion_failure = RunResult(
        success=False,
        exit_code=1,
        stdout="",
        stderr=stderr,
        elapsed_ms=100,
        output=None,
        output_path=None,
        error_category="crash",
    )
    candidate_failure = RunResult(
        success=False,
        exit_code=1,
        stdout="",
        stderr=stderr,
        elapsed_ms=120,
        output=None,
        output_path=None,
        error_category="crash",
    )
    runner.run_solver.side_effect = [champion_failure, candidate_failure] * 4
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.stats.failed_pairs == 4
    assert result.stats.champion_failed_pairs == 4
    assert result.stats.candidate_failed_pairs == 0
    assert result.candidate_runtime_failure_categories == {}
    assert result.candidate_first_runtime_failure is None
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["candidate_failed_pairs"] == 0
    assert raw["champion_failed_pairs"] == 4
    assert raw["failures"][0]["side"] == "both"
    assert raw["failures"][0]["error_category"] == "shared_process_failure"
    assert raw["pairs"][0]["decisive_metric"] == "shared_process_failure"


def test_candidate_failure_summary_preserves_traceback_terminal_exception(tmp_path):
    runner = MagicMock()
    stderr = """Traceback (most recent call last):
  File "solver.py", line 84, in _main
    instance = adapter.load_instance(instance_path)
FileNotFoundError: [Errno 2] No such file or directory: 'cvrplib/A/A-n32-k5.vrp'
"""
    runner.run_solver.side_effect = [
        _make_run_result(1, 900),
        RunResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr=stderr,
            elapsed_ms=120,
            output=None,
            output_path=None,
            error_category="crash",
        ),
    ] * 4
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.candidate_first_runtime_failure is not None
    summary = result.candidate_first_runtime_failure["detail_summary"]
    assert "FileNotFoundError" in summary
    assert "cvrplib/A/A-n32-k5.vrp" in summary


def test_candidate_operator_runtime_error_counts_as_screening_failure(tmp_path):
    runner = MagicMock()
    runtime = {
        "operator_errors": 1,
        "operator_loaded": 1,
        "operator_attempts": 1,
        "operator_accepted": 0,
        "operator_events": [
            {
                "operator": "bad_cvrp_op",
                "status": "error",
                "detail": "'CvrpInstance' object has no attribute 'vehicle_capacity'",
            }
        ],
    }
    pair = [
        _make_run_result(1, 900, elapsed_ms=100),
        _make_run_result(1, 900, elapsed_ms=110, runtime=runtime),
    ]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.gate_outcome == "fail"
    assert result.stats.valid_pairs == 0
    assert result.stats.failed_pairs == 4
    assert result.stats.candidate_failed_pairs == 4
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["candidate_failed_pairs"] == 4
    assert raw["failures"][0]["error_category"] == "operator_runtime_error"
    assert raw["pairs"][0]["decisive_metric"] == "operator_runtime_error"


def test_candidate_required_baseline_error_counts_as_screening_failure(tmp_path):
    runner = MagicMock()
    runtime = {
        "baseline_required": True,
        "baseline_mode": "scion_nearest_neighbor_fallback",
        "baseline_error": "vrp/src baseline not available",
    }
    pair = [
        _make_run_result(1, 900, elapsed_ms=100),
        _make_run_result(1, 900, elapsed_ms=110, runtime=runtime),
    ]
    runner.run_solver.side_effect = pair * 4
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.gate_outcome == "fail"
    assert result.stats.valid_pairs == 0
    assert result.stats.failed_pairs == 4
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["failures"][0]["error_category"] == "baseline_runtime_error"
    assert raw["pairs"][0]["decisive_metric"] == "baseline_runtime_error"


def test_missing_output_records_both_elapsed_values(tmp_path):
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 1000, elapsed_ms=80),
        _make_missing_output(elapsed_ms=95),
    ] * 4
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["failed_pairs"] == 4
    assert len(raw["failures"]) == 4
    assert all(f["candidate_elapsed_ms"] == 95 for f in raw["failures"])
    assert all(f["champion_elapsed_ms"] == 80 for f in raw["failures"])
    assert all(p["runtime_delta_ms"] == 15 for p in raw["pairs"])


def test_validation_fails_when_candidate_timeout_makes_evidence_incomplete(tmp_path):
    runner = MagicMock()
    # First three pairs are strong wins; final candidate timeout must still
    # force validation failure because validation evidence is incomplete.
    side_effect = []
    for _ in range(3):
        side_effect.extend([_make_run_result(2, 1000), _make_run_result(1, 800)])
    side_effect.extend([_make_run_result(2, 1000), _make_run_failure("timeout")])
    runner.run_solver.side_effect = side_effect
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.VALIDATION, "/cand", "/champ", "modify"
    )

    assert result.gate_outcome == "fail"
    assert "INCOMPLETE_EVIDENCE" in result.reason_codes
    assert "CANDIDATE_RUNTIME_FAILURE" in result.reason_codes
    assert result.stats.valid_pairs == 3
    assert result.stats.failed_pairs == 1
    assert result.stats.candidate_failed_pairs == 1
    assert "failed_pairs=1" in result.exposed_summary
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["attempted_pairs"] == 4
    assert raw["valid_pairs"] == 3
    assert raw["failed_pairs"] == 1


def test_protocol_result_exposes_bounded_candidate_runtime_categories(tmp_path):
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(1, 800),
        _make_run_result(2, 1000, runtime={"operator_errors": 1}),
        _make_run_result(1, 800),
        _make_run_result(2, 1000, runtime={"operator_invalid_outputs": 1}),
        _make_run_result(1, 800),
        _make_run_result(2, 1000, runtime={"policy_errors": 1}),
        _make_run_result(1, 800),
        _make_run_result(
            2,
            1000,
            runtime={
                "operator_attempts": 4,
                "operator_accepted": 0,
                "operator_stop_reason": "no_improvement_round",
            },
        ),
    ]
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.candidate_runtime_failure_categories["operator_error"] == 1
    assert result.candidate_runtime_failure_categories["invalid_output"] == 1
    assert result.candidate_runtime_failure_categories["policy_error"] == 1
    assert result.candidate_runtime_failure_categories["no_accepted_moves"] == 1
    assert result.candidate_first_runtime_failure == {
        "category": "operator_error",
        "code": "operator_errors",
        "surface": "",
        "component": "operator",
        "detail_summary": "solver runtime reported operator_errors=1",
    }
    assert result.candidate_operator_attempts == 4
    assert result.candidate_operator_accepted == 0
    assert result.candidate_operator_errors == 1
    assert result.candidate_operator_invalid_outputs == 1
    assert result.candidate_policy_errors == 1
    assert result.candidate_runtime_stop_reasons == {"no_improvement_round": 1}
    assert "candidate_runtime_categories=" in result.exposed_summary


def test_frozen_fails_when_champion_runtime_failure_makes_pair_invalid(tmp_path):
    runner = MagicMock()
    side_effect = []
    for _ in range(3):
        side_effect.extend([_make_run_result(2, 1000), _make_run_result(1, 800)])
    side_effect.extend([_make_run_failure("timeout"), _make_run_result(1, 800)])
    runner.run_solver.side_effect = side_effect
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.FROZEN, "/cand", "/champ", "modify"
    )

    assert result.gate_outcome == "fail"
    assert "INCOMPLETE_EVIDENCE" in result.reason_codes
    assert "CHAMPION_RUNTIME_FAILURE" in result.reason_codes
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["valid_pairs"] == 3
    assert raw["champion_failed_pairs"] == 1
