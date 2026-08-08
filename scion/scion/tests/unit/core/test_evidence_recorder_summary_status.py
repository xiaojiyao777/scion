"""Focused tests split from test_evidence_recorder.py."""

from dataclasses import replace

import pytest

from .evidence_recorder_test_support import *  # noqa: F401,F403
from scion.core.execution_outcome import ExecutionOutcome
from scion.core.run_validity import (
    RUN_VALIDITY_INVALID_INFRA_ONLY,
    RUN_VALIDITY_VALID_BUT_INCOMPLETE,
    RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED,
)
from scion.core.models import CaseAggregateFeedback, Decision, DecisionFeatures
from scion.core.evidence_recording.accounting_quality_blocks import (
    quality_block_ledger,
)
from scion.core.evidence_recording.summary_cache import _campaign_cache_stats
from scion.core.step_result import StepResult


def _outcome_counts(**overrides: int) -> dict[str, int]:
    counts = {outcome.value: 0 for outcome in ExecutionOutcome}
    counts.update(overrides)
    return counts


def _non_evaluated_step(
    outcome: ExecutionOutcome,
    *,
    reason_code: str,
    detail: str,
    round_num: int = 1,
) -> StepRecord:
    return StepRecord(
        round_num=round_num,
        branch_id="branch-1",
        hypothesis=_hypothesis("Execution ended before protocol evaluation."),
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage=None,
        failure_detail=None,
        attempt_kind="execution_outcome",
        execution_outcome=outcome,
        execution_outcome_reason_code=reason_code,
        execution_outcome_detail=detail,
        execution_outcome_provenance={
            "owner": "fixture_execution",
            "stage": "execution",
        },
    )




def _run_validity_completion_projection(payload: dict) -> dict:
    validity = payload["run_validity"]
    return {
        "status": validity["status"],
        "reason": validity["reason"],
        "valid": validity["valid"],
        "requested_rounds": validity["requested_rounds"],
        "effective_rounds_completed": validity["effective_rounds_completed"],
        "completed_requested_rounds": validity["completed_requested_rounds"],
        "complete": validity["complete"],
        "interrupted": validity["interrupted"],
        "partial_campaign_evidence": validity["partial_campaign_evidence"],
        "protocol_in_flight": validity["protocol_in_flight"],
        "partial_in_flight": validity["partial_in_flight"],
        "completeness_status": validity["completeness_status"],
        "stopped_reason": validity["stopped_reason"],
        "failure_categories": validity["failure_categories"],
        "infra_failure_attempts": validity["infra_failure_attempts"],
        "noninfra_failure_attempts": validity["noninfra_failure_attempts"],
        "top_run_validity_status": payload["run_validity_status"],
        "top_completed_requested_rounds": payload["completed_requested_rounds"],
        "top_run_complete": payload["run_complete"],
        "top_run_completeness_status": payload["run_completeness_status"],
    }






@pytest.mark.parametrize("measurement_governance", ["record_only", "on"])
def test_summary_and_status_expose_measurement_governance_consistently(
    tmp_path: Path,
    measurement_governance: str,
) -> None:
    measurement_readiness = {
        "status": "degraded",
        "reason_code": "calibration_stale",
        "calibration_age_days": 161,
        "calibration_max_age_days": 90,
        "n_pairs": 48,
        "mde_at_power_80": 4.0,
        "noise_band_p90_abs": 7.5,
        "effect_to_mde_ratio": 0.5,
        "signal_to_noise_tier": "marginal",
        "decision_features_excluded": True,
        "calibration_ref": "/tmp/internal-aa-noise-floor.json",
    }
    recorder = EvidenceRecorder(
        campaign_id="camp-measurement-governance",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-measurement-governance",
            "n_experiments": 0,
            "screened_experiments": 0,
            "total_rounds": 0,
            "proposal_attempts": 0,
            "proposal_attempts_consumed": 0,
            "n_steps": 0,
            "n_active_branches": 0,
            "champion_version": 7,
            "measurement_governance": measurement_governance,
            "measurement_readiness": measurement_readiness,
            "budget_remaining": 1.0,
            "branches": [],
            "branch_cards": [],
        },
    )

    status = recorder.write_status()
    summary = recorder.write_campaign_summary(
        step_history=[],
        round_num=0,
        champion=_champion(),
        measurement_governance=measurement_governance,
        measurement_readiness=measurement_readiness,
    )

    assert status["measurement_governance"] == measurement_governance
    assert summary["measurement_governance"] == measurement_governance
    assert status["measurement_readiness"] == summary["measurement_readiness"]
    assert status["measurement_readiness"]["status"] == "degraded"
    assert status["measurement_readiness"]["reason_code"] == "calibration_stale"
    assert status["measurement_readiness"]["mde_at_power_80"] == 4.0
    assert "calibration_ref" not in status["measurement_readiness"]
    assert "calibration_ref" not in summary["measurement_readiness"]




