"""Focused tests split from test_evidence_recorder.py."""

from .evidence_recorder_test_support import *  # noqa: F401,F403
from scion.core.step_result import StepResult

def test_record_step_and_summary_preserve_current_fields(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "n_experiments": 1,
            "proposal_attempts": 3,
            "screened_experiments": 1,
            "n_active_branches": 0,
            "branches": [],
        },
    )
    step_history: list[StepRecord] = []

    recorder.record_step(_step("/tmp/metrics-round-3.json"), step_history)
    summary = recorder.write_campaign_summary(
        step_history=step_history,
        round_num=3,
        champion=_champion(),
        budget_used=2,
        budget_total=8,
        stopped_reason="max_rounds",
        diagnostics={"note": "ok"},
    )

    assert (tmp_path / "campaign_summary.json").exists()
    from_disk = json.loads((tmp_path / "campaign_summary.json").read_text())
    assert from_disk == summary
    assert summary["campaign_id"] == "camp-1"
    assert summary["total_rounds"] == 3
    assert summary["proposal_attempts"] == 3
    assert summary["screened_experiments"] == 1
    assert summary["champion_version"] == 7
    assert summary["champion_weight_revision"] == 2
    assert summary["n_active_branches"] == 0
    assert summary["budget_utilization"] == 0.25
    assert summary["cache_stats"]["total_tokens"] == 100
    assert summary["cache_stats"]["cache_read_tokens"] == 25

    summary_step = summary["steps"][0]
    assert summary_step["round"] == 3
    assert summary_step["screened_experiment"] is True
    assert summary_step["branch_id"] == "branch-1"
    assert summary_step["decision"] == "queue_validate"
    assert summary_step["hypothesis"]["text"] == "Improve route insertion with regret scoring."
    assert not summary_step["protocol_result"]["raw_metrics_ref"].startswith("/")
    assert "metrics-round-3.json" in summary_step["protocol_result"]["raw_metrics_ref"]
    assert summary_step["protocol_result"]["raw_metrics_ref_scope"] == (
        "public_artifact_ref"
    )
    assert summary_step["protocol_result"]["raw_metrics_internal_only"] is True
    assert summary_step["protocol_result"]["win_rate_scope"] == "case_level_gate"
    assert summary_step["protocol_result"]["screening_case_win_rate"] == 0.67
    assert summary_step["protocol_result"]["screening_gate_win_rate"] == 0.67
    assert summary_step["protocol_result"]["screening_win_rate"] == 0.67
    assert summary_step["protocol_result"]["screening_win_rate_scope"] == (
        "case_level_gate"
    )
    assert summary_step["protocol_result"]["reason_codes"] == [
        "screening_positive",
        "runtime_ok",
    ]
    assert summary_step["protocol_result"]["protocol_reason_codes"] == [
        "screening_positive",
        "runtime_ok",
    ]
    assert summary_step["protocol_result"]["decision_reason_codes"] == [
        "screening_positive",
    ]
    assert summary_step["protocol_result"]["effective_reason_codes"] == [
        "screening_positive",
    ]
    assert summary_step["protocol_result"]["effective_reason_source"] == (
        "decision_engine"
    )
    assert summary_step["protocol_result"]["runtime_ratio_median"] == 1.18
    assert summary_step["protocol_result"]["runtime_delta_median_ms"] == 24.0
    assert summary_step["protocol_result"]["runtime_regression_rate"] == 0.5
    assert summary_step["protocol_result"]["runtime_pairs"] == 4


