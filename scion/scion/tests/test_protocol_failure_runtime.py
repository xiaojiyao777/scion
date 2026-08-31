"""Focused tests split from test_protocol.py."""

import uuid

from scion.config.problem import ProtocolConfig
from scion.core.decision import DecisionEngine
from scion.core.features import SafeFeatureExtractor
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ContractResult,
    Decision,
    VerificationResult,
)
from scion.protocol.experiment import stages
from scion.protocol.experiment.stages import _screening_evidence_status

from .protocol_test_support import *  # noqa: F401,F403


def _decision_for_screening_result(result):
    branch = Branch(
        branch_id=str(uuid.uuid4()),
        state=BranchState.EXPLORE,
        base_champion_id=0,
    )
    features = SafeFeatureExtractor().extract(
        branch_state=branch.state,
        screening_expand_count=branch.screening_expand_count,
        validation_expand_count=branch.validation_expand_count,
        failure_codes=tuple(branch.failure_codes),
        hypothesis_action="modify",
        contract=ContractResult(passed=True, checks=()),
        verification=VerificationResult(passed=True, checks=()),
        canary=CanaryResult(passed=True),
        protocol=result,
    )
    return DecisionEngine(ProtocolConfig()).decide(features)


@pytest.mark.parametrize(
    ("complete", "champion_failed_pairs", "expected"),
    [
        (False, 0, "in_progress"),
        (False, 1, "in_progress"),
        (True, 0, "complete"),
        (True, 1, "partial_champion_evidence"),
    ],
)
def test_screening_evidence_status_tracks_snapshot_lifecycle(
    complete,
    champion_failed_pairs,
    expected,
):
    assert (
        _screening_evidence_status(
            stage=ExperimentStage.SCREENING,
            complete=complete,
            champion_failed_pairs=champion_failed_pairs,
        )
        == expected
    )


def test_screening_writes_raw_metrics_only_at_terminal(tmp_path):
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 1000),
        _make_run_result(1, 900),
    ] * 4
    proto = _make_protocol(runner, tmp_path)
    snapshots = []

    def capture_snapshot(**payload):
        raw_ref = payload.get("raw_metrics_ref")
        if raw_ref:
            with open(raw_ref, encoding="utf-8") as stream:
                snapshots.append(json.load(stream))

    proto.set_progress_callback(capture_snapshot)
    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        "/cand",
        "/champ",
        "modify",
    )

    assert len(snapshots) == 1
    assert snapshots[0]["complete"] is True
    final = json.loads(open(result.raw_metrics_ref, encoding="utf-8").read())
    assert final["complete"] is True
    assert final["screening_evidence_status"] == "complete"


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


@pytest.mark.parametrize(
    ("champion_feasible", "expected_count"),
    ((True, 4), (False, 0)),
)
def test_nonpaired_infeasibility_count_is_observational_and_candidate_attributable(
    tmp_path,
    champion_feasible,
    expected_count,
):
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(1, 900, feasible=champion_feasible),
        _make_run_result(3, 1500, feasible=False),
    ] * 4
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        "/cand",
        "/champ",
        "modify",
    )

    assert result.candidate_attributable_infeasible_pairs == expected_count
    assert result.stats.failed_pairs == 0
    assert result.stats.candidate_failed_pairs == 0
    assert result.stats.valid_pairs == 4


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
    assert result.candidate_only_timeout_pairs == 4
    assert result.candidate_only_invalid_output_pairs == 0
    assert len(result.pair_feedback) == 4
    assert all(item.comparison == "loss" for item in result.pair_feedback)
    assert "failed_pairs=4" in result.exposed_summary
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["failed_pairs"] == 4
    assert raw["candidate_failed_pairs"] == 4
    assert len(raw["failures"]) == 4
    assert all(p["comparison"] == "loss" for p in raw["pairs"])
    assert all(p["candidate_elapsed_ms"] == 1000 for p in raw["pairs"])
    assert all(p["champion_elapsed_ms"] == 100 for p in raw["pairs"])