def test_campaign_summary_exposes_contract_diagnostics(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-contract-diag", campaign_dir=tmp_path)
    diagnostic = {
        "name": "C10_novelty",
        "passed": True,
        "severity": "light",
        "detail": "duplicate structured novelty_signature",
        "metadata": {
            "gate_action": "diagnostic",
            "diagnostic_kind": "semantic_identity_duplicate",
        },
    }
    step = replace(
        _step("/tmp/metrics-round-1.json"),
        contract_diagnostics=(diagnostic,),
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    assert summary["steps"][0]["contract_diagnostics"] == [diagnostic]






def test_campaign_summary_exposes_screening_visibility_fields(
    tmp_path: Path,
) -> None:
    base_protocol = _protocol_result("/tmp/metrics-visibility.json")
    protocol = replace(
        base_protocol,
        stats=replace(base_protocol.stats, runtime_pairs=0),
        champion_cache_hits=2,
        champion_cache_misses=3,
        champion_cached_runtime_pairs=4,
        runtime_confidence="low_cached_champion",
        runtime_model="budget_exhausting",
        opportunity_status="opportunity_poor",
        opportunity_diagnostics=("primary mechanism did not trigger",),
        mechanism_evidence={
            "primary_mechanism": "candidate_list",
            "primary_activation_status": "missing",
            "primary_effect_status": "not_observed",
        },
        candidate_surface_runtime_summary={
            "fields": {
                "candidate_elapsed_ms": {
                    "present": 2,
                    "missing": 0,
                    "empty": 0,
                    "failed": 0,
                }
            }
        },
    )
    step = replace(_step("/tmp/metrics-visibility.json"), protocol_result=protocol)
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
        stopped_reason="max_rounds",
    )

    protocol_summary = summary["steps"][0]["protocol_result"]
    assert protocol_summary["champion_cache_hits"] == 2
    assert protocol_summary["champion_cache_misses"] == 3
    assert protocol_summary["champion_cached_runtime_pairs"] == 4
    assert protocol_summary["runtime_confidence"] == "low_cached_champion"
    assert protocol_summary["runtime_evidence_confidence"] == "low_cached_champion"
    assert protocol_summary["runtime_model"] == "budget_exhausting"
    assert protocol_summary["runtime_evidence_policy"]["runtime_model"] == (
        "budget_exhausting"
    )
    assert protocol_summary["runtime_evidence_policy"][
        "runtime_model_interpretation"
    ] == "budget_exhausting_runtime_aggregates_observational_not_standalone"
    assert protocol_summary["runtime_evidence_policy"][
        "decision_features_excluded"
    ] is True
    assert protocol_summary["opportunity_status"] == "opportunity_poor"
    assert protocol_summary["opportunity_diagnostics"] == [
        "primary mechanism did not trigger"
    ]
    assert protocol_summary["mechanism_evidence"] == {
        "primary_mechanism": "candidate_list",
        "primary_activation_status": "missing",
        "primary_effect_status": "not_observed",
    }
    assert protocol_summary["runtime_aggregate_exclusion"]["reason"] == (
        "low_cached_champion"
    )
    assert protocol_summary["runtime_aggregate_exclusion"][
        "candidate_runtime_pair_evidence_count"
    ] == 2


def test_campaign_summary_marks_planner_loop_budget_as_diagnostic_after_formal_round(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = replace(
        _step("/tmp/metrics-formal-success.json"),
        proposal_session_ref={
            "schema_version": "agentic-proposal-session.v1",
            "session_id": "session-budget",
            "termination_reason": "tool_loop_limit",
            "status": "partial_hypothesis_only",
            "failure_category": "tool_budget_exhausted",
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=3,
        champion=_champion(),
        stopped_reason="max_rounds",
    )

    session_ref = summary["steps"][0]["proposal_session_ref"]
    assert session_ref["formal_round_succeeded"] is True
    assert session_ref["diagnostic_only"] is True
    assert session_ref["planner_loop_diagnostic"] == {
        "schema_version": "planner_loop_diagnostic.v1",
        "category": "planner_loop_diagnostic",
        "code": "tool_budget_exhausted",
        "failure_category": "tool_budget_exhausted",
        "termination_reason": "tool_loop_limit",
        "diagnostic_only": True,
        "formal_round_succeeded": True,
    }
    assert summary["steps"][0]["protocol_result"]["gate_outcome"] == "pass"


def test_campaign_summary_persists_compact_direct_attempt_ref(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = replace(
        _step("/tmp/metrics-direct-attempt.json"),
        proposal_session_ref={
            "schema_version": "proposal-attempt-ref.v1",
            "attempt_id": "attempt-1",
            "runtime_mode": "direct_v3",
            "phase": "code",
            "status": "generated",
            "transition_reason": "generated",
            "failure_lane": None,
            "lineage_event_id": "event-1",
            "hypothesis_id": "hypothesis-1",
            "artifact_ref": "artifacts/llm_traces/code.json",
            "prompt_manifest_ref": "artifacts/llm_traces/code.json#/prompt_manifest",
            "prompt_hash": "prompt-hash",
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
        stopped_reason="max_rounds",
    )

    persisted = summary["steps"][0]["proposal_session_ref"]
    assert persisted["schema_version"] == "proposal-attempt-ref.v1"
    assert persisted["attempt_id"] == "attempt-1"
    assert persisted["runtime_mode"] == "direct_v3"
    assert persisted["phase"] == "code"
    assert persisted["status"] == "generated"
    assert persisted["lineage_event_id"] == "event-1"
    assert persisted["hypothesis_id"] == "hypothesis-1"
    assert persisted["prompt_hash"] == "prompt-hash"


def test_scheduler_metadata_persists_to_summary_and_lineage(tmp_path: Path) -> None:
    registry = LineageRegistry(str(tmp_path / "scion.db"))
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        registry=registry,
        state_provider=lambda: {
            "n_experiments": 1,
            "proposal_attempts": 1,
            "screened_experiments": 1,
            "branches": [],
        },
    )
    step_history: list[StepRecord] = []
    recorder.record_step(
        replace(_step("/tmp/metrics-scheduler.json"), round_num=1),
        step_history,
    )

    recorder.record_scheduler_result(
        StepResult(
            action="explore",
            branch_id="branch-1",
            decision=Decision.CONTINUE_EXPLORE,
            reason="decision=continue_explore; scheduler_slot=refine_active",
            scheduler_slot="refine_active",
            scheduler_reason="existing_branch_selected",
            scheduler_audit_metadata={
                "scheduler_action": "run_existing",
                "pre_finalizer_scheduler_action": "run_existing",
                "pre_finalizer_scheduler_slot": "refine_active",
                "post_finalizer_actual_branch_action": "continue_same_branch",
                "post_finalizer_next_proposal_policy": "same_branch_eligible",
                "same_branch_refinement_not_selected_reason": "",
            },
        ),
        step_history,
    )
    summary = recorder.write_campaign_summary(
        step_history=step_history,
        round_num=1,
        champion=_champion(),
        stopped_reason="max_rounds",
    )

    assert step_history[0].scheduler_slot == "refine_active"
    assert step_history[0].scheduler_reason == "existing_branch_selected"
    summary_step = summary["steps"][0]
    assert summary_step["scheduler_slot"] == "refine_active"
    assert summary_step["scheduler_reason"] == "existing_branch_selected"
    assert summary_step["scheduler_audit_metadata"]["scheduler_action"] == (
        "run_existing"
    )

    events = registry.query_by_branch("branch-1")
    scheduler_events = [
        event for event in events if event["event_kind"] == "scheduler_result"
    ]
    assert len(scheduler_events) == 1
    event = scheduler_events[0]
    assert event["scheduler_slot"] == "refine_active"
    assert event["scheduler_reason"] == "existing_branch_selected"
    assert event["decision_features_json"] == ""
    payload = json.loads(event["audit_payload_json"])
    assert payload["scheduler_slot"] == "refine_active"
    assert payload["scheduler_reason"] == "existing_branch_selected"
    assert payload["scheduler_audit_metadata"]["scheduler_action"] == "run_existing"
    assert payload["pre_finalizer_scheduler_action"] == "run_existing"
    assert payload["pre_finalizer_scheduler_slot"] == "refine_active"
    assert payload["post_finalizer_actual_branch_action"] == "continue_same_branch"
    assert payload["post_finalizer_next_proposal_policy"] == "same_branch_eligible"
    assert payload["step_round"] == 1


def test_campaign_summary_promotes_runtime_budget_diagnostics(tmp_path: Path) -> None:
    diagnostic = {
        "schema": "scion.runtime_budget_diagnostic.v1",
        "code": "SCREENING_RUNTIME_BUDGET_SATURATION",
        "stage": "screening",
        "severity": "warn",
        "repairable": True,
        "total_pairs": 16,
        "threshold_ratio": 0.9,
        "saturation_ratio": 0.97,
    }
    step = _step("/tmp/metrics-runtime-budget.json")
    protocol = replace(
        step.protocol_result,
        candidate_surface_runtime_summary={
            "selected_surface": "solver_design",
            "runtime_budget_diagnostic": diagnostic,
        },
    )
    step = replace(step, protocol_result=protocol)
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "n_experiments": 1,
            "proposal_attempts": 1,
            "screened_experiments": 1,
            "branches": [],
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
        stopped_reason="max_rounds",
    )

    assert summary["runtime_budget_diagnostic_count"] == 1
    assert summary["runtime_budget_diagnostics"][0]["code"] == (
        "SCREENING_RUNTIME_BUDGET_SATURATION"
    )
    protocol_summary = summary["steps"][0]["protocol_result"]
    assert protocol_summary["runtime_budget_diagnostic"]["saturation_ratio"] == 0.97


def test_status_promotes_runtime_budget_diagnostic_top_level(tmp_path: Path) -> None:
    diagnostic = {
        "schema": "scion.runtime_budget_diagnostic.v1",
        "code": "SCREENING_RUNTIME_BUDGET_SATURATION",
        "stage": "screening",
        "severity": "warn",
        "repairable": True,
        "total_pairs": 16,
        "threshold_ratio": 0.9,
        "saturation_ratio": 0.97,
    }
    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()
    metrics_path = metrics_dir / "runtime-budget.json"
    metrics_path.write_text(
        json.dumps(
            {
                "stage": "screening",
                "complete": True,
                "total_pairs": 16,
                "attempted_pairs": 16,
                "valid_pairs": 15,
                "failed_pairs": 1,
                "candidate_failed_pairs": 0,
                "champion_failed_pairs": 1,
                "screening_evidence_status": "partial_champion_evidence",
                "screening_partial_champion_evidence": {
                    "reason_code": "SCREENING_PARTIAL_CHAMPION_EVIDENCE",
                    "champion_failed_pairs": 1,
                    "decision_complete_evidence": False,
                },
                "candidate_surface_runtime_summary": {
                    "runtime_budget_diagnostic": diagnostic,
                },
            }
        ),
        encoding="utf-8",
    )
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {"campaign_id": "camp-1", "screened_experiments": 1},
    )

    recorder.record_protocol_progress(
        branch_id="branch-1",
        stage="screening",
        raw_metrics_ref=str(metrics_path),
    )

    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["runtime_budget_diagnostic"]["code"] == (
        "SCREENING_RUNTIME_BUDGET_SATURATION"
    )
    assert status["runtime_budget_diagnostic_code"] == (
        "SCREENING_RUNTIME_BUDGET_SATURATION"
    )
    assert status["current_progress"]["runtime_budget_diagnostic"]["saturation_ratio"] == (
        0.97
    )
    assert status["in_flight_protocol"]["runtime_budget_diagnostic_code"] == (
        "SCREENING_RUNTIME_BUDGET_SATURATION"
    )
    assert status["current_progress"]["screening_evidence_status"] == (
        "partial_champion_evidence"
    )
    assert status["current_progress"]["failed_pairs"] == 1
    assert status["current_progress"]["candidate_failed_pairs"] == 0
    assert status["current_progress"]["champion_failed_pairs"] == 1
    assert status["current_progress"]["screening_partial_champion_evidence"] == {
        "reason_code": "SCREENING_PARTIAL_CHAMPION_EVIDENCE",
        "champion_failed_pairs": 1,
        "decision_complete_evidence": False,
    }
    assert status["in_flight_protocol"]["screening_evidence_status"] == (
        "partial_champion_evidence"
    )
    assert status["in_flight_protocol"]["failed_pairs"] == 1
    assert status["in_flight_protocol"]["candidate_failed_pairs"] == 0
    assert status["in_flight_protocol"]["champion_failed_pairs"] == 1
    assert status["in_flight_protocol"][
        "screening_partial_champion_evidence"
    ] == status["current_progress"]["screening_partial_champion_evidence"]
    assert {
        "screening_evidence_status",
        "screening_partial_champion_evidence",
    }.isdisjoint(DecisionFeatures.__dataclass_fields__)




def test_status_and_summary_report_all_active_slots_without_truncation(
    tmp_path: Path,
) -> None:
    def active_row(branch_id: str) -> dict:
        return {
            "id": branch_id,
            "branch_card": {
                "branch_id": branch_id,
                "status": "explore",
                "scheduling_status": {
                    "consumes_active_slot": True,
                    "schedulable": True,
                    "lane": "explore",
                    "release_reason": None,
                },
            },
        }

    state = {
        "n_experiments": 3,
        "proposal_attempts": 3,
        "screened_experiments": 3,
        "n_active_branches": 3,
        "active_slots": {
            "used": 3,
            "max": 2,
            "available": 0,
            "branch_ids": ["branch-a", "branch-b", "branch-c"],
        },
        "branches": [
            active_row("branch-a"),
            active_row("branch-b"),
            active_row("branch-c"),
        ],
    }
    recorder = EvidenceRecorder(
        campaign_id="camp-active-slots",
        campaign_dir=tmp_path,
        state_provider=lambda: state,
    )

    status = recorder.write_status()
    summary = recorder.write_campaign_summary(
        step_history=[],
        round_num=0,
        champion=_champion(),
        stopped_reason="max_rounds",
    )

    for payload in (status, summary):
        assert payload["n_active_branches"] == 3
        assert payload["active_slots"]["used"] == 3
        assert payload["active_slots"]["max"] == 2
        assert payload["active_slots"]["available"] == 0
        assert payload["active_slots"]["branch_ids"] == [
            "branch-a",
            "branch-b",
            "branch-c",
        ]












def test_summary_cache_helper_preserves_step_record_fallback_schema(
    tmp_path: Path,
) -> None:
    cache_stats = _campaign_cache_stats(
        [_step("/tmp/metrics-round-3.json")],
        campaign_dir=tmp_path,
    )

    llm_accounting = cache_stats.pop("llm_accounting")
    assert cache_stats == {
        "total_tokens": 100,
        "prompt_tokens_total": 100,
        "input_tokens": 100,
        "cache_read_tokens": 25,
        "cache_miss_tokens": 75,
        "cache_create_tokens": 75,
        "cache_hit_rate": 0.25,
        "cache_accounting_modes": {},
        "output_tokens": 0,
        "calls": 0,
        "source": "step_records",
        "by_request_kind_provider": [],
        "repeated_cache_create_groups": [],
        "repeated_cache_key_groups": [],
        "repeated_cache_key_no_read": [],
    }
    assert llm_accounting["source"] == "step_records"
    assert llm_accounting["request_kind_counts"] == {}
    assert llm_accounting["provider_counts"] == {}
    assert llm_accounting["model_counts"] == {}
    assert llm_accounting["token_sums"]["input_tokens"] is None
    assert llm_accounting["token_field_availability"]["input_tokens"][
        "sum_is_null_when_all_values_unavailable"
    ] is True


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
        stopped_reason="api_balance_exhausted",
    )

    assert summary["stopped_reason"] == "api_balance_exhausted"
    assert summary["balance_exhausted"] is True
    assert "circuit_breaker_tripped" not in summary
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
        },
    )

    status = recorder.write_status(stopped_reason="api_balance_exhausted")
    on_disk = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))

    assert status["stopped_reason"] == "api_balance_exhausted"
    assert status["balance_exhausted"] is True
    assert "circuit_breaker_tripped" not in status
    assert status["stop_category"] == "provider_error"
    assert status["provider_error"]["category"] == "balance_exhausted"
    assert on_disk["stopped_reason"] == "api_balance_exhausted"