def test_campaign_summary_marks_agent_quality_block_contract_not_run(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = StepRecord(
        round_num=1,
        branch_id="branch-1",
        hypothesis=_hypothesis("Rejected as proposal-only novelty duplicate."),
        patch=None,
        contract_passed=True,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="agent_quality_blocked",
        failure_detail=(
            "agentic_proposal:premise_contradicted: "
            "agent_quality_blocked:proposal_premise_contradicted:"
            "agent_grounding_failure"
        ),
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
        stopped_reason="max_rounds_exhausted",
    )

    summary_step = summary["steps"][0]
    assert summary_step["contract_passed"] is False
    assert summary_step["contract_not_run_reason"] == (
        "proposal_only_agent_quality_blocked"
    )
    assert summary_step["verification_passed"] is False


def test_campaign_summary_separates_primary_contract_and_session_observation(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = StepRecord(
        round_num=3,
        branch_id="branch-1",
        hypothesis=_hypothesis("Invalid telemetry with contradicted premise."),
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="hypothesis_contract",
        failure_detail=(
            "C11_expected_telemetry: expected_telemetry category "
            "'attribution' is not supported"
        ),
        proposal_session_ref={
            "schema_version": "agentic-proposal-session.v1",
            "session_id": "session-3",
            "termination_reason": "premise_contradicted",
            "status": "partial_hypothesis_only",
            "failure_category": "agent_grounding_failure",
            "failure_code": "proposal_premise_contradicted",
            "agent_block_reason": "agent_quality_blocked",
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=3,
        champion=_champion(),
        stopped_reason="max_rounds_exhausted",
    )

    summary_step = summary["steps"][0]
    assert summary_step["primary_failure"] == {
        "stage": "agent_quality_blocked",
        "reason": "proposal_premise_contradicted",
        "category": "agent_grounding_failure",
        "code": "proposal_premise_contradicted",
    }
    assert summary_step.get("secondary_observations", []) == []
    assert (
        summary_step["proposal_session_ref"]["failure_code"]
        == "proposal_premise_contradicted"
    )


def test_campaign_summary_uses_transient_api_session_failure_as_primary(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = StepRecord(
        round_num=3,
        branch_id="branch-1",
        hypothesis=_hypothesis("Repair failed on external gateway error."),
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="code_generation",
        failure_detail=(
            "agentic_proposal:code_generation_failed: Tool call failed after "
            "2 transient API attempt(s). Last error: Transient provider error: "
            "HTTP 502 Bad Gateway"
        ),
        proposal_session_ref={
            "session_id": "transient-session",
            "termination_reason": "code_generation_failed",
            "status": "partial_hypothesis_only",
            "failure_category": "llm_transient_api_error",
            "primary_failure": {
                "stage": "code_generation_failed",
                "reason": (
                    "Tool call failed after 2 transient API attempt(s). "
                    "Last error: Transient provider error: HTTP 502 Bad Gateway"
                ),
                "category": "llm_transient_api_error",
            },
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=3,
        champion=_champion(),
        stopped_reason="max_rounds_exhausted",
    )

    summary_step = summary["steps"][0]
    assert summary_step["primary_failure"]["category"] == "llm_transient_api_error"
    assert summary_step["primary_failure"]["stage"] == "code_generation_failed"
    assert "502 Bad Gateway" in summary_step["primary_failure"]["reason"]
    assert summary_step["proposal_session_ref"]["failure_category"] == (
        "llm_transient_api_error"
    )


def test_campaign_summary_reports_provider_balance_stop_from_failure_detail(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = StepRecord(
        round_num=2,
        branch_id="branch-1",
        hypothesis=_hypothesis("Proposal failed before a candidate was generated."),
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="proposal",
        failure_detail=(
            "agentic_proposal:hypothesis_generation_failed: Tool call failed after "
            "3 attempt(s). Last error: Transient provider error: Error code: 403 - "
            "{'error': {'type': 'Aihubmix_api_error', 'message': "
            "'Your account balance is insufficient. Please recharge your account.'}}"
        ),
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=2,
        champion=_champion(),
        stopped_reason="circuit_breaker",
        circuit_breaker_tripped=True,
    )

    assert summary["stopped_reason"] == "api_balance_exhausted"
    assert summary["balance_exhausted"] is True
    assert summary["circuit_breaker_tripped"] is True
    assert summary["stop_category"] == "provider_error"
    assert summary["provider_error"]["category"] == "balance_exhausted"
    assert summary["steps"][0]["contract_not_run_reason"] == (
        "proposal_generation_failed"
    )


def test_status_reports_balance_stop_consistently(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-1",
            "balance_exhausted": True,
            "circuit_breaker_tripped": True,
        },
    )

    status = recorder.write_status(stopped_reason="circuit_breaker")
    on_disk = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))

    assert status["stopped_reason"] == "api_balance_exhausted"
    assert status["balance_exhausted"] is True
    assert status["circuit_breaker_tripped"] is True
    assert status["stop_category"] == "provider_error"
    assert status["provider_error"]["category"] == "balance_exhausted"
    assert on_disk["stopped_reason"] == "api_balance_exhausted"


def test_status_reports_non_counting_last_result(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-1",
            "proposal_attempts": 2,
            "screened_experiments": 0,
        },
    )

    status = recorder.write_status(
        last_result=StepResult(
            action="explore",
            branch_id="branch-1",
            reason="agent_quality_blocked",
            counts_toward_max_rounds=False,
        )
    )

    assert status["proposal_attempts"] == 2
    assert status["screened_experiments"] == 0
    assert status["last_result"]["counts_toward_max_rounds"] is False


def test_status_reports_telemetry_failed_breakdown(tmp_path: Path) -> None:
    telemetry_detail = {
        "schema": "scion.telemetry_decision_detail.v1",
        "stage": "screening",
        "code": "TELEMETRY_ACTIVITY_NOT_OBSERVED",
        "category": "activity",
        "mechanism_id": "activity_probe",
        "surface_field_id": "activity_counter",
        "surface_field_ids": ["activity_counter"],
        "runtime_role": "activity",
        "missing_fields": [],
        "invalid_fields": [],
        "repairable": False,
        "declaration_source_digest": "surface-digest-1",
        "candidate_missing": 0,
        "candidate_present": 16,
        "candidate_positive": 0,
        "champion_positive": 0,
    }
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-1",
            "screened_experiments": 3,
            "telemetry_failed_experiments": 2,
            "telemetry_failed_experiments_by_category": {
                "activity": 1,
                "effect": 1,
            },
            "telemetry_failure_details": [telemetry_detail],
        },
    )

    status = recorder.write_status()

    assert status["telemetry_failed_experiments"] == 2
    assert status["telemetry_failed_experiments_by_category"] == {
        "activity": 1,
        "effect": 1,
    }
    assert status["telemetry_failure_details"] == [telemetry_detail]


