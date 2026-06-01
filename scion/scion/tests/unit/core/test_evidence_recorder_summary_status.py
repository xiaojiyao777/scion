"""Focused tests split from test_evidence_recorder.py."""

from dataclasses import replace

from .evidence_recorder_test_support import *  # noqa: F401,F403
from scion.core.run_validity import (
    RUN_VALIDITY_INVALID_INFRA_ONLY,
    RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED,
)
from scion.core.models import MechanismChange
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
    assert summary["counted_experiment_steps"] == 1
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
    assert summary_step["protocol_result"]["gate_observation_reason_codes"] == [
        "screening_positive",
        "runtime_ok",
    ]
    assert summary_step["protocol_result"]["lifecycle_action_reason_codes"] == []
    assert summary_step["protocol_result"]["effective_reason_source"] == (
        "decision_engine"
    )
    assert summary_step["protocol_result"]["runtime_ratio_median"] == 1.18
    assert summary_step["protocol_result"]["runtime_delta_median_ms"] == 24.0
    assert summary_step["protocol_result"]["runtime_regression_rate"] == 0.5
    assert summary_step["protocol_result"]["runtime_pairs"] == 4


def test_campaign_summary_exposes_screening_visibility_fields(
    tmp_path: Path,
) -> None:
    protocol = replace(
        _protocol_result("/tmp/metrics-visibility.json"),
        champion_cache_hits=2,
        champion_cache_misses=3,
        champion_cached_runtime_pairs=4,
        runtime_confidence="low_cached_champion",
        opportunity_status="opportunity_poor",
        opportunity_diagnostics=("primary mechanism did not trigger",),
        mechanism_evidence={
            "primary_mechanism": "candidate_list",
            "primary_activation_status": "missing",
            "primary_effect_status": "not_observed",
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
    assert protocol_summary["opportunity_status"] == "opportunity_poor"
    assert protocol_summary["opportunity_diagnostics"] == [
        "primary mechanism did not trigger"
    ]
    assert protocol_summary["mechanism_evidence"]["primary_mechanism"] == (
        "candidate_list"
    )
    assert protocol_summary["screening_feedback"]["runtime_confidence"] == (
        "low_cached_champion"
    )
    assert protocol_summary["screening_feedback"]["opportunity_status"] == (
        "opportunity_poor"
    )
    assert protocol_summary["screening_feedback_digest"]


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
    payload = json.loads(event["audit_payload_json"])
    assert payload["scheduler_slot"] == "refine_active"
    assert payload["scheduler_reason"] == "existing_branch_selected"
    assert payload["scheduler_audit_metadata"]["scheduler_action"] == "run_existing"
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
                "valid_pairs": 16,
                "failed_pairs": 0,
                "candidate_failed_pairs": 0,
                "champion_failed_pairs": 0,
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


def test_status_syncs_current_progress_checkpoint_fields_from_branch_card(
    tmp_path: Path,
) -> None:
    branch_card = {
        "branch_id": "branch-1",
        "lineage_id": "lineage-1",
        "lineage_status": "restored_checkpoint",
        "current_head_status": "active_marginal",
        "best_checkpoint_status": "best_quality_retained",
        "best_quality_checkpoint_id": "checkpoint-best",
        "last_valid_checkpoint_id": "checkpoint-last",
        "rollback_count": 1,
        "lineage_retained_checkpoint": True,
        "latest_head_failed": False,
        "allowed_next_actions": ["refine_checkpoint"],
        "forbidden_next_actions": [],
    }
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-1",
            "branches": [{"id": "branch-1", "branch_card": branch_card}],
            "branch_cards": [branch_card],
        },
    )
    recorder.current_status_progress = {
        "branch_id": "branch-1",
        "stage": "screening",
        "best_quality_checkpoint_id": "stale-checkpoint",
        "last_valid_checkpoint_id": "stale-last",
    }
    recorder.in_flight_protocol = {
        "phase": "formal_screening",
        "branch_id": "branch-1",
    }

    status = recorder.write_status()

    progress = status["current_progress"]
    assert progress["best_quality_checkpoint_id"] == "checkpoint-best"
    assert progress["last_valid_checkpoint_id"] == "checkpoint-last"
    assert progress["branch_card"]["best_quality_checkpoint_id"] == "checkpoint-best"
    assert status["in_flight_protocol"]["best_quality_checkpoint_id"] == (
        "checkpoint-best"
    )