def test_status_reports_api_balance_partial_run_completion_aliases(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-partial-balance",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-partial-balance",
            "n_experiments": 6,
            "screened_experiments": 6,
            "execution_outcome_counts": _outcome_counts(
                evaluated=6,
                blocked_infra=1,
            ),
        },
    )

    status = recorder.write_status(
        stopped_reason="api_balance_exhausted",
        loop_status={
            "requested_rounds": 12,
            "total_rounds": 7,
            "proposal_attempts": 7,
            "proposal_attempts_consumed": 7,
            "effective_rounds_completed": 6,
            "failure_categories": {"infra": 1},
            "execution_outcome_counts": _outcome_counts(
                evaluated=6,
                blocked_infra=1,
            ),
        },
    )

    validity = status["run_validity"]
    assert validity["status"] == "valid"
    assert validity["reason"] == RUN_VALIDITY_VALID_BUT_INCOMPLETE
    assert validity["valid"] is True
    assert validity["completed_requested_rounds"] is False
    assert validity["complete"] is False
    assert validity["stopped_reason"] == "api_balance_exhausted"
    assert status["last_stop_reason"] == "api_balance_exhausted"
    assert status["completed_requested_rounds"] is False
    assert status["run_complete"] is False
    assert status["run_completeness_status"] == validity["completeness_status"]