def test_status_and_summary_report_proposal_quality_loop_budget(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {"campaign_id": "camp-1"},
    )
    loop_status = {
        "requested_rounds": 3,
        "attempt_limit": 3,
        "effective_rounds_completed": 0,
        "proposal_quality_limit": 6,
        "proposal_quality_loop_limit": 6,
        "proposal_quality_blocks_consumed": 4,
        "proposal_quality_blocks_remaining": 2,
    }

    status = recorder.write_status(loop_status=loop_status)
    summary = recorder.write_campaign_summary(
        step_history=[],
        round_num=0,
        champion=_champion(),
    )

    assert status["campaign_loop"]["requested_rounds"] == 3
    assert status["campaign_loop"]["attempt_limit"] == 3
    assert status["campaign_loop"]["effective_rounds_completed"] == 0
    assert status["campaign_loop"]["proposal_quality_limit"] == 6
    assert status["campaign_loop"]["proposal_quality_blocks_consumed"] == 4
    assert summary["campaign_loop"]["proposal_quality_blocks_remaining"] == 2


def test_sigterm_during_formal_screening_keeps_n_experiments_zero_and_reports_inflight(
    tmp_path: Path,
) -> None:
    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()
    metrics_path = metrics_dir / "partial-screening.json"
    metrics_path.write_text(
        json.dumps(
            {
                "stage": "screening",
                "complete": False,
                "total_pairs": 16,
                "attempted_pairs": 3,
                "valid_pairs": 3,
                "failed_pairs": 0,
                "candidate_failed_pairs": 0,
                "champion_failed_pairs": 0,
            }
        ),
        encoding="utf-8",
    )
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-1",
            "n_experiments": 0,
            "screened_experiments": 0,
        },
    )

    recorder.record_protocol_progress(
        branch_id="branch-1",
        stage="screening",
        target_file="policies/baseline_modules/destroy_repair.py",
        hypothesis_action="modify",
        hypothesis_text="Add a random segment removal operator.",
        mechanism_changes=[
            {"id": "random_segment_removal", "change_type": "add"}
        ],
        raw_metrics_ref=str(metrics_path),
    )
    recorder.current_status_progress = None
    status = recorder.write_status(
        last_result=StepResult(
            action="explore",
            branch_id="branch-old",
            reason="agent_quality_blocked",
            counts_toward_max_rounds=False,
        ),
        stopped_reason="signal:SIGTERM",
    )

    assert status["n_experiments"] == 0
    assert status["screened_experiments"] == 0
    assert status["last_result"]["reason"] == "agent_quality_blocked"
    inflight = status["in_flight_protocol"]
    assert inflight["phase"] == "formal_screening"
    assert inflight["branch_id"] == "branch-1"
    assert inflight["candidate"]["mechanism_changes"][0]["id"] == (
        "random_segment_removal"
    )
    assert inflight["partial_metrics_ref"] == "metrics/partial-screening.json"
    assert inflight["attempted_pairs"] == 3
    assert inflight["total_pairs"] == 16
    assert inflight["valid_pairs"] == 3
    assert inflight["failed_pairs"] == 0
    assert inflight["complete"] is False
    assert inflight["decision_formed"] is False
    assert inflight["counts_toward_n_experiments"] is False
    assert status["last_completed_result"]["reason"] == "agent_quality_blocked"