def test_shared_process_failure_is_not_recorded_as_candidate_algorithm_failure(
    tmp_path,
):
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
        error_category="crash",
    )
    candidate_failure = RunResult(
        success=False,
        exit_code=1,
        stdout="",
        stderr=stderr,
        elapsed_ms=120,
        output=None,
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
    assert result.pair_feedback == ()
    assert result.candidate_runtime_failure_categories == {}
    assert result.candidate_first_runtime_failure is None
    assert result.candidate_only_timeout_pairs == 0
    assert result.candidate_only_invalid_output_pairs == 0
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["candidate_failed_pairs"] == 0
    assert raw["champion_failed_pairs"] == 4
    assert raw["failures"][0]["side"] == "both"
    assert raw["failures"][0]["error_category"] == "shared_process_failure"
    assert raw["pairs"][0]["decisive_metric"] == "shared_process_failure"


def test_mixed_screening_champion_failures_are_explicit_partial_evidence(tmp_path):
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_failure("timeout"),
        _make_run_result(1, 800),
        _make_run_result(2, 1000),
        _make_run_result(1, 800),
        _make_run_result(2, 1000),
        _make_run_result(1, 800),
        _make_run_result(2, 1000),
        _make_run_result(1, 800),
    ]
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.stats.valid_pairs == 3
    assert result.stats.failed_pairs == 1
    assert result.stats.champion_failed_pairs == 1
    assert len(result.pair_feedback) == 3
    assert result.gate_outcome == "unclear"
    assert "SCREENING_PARTIAL_CHAMPION_EVIDENCE" in result.reason_codes
    assert "champion_failures=1" in result.exposed_summary
    assert "screening_evidence_status=partial_champion_evidence" in (
        result.exposed_summary
    )
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["screening_evidence_status"] == "partial_champion_evidence"
    partial = raw["screening_partial_champion_evidence"]
    assert partial["reason_code"] == "SCREENING_PARTIAL_CHAMPION_EVIDENCE"
    assert partial["champion_failed_pairs"] == 1
    assert partial["valid_pairs"] == 3
    assert partial["decision_complete_evidence"] is False