def test_status_reports_infra_only_run_validity(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-infra",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-infra",
            "n_experiments": 0,
            "screened_experiments": 0,
            "execution_outcome_counts": _outcome_counts(blocked_infra=12),
        },
    )

    status = recorder.write_status(
        stopped_reason="proposal_attempt_limit_exhausted",
        loop_status={
            "requested_rounds": 4,
            "total_rounds": 12,
            "proposal_attempts": 12,
            "proposal_attempts_consumed": 12,
            "effective_rounds_completed": 0,
            "failure_categories": {"infra": 12},
            "execution_outcome_counts": _outcome_counts(blocked_infra=12),
        },
    )

    assert status["run_validity"]["status"] == "invalid"
    assert status["run_validity"]["reason"] == RUN_VALIDITY_INVALID_INFRA_ONLY
    assert status["run_validity"]["infra_failure_attempts"] == 12
    assert status["run_validity_status"] == RUN_VALIDITY_INVALID_INFRA_ONLY
    assert status["run_validity"]["partial_in_flight"] is False
    assert status["run_validity"]["completeness_status"] == "incomplete"


def test_campaign_summary_reports_infra_only_run_validity(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-infra",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-infra",
            "n_experiments": 0,
            "screened_experiments": 0,
            "execution_outcome_counts": _outcome_counts(blocked_infra=1),
        },
    )
    recorder.write_status(
        loop_status={
            "requested_rounds": 4,
            "total_rounds": 12,
            "proposal_attempts": 12,
            "proposal_attempts_consumed": 12,
            "effective_rounds_completed": 0,
            "failure_categories": {"infra": 12},
        },
    )
    step = StepRecord(
        round_num=1,
        branch_id="branch-1",
        hypothesis=_hypothesis("Provider failed before hypothesis generation."),
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="proposal",
        failure_detail=(
            "agentic_proposal:hypothesis_generation_failed: Tool call failed "
            "after 3 transient API attempt(s). Last error: HTTP 503 "
            "no_available_accounts"
        ),
        attempt_kind="proposal_block",
        execution_outcome=ExecutionOutcome.BLOCKED_INFRA,
        execution_outcome_reason_code="PROVIDER_UNAVAILABLE",
        execution_outcome_detail="Provider unavailable before evaluation.",
        execution_outcome_provenance={
            "owner": "fixture_provider",
            "stage": "proposal",
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=12,
        champion=_champion(),
        stopped_reason="proposal_attempt_limit_exhausted",
    )

    assert summary["run_validity"]["status"] == "invalid"
    assert summary["run_validity"]["reason"] == RUN_VALIDITY_INVALID_INFRA_ONLY
    assert summary["run_validity"]["partial_in_flight"] is False
    assert summary["run_validity"]["completeness_status"] == "incomplete"
    assert summary["failure_categories"] == {"infra": 12}
    assert summary["stopped_reason"] == "proposal_attempt_limit_exhausted"


def test_status_and_summary_consistent_for_zero_candidate_api_balance_infra_only(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-zero-candidate-balance",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-zero-candidate-balance",
            "n_experiments": 0,
            "screened_experiments": 0,
            "execution_outcome_counts": _outcome_counts(blocked_infra=1),
        },
    )
    loop_status = {
        "requested_rounds": 12,
        "total_rounds": 1,
        "proposal_attempts": 1,
        "proposal_attempts_consumed": 1,
        "effective_rounds_completed": 0,
        "failure_categories": {"infra": 1},
        "execution_outcome_counts": _outcome_counts(blocked_infra=1),
    }

    status = recorder.write_status(
        stopped_reason="api_balance_exhausted",
        loop_status=loop_status,
    )
    step = StepRecord(
        round_num=1,
        branch_id="branch-1",
        hypothesis=_hypothesis("Provider quota failed before proposal completion."),
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="proposal",
        failure_detail=(
            "agentic_proposal:hypothesis_generation_failed: Transient provider "
            "error: Error code: 403 - account balance is insufficient"
        ),
        attempt_kind="proposal_block",
        execution_outcome=ExecutionOutcome.BLOCKED_INFRA,
        execution_outcome_reason_code="ACCOUNT_BALANCE_EXHAUSTED",
        execution_outcome_detail="Account balance exhausted before evaluation.",
        execution_outcome_provenance={
            "owner": "fixture_provider",
            "stage": "proposal",
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
        stopped_reason="api_balance_exhausted",
    )

    assert _run_validity_completion_projection(status) == (
        _run_validity_completion_projection(summary)
    )
    assert status["run_validity"]["reason"] == RUN_VALIDITY_INVALID_INFRA_ONLY
    assert status["run_validity"]["partial_in_flight"] is False
    assert status["run_validity"]["completeness_status"] == "incomplete"
    assert summary["run_validity"]["partial_in_flight"] is False
    assert summary["run_completeness_status"] == "incomplete"


def test_campaign_summary_reports_api_balance_partial_completion_aliases(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-partial-balance",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-partial-balance",
            "n_experiments": 6,
            "screened_experiments": 6,
            "execution_outcome_counts": _outcome_counts(
                evaluated=6,
                blocked_infra=1,
            ),
        },
    )
    recorder.write_status(
        loop_status={
            "requested_rounds": 12,
            "total_rounds": 7,
            "proposal_attempts": 7,
            "proposal_attempts_consumed": 7,
            "effective_rounds_completed": 6,
            "failure_categories": {"infra": 1},
        },
    )
    steps = [
        replace(_step(f"/tmp/metrics-round-{idx}.json"), round_num=idx)
        for idx in range(1, 7)
    ]
    steps.append(
        _non_evaluated_step(
            ExecutionOutcome.BLOCKED_INFRA,
            reason_code="ACCOUNT_BALANCE_EXHAUSTED",
            detail="Account balance exhausted before evaluation.",
            round_num=7,
        )
    )

    summary = recorder.write_campaign_summary(
        step_history=steps,
        round_num=7,
        champion=_champion(),
        stopped_reason="api_balance_exhausted",
    )

    validity = summary["run_validity"]
    assert summary["requested_rounds"] == 12
    assert summary["effective_rounds_completed"] == 6
    assert validity["reason"] == RUN_VALIDITY_VALID_BUT_INCOMPLETE
    assert validity["completed_requested_rounds"] is False
    assert validity["complete"] is False
    assert validity["partial_in_flight"] is True
    assert validity["partial_campaign_evidence"] is True
    assert validity["protocol_in_flight"] is False
    assert validity["completeness_status"] == "incomplete"
    assert summary["last_stop_reason"] == "api_balance_exhausted"
    assert summary["completed_requested_rounds"] is False
    assert summary["run_complete"] is False
    assert summary["run_completeness_status"] == validity["completeness_status"]