def test_campaign_summary_separates_telemetry_failed_experiment(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = _step()
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=16,
            wins=0,
            losses=0,
            ties=16,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="fail",
        reason_codes=(
            "TELEMETRY_VALIDATION_REPAIRABLE",
            "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
            "SCREENING_FAIL_WIN_RATE",
        ),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/telemetry.json",
        candidate_surface_runtime_summary={
            "selected_surface": "generic_surface",
            "declaration_source_digest": "surface-digest-activation",
            "telemetry_guard": {
                "passed": False,
                "candidate_runs": 16,
                "declaration_source_digest": "guard-digest-activation",
                "failures": [
                    {
                        "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                        "severity": "fail",
                        "category": "activation",
                        "mechanism": "activation_probe",
                        "field": "mechanisms.activation_probe.active",
                        "runtime_role": "activation",
                        "candidate_missing": 16,
                        "candidate_present": 0,
                        "candidate_positive": 0,
                    }
                ],
            },
        },
    )
    step.decision = Decision.CONTINUE_EXPLORE
    step.decision_reason_codes = ("TELEMETRY_VALIDATION_REPAIRABLE",)

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
        stopped_reason="max_rounds_exhausted",
    )

    assert summary["screened_experiments"] == 0
    assert summary["telemetry_failed_experiments"] == 1
    assert summary["telemetry_failure_details"][0]["repairable"] is True
    summary_step = summary["steps"][0]
    assert summary_step["screened_experiment"] is True
    assert summary_step["screened_experiment_effective"] is False
    protocol = summary_step["protocol_result"]
    assert protocol["screened_experiment_effective"] is False
    assert "activation_probe" in protocol["telemetry_validation_feedback"]
    assert "candidate_missing=16" in protocol["telemetry_validation_feedback"]
    detail = protocol["telemetry_failure_details"][0]
    assert detail["stage"] == "screening"
    assert detail["category"] == "activation"
    assert detail["mechanism_id"] == "activation_probe"
    assert detail["surface_field_id"] == "mechanisms.activation_probe.active"
    assert detail["runtime_role"] == "activation"
    assert detail["missing_fields"] == ["mechanisms.activation_probe.active"]
    assert detail["repairable"] is True
    assert detail["declaration_source_digest"] == "guard-digest-activation"