def test_campaign_summary_reports_branch_history_cards_and_checkpoints(
    tmp_path: Path,
) -> None:
    hypothesis = _hypothesis("Evaluate a generic adjustment.")
    hypothesis.mechanism_changes = (
        MechanismChange(id="generic_adjustment", change_type="modify"),
    )
    protocol = replace(
        _protocol_result("/tmp/generic-metrics.json"),
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=3,
            ties=1,
            win_rate=0.0,
            median_delta=-0.08,
            ci_low=-0.2,
            ci_high=-0.01,
            runtime_ratio_median=1.11,
            runtime_regression_rate=0.5,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_REGRESSION",),
    )
    step = replace(
        _step("/tmp/generic-metrics.json"),
        branch_id="abandoned-branch",
        hypothesis=hypothesis,
        protocol_result=protocol,
        decision=Decision.ABANDON,
        decision_reason_codes=("BRANCH_LIFECYCLE_PARK_LINEAGE",),
    )
    active_card = {
        "branch_id": "active-branch",
        "lineage_status": "restored_checkpoint",
        "current_head_status": "active_weak_positive",
        "best_checkpoint_status": "best_quality_retained",
        "best_quality_checkpoint_id": "checkpoint-best",
        "last_valid_checkpoint_id": "checkpoint-last",
        "rollback_count": 2,
        "lineage_retained_checkpoint": True,
        "allowed_next_actions": ["refine_checkpoint"],
        "forbidden_next_actions": [],
        "generic_evidence_summary": {"tier": "weak_positive"},
    }
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "n_active_branches": 1,
            "branches": [{"id": "active-branch", "branch_card": active_card}],
            "checkpoint_inventory": {
                "lineage-active": {
                    "best_quality_checkpoint_id": "checkpoint-best",
                    "last_valid_checkpoint_id": "checkpoint-last",
                    "checkpoint_count": 2,
                }
            },
            "current_progress": {
                "branch_id": "active-branch",
                "best_quality_checkpoint_id": "checkpoint-best",
                "last_valid_checkpoint_id": "checkpoint-last",
            },
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=1,
        champion=_champion(),
    )

    history = {
        card["branch_id"]: card for card in summary["branch_history_cards"]
    }
    abandoned_card = history["abandoned-branch"]
    assert abandoned_card["status"] == "abandoned"
    assert abandoned_card["mechanism_ids"] == ["generic_adjustment"]
    assert abandoned_card["current_head_status"] == "regression"
    assert abandoned_card["latest_head_failed"] is True
    assert abandoned_card["generic_evidence_summary"]["wins"] == 0
    assert abandoned_card["generic_evidence_summary"]["losses"] == 3
    assert abandoned_card["generic_evidence_summary"]["runtime"][
        "runtime_ratio_median"
    ] == 1.11
    assert abandoned_card["why_abandoned_reason_codes"] == [
        "BRANCH_LIFECYCLE_PARK_LINEAGE",
        "SCREENING_REGRESSION",
    ]
    assert summary["checkpoint_inventory"]["lineage-active"][
        "best_quality_checkpoint_id"
    ] == "checkpoint-best"
    assert summary["current_progress"]["last_valid_checkpoint_id"] == (
        "checkpoint-last"
    )
    assert summary["rollback_events"][0]["rollback_count"] == 2


def test_campaign_summary_uses_llm_trace_cache_stats_when_present(
    tmp_path: Path,
) -> None:
    trace_dir = tmp_path / "llm_traces"
    trace_dir.mkdir()
    trace_a = {
        "request_kind": "code",
        "model": "claude-sonnet-4-6",
        "llm_usage": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "request_kind": "code",
            "input_tokens": 100,
            "output_tokens": 20,
            "cache_creation_input_tokens": 200,
            "cache_read_input_tokens": 0,
        },
        "prompt_cache_audit": {
            "cacheable_system_blocks_hash": "same-cache-key",
            "tool_schema_hash": "schema-a",
            "cacheable_system_chars": 1000,
        },
    }
    trace_b = {
        **trace_a,
        "llm_usage": {
            **trace_a["llm_usage"],
            "input_tokens": 120,
            "output_tokens": 25,
            "cache_creation_input_tokens": 200,
        },
    }
    (trace_dir / "0001_code.json").write_text(json.dumps(trace_a))
    (trace_dir / "0002_code.json").write_text(json.dumps(trace_b))

    recorder = EvidenceRecorder(
        campaign_id="camp-cache",
        campaign_dir=tmp_path,
    )
    summary = recorder.write_campaign_summary(
        step_history=[_step("/tmp/metrics-round-3.json")],
        round_num=1,
        champion=_champion(),
    )

    cache_stats = summary["cache_stats"]
    assert cache_stats["source"] == "llm_traces"
    assert cache_stats["calls"] == 2
    assert cache_stats["total_tokens"] == 620
    assert cache_stats["output_tokens"] == 45
    assert cache_stats["cache_create_tokens"] == 400
    assert cache_stats["cache_read_tokens"] == 0
    repeated = cache_stats["repeated_cache_create_groups"]
    assert repeated[0]["request_kind"] == "code"
    assert repeated[0]["cache_create_calls"] == 2
    assert repeated[0]["cache_read_calls"] == 0
    assert "multiple cache writes without a read" in repeated[0]["diagnosis"]


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