def test_status_and_summary_consistent_for_partial_api_balance_interrupted(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-partial-balance",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-partial-balance",
            "n_experiments": 6,
            "screened_experiments": 6,
            "execution_outcome_counts": _outcome_counts(
                evaluated=6,
                blocked_infra=1,
            ),
        },
    )
    loop_status = {
        "requested_rounds": 12,
        "total_rounds": 7,
        "proposal_attempts": 7,
        "proposal_attempts_consumed": 7,
        "effective_rounds_completed": 6,
        "failure_categories": {"infra": 1},
        "execution_outcome_counts": _outcome_counts(
            evaluated=6,
            blocked_infra=1,
        ),
    }

    status = recorder.write_status(
        stopped_reason="api_balance_exhausted",
        loop_status=loop_status,
    )
    steps = [
        replace(_step(f"/tmp/metrics-round-{idx}.json"), round_num=idx)
        for idx in range(1, 7)
    ]
    steps.append(
        _non_evaluated_step(
            ExecutionOutcome.BLOCKED_INFRA,
            reason_code="ACCOUNT_BALANCE_EXHAUSTED",
            detail="Account balance exhausted before evaluation.",
            round_num=7,
        )
    )
    summary = recorder.write_campaign_summary(
        step_history=steps,
        round_num=7,
        champion=_champion(),
        stopped_reason="api_balance_exhausted",
    )

    assert _run_validity_completion_projection(status) == (
        _run_validity_completion_projection(summary)
    )
    assert status["run_validity"]["reason"] == RUN_VALIDITY_VALID_BUT_INCOMPLETE
    assert status["run_validity"]["partial_in_flight"] is True
    assert status["run_validity"]["partial_campaign_evidence"] is True
    assert status["run_validity"]["protocol_in_flight"] is False
    assert status["run_validity"]["completeness_status"] == "incomplete"
    assert summary["run_validity"]["partial_in_flight"] is True
    assert summary["run_validity"]["partial_campaign_evidence"] is True
    assert summary["run_validity"]["protocol_in_flight"] is False
    assert summary["run_completeness_status"] == "incomplete"