def test_campaign_summary_counts_formal_screening_telemetry_guard_failure(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "screened_experiments": 1,
            "telemetry_failed_experiments": 0,
            "telemetry_failed_experiments_by_category": {},
        },
    )
    step = _step()
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=step.protocol_result.stats,
        gate_outcome="fail",
        reason_codes=("TELEMETRY_GUARD_FAILED", "TELEMETRY_ACTIVITY_NOT_OBSERVED"),
        exposed_summary="screening telemetry guard failed",
        raw_metrics_ref="/tmp/activity-telemetry.json",
        candidate_surface_runtime_summary={
            "selected_surface": "generic_surface",
            "declaration_source_digest": "surface-digest-activity",
            "telemetry_guard": {
                "passed": False,
                "candidate_runs": 16,
                "declaration_source_digest": "guard-digest-activity",
                "failures": [
                    {
                        "code": "TELEMETRY_ACTIVITY_NOT_OBSERVED",
                        "severity": "fail",
                        "category": "activity",
                        "mechanism": "activity_probe",
                        "field": "activity_counter",
                        "runtime_role": "activity",
                        "candidate_present": 16,
                        "candidate_positive": 0,
                    }
                ],
            },
        },
    )
    step.decision = Decision.ABANDON
    step.decision_reason_codes = ("SCREENING_TELEMETRY_FAILED",)

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    assert summary["screened_experiments"] == 1
    assert summary["telemetry_failed_experiments"] == 1
    assert summary["telemetry_failed_experiments_by_category"] == {"activity": 1}
    assert summary["telemetry_failure_details"][0]["mechanism_id"] == (
        "activity_probe"
    )
    summary_step = summary["steps"][0]
    assert summary_step["screened_experiment_effective"] is True
    assert summary_step["telemetry_guard_failed"] is True
    assert summary_step["telemetry_failure_categories"] == ["activity"]
    assert summary_step["telemetry_failure_details"][0]["category"] == "activity"
    protocol = summary_step["protocol_result"]
    assert protocol["telemetry_guard_failed"] is True
    assert protocol["telemetry_failure_categories"] == ["activity"]
    detail = protocol["telemetry_failure_details"][0]
    assert detail["schema"] == "scion.telemetry_decision_detail.v1"
    assert detail["stage"] == "screening"
    assert detail["category"] == "activity"
    assert detail["mechanism_id"] == "activity_probe"
    assert detail["surface_field_id"] == "activity_counter"
    assert detail["runtime_role"] == "activity"
    assert detail["missing_fields"] == []
    assert detail["invalid_fields"] == []
    assert detail["repairable"] is False
    assert detail["declaration_source_digest"] == "guard-digest-activity"
    assert protocol["auxiliary_protocol_reason_codes"] == [
        "TELEMETRY_GUARD_FAILED",
        "TELEMETRY_ACTIVITY_NOT_OBSERVED",
    ]
    assert protocol["effective_reason_codes"] == ["SCREENING_TELEMETRY_FAILED"]


def test_campaign_summary_does_not_count_proposal_preflight_telemetry_failure(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = StepRecord(
        round_num=1,
        branch_id="branch-1",
        hypothesis=_hypothesis("Rejected before formal screening."),
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="agent_quality_blocked",
        failure_detail=(
            "proposal.schema_preview:C11 telemetry preflight failed: "
            "TELEMETRY_ACTIVITY_NOT_OBSERVED"
        ),
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    assert summary["screened_experiments"] == 0
    assert summary["telemetry_failed_experiments"] == 0
    assert summary["telemetry_failed_experiments_by_category"] == {}
    assert summary["steps"][0]["telemetry_guard_failed"] is False


def test_campaign_summary_exposes_runtime_veto_decision_reason_codes(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = _step()
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=step.protocol_result.stats,
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/runtime-timeout.json",
    )
    step.decision = Decision.ABANDON
    step.decision_reason_codes = ("CANDIDATE_RUNTIME_FAILURE",)

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    protocol = summary["steps"][0]["protocol_result"]
    assert protocol["protocol_reason_codes"] == ["SCREENING_FAIL_WIN_RATE"]
    assert protocol["decision_reason_codes"] == ["CANDIDATE_RUNTIME_FAILURE"]
    assert protocol["effective_reason_codes"] == ["CANDIDATE_RUNTIME_FAILURE"]
    assert protocol["effective_reason_source"] == "decision_engine"