def test_candidate_failure_summary_preserves_traceback_terminal_exception(tmp_path):
    runner = MagicMock()
    long_diagnostic = "diagnostic-context-" + "x" * 600 + "-complete-tail"
    stderr = f"""Traceback (most recent call last):
  File "solver.py", line 84, in _main
    instance = adapter.load_instance(instance_path)
{long_diagnostic}
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
            error_category="crash",
        ),
    ] * 4
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.candidate_first_runtime_failure is not None
    summary = result.candidate_first_runtime_failure["detail_summary"]
    assert summary == stderr
    assert "complete-tail" in summary
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


@pytest.mark.parametrize(
    ("mode", "candidate_failures", "champion_failures", "shared", "bilateral"),
    (
        ("candidate", 4, 0, 0, 0),
        ("champion", 0, 4, 0, 0),
        ("shared", 0, 4, 4, 0),
        ("bilateral", 4, 4, 0, 4),
    ),
)
def test_normal_runtime_audit_failure_attribution_is_pair_local(
    tmp_path,
    monkeypatch,
    mode,
    candidate_failures,
    champion_failures,
    shared,
    bilateral,
):
    champion_issue = {
        "error_category": "solver_runtime_error",
        "runtime_error_field": "solver_errors",
        "runtime_error_count": 1,
        "detail": "solver runtime audit reported solver_errors=1",
    }
    candidate_issue = dict(champion_issue)
    if mode == "shared":
        candidate_issue = {
            **candidate_issue,
            "selected_surface": "solver_design",
            "runtime_error_counts": {"solver_errors": 1},
        }
    elif mode == "bilateral":
        candidate_issue = {
            **candidate_issue,
            "runtime_error_field": "candidate_errors",
            "detail": "solver runtime audit reported candidate_errors=1",
        }

    def audit(result, **_kwargs):
        is_candidate = result.output.objective["subcategory_splits"] == 1
        if mode == "candidate":
            return candidate_issue if is_candidate else None
        if mode == "champion":
            return None if is_candidate else champion_issue
        return candidate_issue if is_candidate else champion_issue

    monkeypatch.setattr(stages, "runtime_audit_failure_from_result", audit)
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 1000),
        _make_run_result(1, 800),
    ] * 4
    result = _make_protocol(runner, tmp_path).run_experiment(
        ExperimentStage.SCREENING,
        "/cand",
        "/champ",
        "modify",
    )

    assert result.stats.failed_pairs == 4
    assert result.stats.candidate_failed_pairs == candidate_failures
    assert result.stats.champion_failed_pairs == champion_failures
    assert result.stats.shared_failed_pairs == shared
    assert result.stats.bilateral_failed_pairs == bilateral
    decision = _decision_for_screening_result(result)
    if mode == "candidate":
        assert decision.decision is Decision.ABANDON
        assert decision.reason_codes == ("CANDIDATE_RUNTIME_FAILURE",)
    else:
        assert decision.decision is Decision.CONTINUE_EXPLORE
        assert decision.reason_codes == ("SCREENING_PARTIAL_CHAMPION_EVIDENCE",)

    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["shared_failed_pairs"] == shared
    assert raw["bilateral_failed_pairs"] == bilateral
    first_failure = raw["failures"][0]
    expected_side = mode if mode in ("candidate", "champion") else "both"
    assert first_failure["side"] == expected_side
    assert first_failure["failure_attribution"] == mode
    if mode in ("shared", "bilateral"):
        assert first_failure["champion_runtime_audit"] == champion_issue
        assert first_failure["candidate_runtime_audit"] == candidate_issue
        assert raw["pairs"][0]["comparison"] == "invalid"
        assert result.pair_feedback == ()
    else:
        assert raw["pairs"][0]["comparison"] == (
            "loss" if mode == "candidate" else "invalid"
        )


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
    assert result.stats.candidate_failed_pairs == 4
    assert result.stats.champion_failed_pairs == 0
    assert result.candidate_only_timeout_pairs == 0
    assert result.candidate_only_invalid_output_pairs == 4
    assert raw["failed_pairs"] == 4
    assert raw["candidate_failed_pairs"] == 4
    assert raw["champion_failed_pairs"] == 0
    assert len(raw["failures"]) == 4
    assert result.pair_feedback == ()
    assert all(f["side"] == "candidate" for f in raw["failures"])
    assert all(f["candidate_elapsed_ms"] == 95 for f in raw["failures"])
    assert all(f["champion_elapsed_ms"] == 80 for f in raw["failures"])
    assert all(p["runtime_delta_ms"] == 15 for p in raw["pairs"])


def test_mixed_screening_candidate_missing_output_is_a_hard_failure(tmp_path):
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 1000),
        _make_run_result(1, 800),
    ] * 3 + [
        _make_run_result(2, 1000),
        _make_missing_output(),
    ]
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.stats.valid_pairs == 3
    assert result.stats.failed_pairs == 1
    assert result.stats.candidate_failed_pairs == 1
    assert result.stats.champion_failed_pairs == 0
    # Protocol still owns its preregistered scientific threshold. Decision's
    # existing hard-safety boundary owns candidate execution failures.
    assert result.gate_outcome == "pass"
    decision = _decision_for_screening_result(result)
    assert decision.decision is Decision.ABANDON
    assert decision.reason_codes == ("CANDIDATE_RUNTIME_FAILURE",)

    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["valid_pairs"] == result.stats.valid_pairs
    assert raw["failed_pairs"] == result.stats.failed_pairs
    assert raw["candidate_failed_pairs"] == result.stats.candidate_failed_pairs
    assert raw["champion_failed_pairs"] == result.stats.champion_failed_pairs
    assert raw["screening_evidence_status"] == "complete"
    assert raw["failures"][-1]["side"] == "candidate"


def test_mixed_screening_champion_missing_output_is_partial_evidence(tmp_path):
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 1000),
        _make_run_result(1, 800),
    ] * 3 + [
        _make_missing_output(),
        _make_run_result(1, 800),
    ]
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.stats.valid_pairs == 3
    assert result.stats.failed_pairs == 1
    assert result.stats.candidate_failed_pairs == 0
    assert result.stats.champion_failed_pairs == 1
    assert result.gate_outcome == "unclear"
    assert "SCREENING_PARTIAL_CHAMPION_EVIDENCE" in result.reason_codes
    decision = _decision_for_screening_result(result)
    assert decision.decision is Decision.CONTINUE_EXPLORE
    assert decision.reason_codes == ("SCREENING_PARTIAL_CHAMPION_EVIDENCE",)

    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["valid_pairs"] == result.stats.valid_pairs
    assert raw["failed_pairs"] == result.stats.failed_pairs
    assert raw["candidate_failed_pairs"] == result.stats.candidate_failed_pairs
    assert raw["champion_failed_pairs"] == result.stats.champion_failed_pairs
    assert raw["screening_evidence_status"] == "partial_champion_evidence"
    assert raw["failures"][-1]["side"] == "champion"


def test_both_missing_outputs_count_one_failed_pair_and_both_sides(tmp_path):
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 1000),
        _make_run_result(1, 800),
    ] * 3 + [
        _make_missing_output(),
        _make_missing_output(),
    ]
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING, "/cand", "/champ", "modify"
    )

    assert result.stats.valid_pairs == 3
    assert result.stats.failed_pairs == 1
    assert result.stats.candidate_failed_pairs == 0
    assert result.stats.champion_failed_pairs == 1
    assert result.stats.shared_failed_pairs == 1
    assert result.stats.bilateral_failed_pairs == 0
    assert result.candidate_only_timeout_pairs == 0
    assert result.candidate_only_invalid_output_pairs == 0
    decision = _decision_for_screening_result(result)
    assert decision.decision is Decision.CONTINUE_EXPLORE
    assert decision.reason_codes == ("SCREENING_PARTIAL_CHAMPION_EVIDENCE",)

    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["valid_pairs"] == result.stats.valid_pairs
    assert raw["failed_pairs"] == result.stats.failed_pairs
    assert raw["candidate_failed_pairs"] == result.stats.candidate_failed_pairs
    assert raw["champion_failed_pairs"] == result.stats.champion_failed_pairs
    assert raw["screening_evidence_status"] == "partial_champion_evidence"
    assert raw["failures"][-1]["side"] == "both"
    assert raw["failures"][-1]["failure_attribution"] == "shared"


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


def test_validation_bilateral_audit_failure_is_not_candidate_only(
    tmp_path,
    monkeypatch,
):
    champion_issue = {
        "error_category": "solver_runtime_error",
        "runtime_error_field": "champion_errors",
        "detail": "solver runtime audit reported champion_errors=1",
    }
    candidate_issue = {
        "error_category": "solver_runtime_error",
        "runtime_error_field": "candidate_errors",
        "detail": "solver runtime audit reported candidate_errors=1",
    }
    audit = MagicMock(
        side_effect=[None, None] * 3 + [champion_issue, candidate_issue]
    )
    monkeypatch.setattr(stages, "runtime_audit_failure_from_result", audit)
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 1000),
        _make_run_result(1, 800),
    ] * 4

    result = _make_protocol(runner, tmp_path).run_experiment(
        ExperimentStage.VALIDATION,
        "/cand",
        "/champ",
        "modify",
    )

    assert result.stats.valid_pairs == 3
    assert result.stats.failed_pairs == 1
    assert result.stats.candidate_failed_pairs == 1
    assert result.stats.champion_failed_pairs == 1
    assert result.stats.bilateral_failed_pairs == 1
    assert result.reason_codes == (
        "INCOMPLETE_EVIDENCE",
        "CHAMPION_RUNTIME_FAILURE",
    )


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

    result = proto.run_experiment(ExperimentStage.FROZEN, "/cand", "/champ", "modify")

    assert result.gate_outcome == "fail"
    assert "INCOMPLETE_EVIDENCE" in result.reason_codes
    assert "CHAMPION_RUNTIME_FAILURE" in result.reason_codes
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["valid_pairs"] == 3
    assert raw["champion_failed_pairs"] == 1


def test_frozen_dual_timeout_is_explicit_and_not_candidate_only(tmp_path):
    runner = MagicMock()
    side_effect = []
    for _ in range(3):
        side_effect.extend([_make_run_result(2, 1000), _make_run_result(1, 800)])
    side_effect.extend([_make_run_failure("timeout"), _make_run_failure("timeout")])
    runner.run_solver.side_effect = side_effect
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_experiment(ExperimentStage.FROZEN, "/cand", "/champ", "modify")

    assert result.gate_outcome == "fail"
    assert result.stats.failed_pairs == 1
    assert result.stats.champion_failed_pairs == 1
    assert result.stats.candidate_failed_pairs == 0
    assert result.candidate_only_timeout_pairs == 0
    assert result.candidate_only_invalid_output_pairs == 0
    assert result.reason_codes == (
        "INCOMPLETE_EVIDENCE",
        "CHAMPION_RUNTIME_FAILURE",
    )
    raw = json.loads(open(result.raw_metrics_ref).read())
    assert raw["failures"][0]["side"] == "both"
    assert raw["failures"][0]["error_category"] == "dual_runtime_failure"
    assert raw["pairs"][3]["decisive_metric"] == "dual_runtime_failure"