def test_status_reports_valid_partial_interrupted_run_completeness(
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
                "attempted_pairs": 6,
                "valid_pairs": 6,
                "failed_pairs": 0,
                "candidate_failed_pairs": 0,
                "champion_failed_pairs": 0,
            }
        ),
        encoding="utf-8",
    )
    recorder = EvidenceRecorder(
        campaign_id="camp-partial",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-partial",
            "n_experiments": 3,
            "screened_experiments": 3,
            "execution_outcome_counts": _outcome_counts(
                evaluated=3,
                interrupted=1,
            ),
        },
    )
    recorder.record_protocol_progress(
        branch_id="branch-4",
        stage="screening",
        raw_metrics_ref=str(metrics_path),
        case="/tmp/private/current.vrp",
        seed=77,
    )

    status = recorder.write_status(
        stopped_reason="signal:SIGTERM",
        loop_status={
            "requested_rounds": 4,
            "total_rounds": 4,
            "proposal_attempts": 4,
            "proposal_attempts_consumed": 4,
            "effective_rounds_completed": 3,
            "execution_outcome_counts": _outcome_counts(
                evaluated=3,
                interrupted=1,
            ),
        },
    )

    validity = status["run_validity"]
    assert validity["status"] == "valid"
    assert validity["reason"] == RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED
    assert validity["valid"] is True
    assert validity["requested_rounds"] == 4
    assert validity["effective_rounds_completed"] == 3
    assert validity["completed_requested_rounds"] is False
    assert validity["complete"] is False
    assert validity["interrupted"] is True
    assert validity["partial_in_flight"] is True
    assert validity["partial_campaign_evidence"] is True
    assert validity["protocol_in_flight"] is True
    assert validity["completeness_status"] == "partial_interrupted"
    assert validity["stopped_reason"] == "signal:SIGTERM"
    assert "partial evidence" in validity["operator_action"]
    assert status["run_validity_status"] == RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED


def test_campaign_summary_reports_valid_but_incomplete_sigterm_run(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-partial",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-partial",
            "n_experiments": 3,
            "screened_experiments": 3,
        },
    )
    recorder.write_status(
        loop_status={
            "requested_rounds": 4,
            "total_rounds": 4,
            "proposal_attempts": 4,
            "proposal_attempts_consumed": 4,
            "effective_rounds_completed": 3,
        },
    )
    steps = [
        replace(_step(f"/tmp/metrics-round-{idx}.json"), round_num=idx)
        for idx in (1, 2, 3)
    ]
    steps.append(
        _non_evaluated_step(
            ExecutionOutcome.INTERRUPTED,
            reason_code="OPERATOR_SIGNAL",
            detail="Evaluation interrupted by SIGTERM.",
            round_num=4,
        )
    )

    summary = recorder.write_campaign_summary(
        step_history=steps,
        round_num=4,
        champion=_champion(),
        stopped_reason="signal:SIGTERM",
    )

    validity = summary["run_validity"]
    assert summary["effective_rounds_completed"] == 3
    assert summary["requested_rounds"] == 4
    assert validity["status"] == "valid"
    assert validity["reason"] == RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED
    assert validity["valid"] is True
    assert validity["requested_rounds"] == 4
    assert validity["effective_rounds_completed"] == 3
    assert validity["completed_requested_rounds"] is False
    assert validity["complete"] is False
    assert validity["interrupted"] is True
    assert validity["partial_in_flight"] is True
    assert validity["partial_campaign_evidence"] is True
    assert validity["protocol_in_flight"] is False
    assert validity["completeness_status"] == "partial_interrupted"
    assert summary["run_validity_status"] == RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED










