"""Focused tests split from test_evidence_recorder.py."""

from .evidence_recorder_test_support import *  # noqa: F401,F403

def test_record_step_and_summary_preserve_current_fields(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
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
    assert summary["champion_version"] == 7
    assert summary["champion_weight_revision"] == 2
    assert summary["n_active_branches"] == 0
    assert summary["budget_utilization"] == 0.25
    assert summary["cache_stats"]["total_tokens"] == 100
    assert summary["cache_stats"]["cache_read_tokens"] == 25

    summary_step = summary["steps"][0]
    assert summary_step["round"] == 3
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