def test_status_reports_infra_only_run_validity(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-infra",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-infra",
            "n_experiments": 0,
            "screened_experiments": 0,
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
        },
    )

    assert status["run_validity"]["status"] == "invalid"
    assert status["run_validity"]["reason"] == RUN_VALIDITY_INVALID_INFRA_ONLY
    assert status["run_validity"]["infra_failure_attempts"] == 12
    assert status["run_validity_status"] == RUN_VALIDITY_INVALID_INFRA_ONLY


def test_campaign_summary_reports_infra_only_run_validity(tmp_path: Path) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-infra",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-infra",
            "n_experiments": 0,
            "screened_experiments": 0,
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
        counts_toward_max_rounds=False,
        attempt_kind="proposal_block",
    )

    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=12,
        champion=_champion(),
        stopped_reason="proposal_attempt_limit_exhausted",
    )

    assert summary["run_validity"]["status"] == "invalid"
    assert summary["run_validity"]["reason"] == RUN_VALIDITY_INVALID_INFRA_ONLY
    assert summary["failure_categories"] == {"infra": 12}
    assert summary["stopped_reason"] == "proposal_attempt_limit_exhausted"


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
    assert validity["completeness_status"] == "partial_interrupted"
    assert summary["run_validity_status"] == RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED


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
            scheduler_slot="repair_diagnostic",
            scheduler_reason="retry_branch_selected",
        )
    )

    assert status["proposal_attempts"] == 2
    assert status["screened_experiments"] == 0
    assert status["last_result"]["counts_toward_max_rounds"] is False
    assert status["last_result"]["scheduler_slot"] == "repair_diagnostic"
    assert status["last_result"]["scheduler_reason"] == "retry_branch_selected"


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
        state_provider=lambda: {"campaign_id": "camp-1", "requested_rounds": None},
    )
    loop_status = {
        "requested_rounds": 3,
        "attempt_limit": 3,
        "proposal_attempts": 2,
        "total_rounds": 2,
        "effective_rounds_completed": 0,
        "telemetry_diagnostic_attempts": 1,
        "branch_lifecycle_policy_blocks": 1,
        "reconcile_lifecycle_steps": 1,
        "non_counted_lifecycle_steps": 2,
        "proposal_quality_limit": 6,
        "proposal_quality_loop_limit": 6,
        "proposal_quality_blocks_consumed": 4,
        "quality_blocks": 4,
        "blocked_attempts": 4,
        "proposal_quality_blocks_remaining": 2,
    }

    status = recorder.write_status(loop_status=loop_status)
    summary = recorder.write_campaign_summary(
        step_history=[],
        round_num=0,
        champion=_champion(),
    )

    assert status["campaign_loop"]["requested_rounds"] == 3
    assert status["requested_rounds"] == 3
    assert status["total_rounds"] == 2
    assert status["proposal_attempts"] == 2
    assert status["effective_rounds_completed"] == 0
    assert status["telemetry_diagnostic_attempts"] == 1
    assert status["branch_lifecycle_policy_blocks"] == 1
    assert status["reconcile_lifecycle_steps"] == 1
    assert status["non_counted_lifecycle_steps"] == 2
    assert status["quality_blocks"] == 4
    assert status["blocked_attempts"] == 4
    assert status["campaign_loop"]["attempt_limit"] == 3
    assert status["campaign_loop"]["effective_rounds_completed"] == 0
    assert status["campaign_loop"]["proposal_quality_limit"] == 6
    assert status["campaign_loop"]["proposal_quality_blocks_consumed"] == 4
    assert summary["requested_rounds"] == 3
    assert summary["telemetry_diagnostic_attempts"] == 1
    assert summary["branch_lifecycle_policy_blocks"] == 1
    assert summary["reconcile_lifecycle_steps"] == 1
    assert summary["non_counted_lifecycle_steps"] == 2
    assert summary["counted_experiment_steps"] == 0
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
        child_pid=12345,
        child_phase="solver_subprocess",
        case="/tmp/private/s1.vrp",
        seed=10,
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

    assert summary["screened_experiments"] == 1
    assert summary["effective_rounds_completed"] == 0
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
    assert protocol["gate_observation_reason_codes"] == ["SCREENING_FAIL_WIN_RATE"]
    assert protocol["lifecycle_action_reason_codes"] == []
    assert protocol["effective_reason_source"] == "decision_engine"