def test_quality_block_ledger_from_steps_preserves_agentic_session_ref() -> None:
    step = replace(
        _step("/tmp/quality-block.json"),
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="agent_quality_blocked",
        failure_detail=(
            "agentic_proposal:code_generation_failed: "
            "agent_quality_blocked:"
            "warehouse_validation_transfer_patch_quality_missing"
        ),
        attempt_kind="proposal_block",
        proposal_session_ref={
            "session_id": "patch-quality-session",
            "status": "failed",
            "termination_reason": "code_generation_failed",
            "agent_block_reason": "agent_quality_blocked",
            "failure_code": (
                "agent_quality_blocked:"
                "warehouse_validation_transfer_patch_quality_missing"
            ),
            "failure_category": "agent_grounding_failure",
            "primary_failure": {
                "stage": "agent_quality_blocked",
                "code": (
                    "agent_quality_blocked:"
                    "warehouse_validation_transfer_patch_quality_missing"
                ),
            },
            "rejection_constraint": {
                "gate_name": "warehouse_validation_transfer_patch_quality",
                "retry_constraint": (
                    "add activation/effect diagnostic counters before protocol"
                ),
            },
        },
    )

    ledger = quality_block_ledger(
        steps=[step],
        loop={},
        state_map={},
        quality_blocks=1,
    )

    assert len(ledger) == 1
    entry = ledger[0]
    assert entry["source"] == "step_history"
    assert entry["session_id"] == "patch-quality-session"
    assert entry["session_status"] == "failed"
    assert entry["termination_reason"] == "code_generation_failed"
    assert entry["agent_block_reason"] == "agent_quality_blocked"
    assert entry["failure_code"] == (
        "agent_quality_blocked:"
        "warehouse_validation_transfer_patch_quality_missing"
    )
    assert entry["quality_gate_name"] == (
        "warehouse_validation_transfer_patch_quality"
    )
    assert "activation/effect diagnostic counters" in entry["retry_constraint"]












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
        raw_metrics_ref=str(metrics_path),
        child_pid=12345,
        child_phase="solver_subprocess",
        case="/tmp/private/s1.vrp",
        seed=10,
    )
    recorder.current_status_progress = None
    failure_detail = "complete status failure " + "x" * 1200 + " complete-tail"
    status = recorder.write_status(
        last_result=StepResult(
            action="explore",
            branch_id="branch-old",
            reason="agent_quality_blocked",
            failure_stage="proposal",
            failure_detail=failure_detail,
        ),
        stopped_reason="signal:SIGTERM",
    )

    assert status["n_experiments"] == 0
    assert status["screened_experiments"] == 0
    assert status["last_result"]["reason"] == "agent_quality_blocked"
    assert status["last_result"]["failure_detail"] == failure_detail
    inflight = status["in_flight_protocol"]
    assert inflight["phase"] == "formal_screening"
    assert inflight["protocol_state"] == "running"
    assert inflight["branch_id"] == "branch-1"
    assert inflight["partial_metrics_ref"] == "metrics/partial-screening.json"
    assert inflight["attempted_pairs"] == 3
    assert inflight["total_pairs"] == 16
    assert inflight["valid_pairs"] == 3
    assert inflight["failed_pairs"] == 0
    assert inflight["complete"] is False
    assert inflight["child_pid"] == 12345
    assert inflight["child_phase"] == "solver_subprocess"
    assert inflight["last_case"].startswith("case:s1.vrp#")
    assert inflight["last_seed"] == 10
    assert inflight["decision_formed"] is False
    assert inflight["counts_toward_n_experiments"] is False
    assert status["last_completed_result"]["reason"] == "agent_quality_blocked"


def test_protocol_progress_completion_clears_child_pid(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {"campaign_id": "camp-1", "screened_experiments": 0},
    )

    recorder.record_protocol_progress(
        branch_id="branch-1",
        stage="screening",
        child_pid=12345,
        child_phase="solver_subprocess",
        case="/tmp/private/s1.vrp",
        seed=10,
    )
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    progress = status["current_progress"]
    assert progress["protocol_state"] == "running"
    assert progress["complete"] is False
    assert progress["last_case"].startswith("case:s1.vrp#")
    assert progress["last_seed"] == 10
    recorder.record_protocol_progress(
        branch_id="branch-1",
        stage="screening",
        child_exit_code=0,
        child_elapsed_ms=42,
        case="/tmp/private/s1.vrp",
        seed=10,
    )
    recorder.record_protocol_progress(
        branch_id="branch-1",
        stage="screening",
        attempted_pairs=1,
        valid_pairs=1,
    )

    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    progress = status["current_progress"]
    inflight = status["in_flight_protocol"]
    assert progress["protocol_state"] == "running"
    assert "child_pid" not in progress
    assert "child_pid" not in inflight
    assert progress["child_exit_code"] == 0
    assert progress["child_phase"] == "solver_subprocess_complete"
    assert inflight["child_exit_code"] == 0
    assert inflight["child_phase"] == "solver_subprocess_complete"

    recorder.record_protocol_progress(
        branch_id="branch-1",
        stage="screening",
        child_pid=67890,
        child_phase="solver_subprocess",
        case="/tmp/private/s2.vrp",
        seed=11,
    )
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    progress = status["current_progress"]
    assert progress["child_pid"] == 67890
    assert progress["child_phase"] == "solver_subprocess"
    assert "child_exit_code" not in progress
    assert "child_elapsed_ms" not in progress


def test_protocol_progress_stage_transition_does_not_retain_complete_or_child(
    tmp_path: Path,
) -> None:
    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()
    screening_metrics = metrics_dir / "screening.json"
    screening_metrics.write_text(
        json.dumps(
            {
                "stage": "screening",
                "complete": False,
                "total_pairs": 16,
                "attempted_pairs": 2,
                "valid_pairs": 0,
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
        state_provider=lambda: {"campaign_id": "camp-1", "screened_experiments": 0},
    )

    recorder.record_protocol_progress(
        branch_id="branch-1",
        stage="canary",
        complete=True,
        attempted_pairs=1,
        completed_pairs=1,
        total_pairs=1,
        child_pid=12345,
        child_phase="solver_subprocess",
    )
    recorder.record_protocol_progress(
        branch_id="branch-1",
        stage="screening",
        case="/tmp/private/screening.vrp",
        seed=29,
        raw_metrics_ref=str(screening_metrics),
    )

    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    progress = status["current_progress"]
    inflight = status["in_flight_protocol"]
    assert progress["stage"] == "screening"
    assert progress["complete"] is False
    assert progress["attempted_pairs"] == 2
    assert progress["total_pairs"] == 16
    assert progress["valid_pairs"] == 0
    assert "child_pid" not in progress
    assert "child_pid" not in inflight
    assert inflight["complete"] is False
    assert inflight["attempted_pairs"] == 2
