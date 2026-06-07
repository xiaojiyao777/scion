"""Focused tests split from test_evidence_recorder.py."""

from dataclasses import replace

from .evidence_recorder_test_support import *  # noqa: F401,F403
from scion.core.run_validity import (
    RUN_VALIDITY_INVALID_INFRA_ONLY,
    RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED,
)
from scion.core.models import CaseAggregateFeedback, MechanismChange
from scion.core.evidence_recording.summary_cache import _campaign_cache_stats
from scion.core.step_result import StepResult


def _research_process_guidance_audit() -> dict:
    return {
        "schema_version": "branch_followup_policy.v1",
        "taint": "proposal_guidance",
        "decision_input_policy": "excluded_from_decision_features",
        "source": "research_process_guidance",
        "guidance_ref": "branch_followup_policy.research_process_guidance",
        "guidance_schema_key": "research_process_guidance",
        "principle": "weak_positive_followups_are_allowed_as_bounded_research_probes",
        "not_a_hard_stop": True,
    }


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
    base_protocol = _protocol_result("/tmp/metrics-visibility.json")
    protocol = replace(
        base_protocol,
        stats=replace(base_protocol.stats, runtime_pairs=0),
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
    assert protocol_summary["opportunity_status"] == "opportunity_poor"
    assert protocol_summary["opportunity_diagnostics"] == [
        "primary mechanism did not trigger"
    ]
    assert protocol_summary["mechanism_evidence"]["primary_mechanism"] == (
        "candidate_list"
    )
    assert protocol_summary["mechanism_evidence"]["activation_evidence_status"] == (
        "missing_activation"
    )
    assert protocol_summary["runtime_aggregate_exclusion"]["reason"] == (
        "low_cached_champion"
    )
    assert protocol_summary["runtime_aggregate_exclusion"][
        "candidate_runtime_pair_evidence_count"
    ] == 2
    assert protocol_summary["screening_feedback"]["runtime_confidence"] == (
        "low_cached_champion"
    )
    assert protocol_summary["screening_feedback"]["opportunity_status"] == (
        "opportunity_poor"
    )
    assert protocol_summary["screening_feedback_digest"]


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
        "active_slot_status": "active_slot",
        "counts_toward_active_slots": True,
    }
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-1",
            "n_active_branches": 0,
            "active_slots": {
                "used": 0,
                "max": 3,
                "available": 3,
                "branch_ids": [],
                "parked_lineages": 0,
                "parked_lineage_ids": [],
            },
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
    assert status["n_active_branches"] == 1
    assert status["active_slots"]["used"] == 1
    assert status["active_slots"]["branch_ids"] == ["branch-1"]


def test_status_and_summary_cap_active_slots_from_branch_cards(
    tmp_path: Path,
) -> None:
    def active_row(branch_id: str) -> dict:
        return {
            "id": branch_id,
            "branch_card": {
                "branch_id": branch_id,
                "status": "explore",
                "active_slot_status": "active_slot",
                "counts_toward_active_slots": True,
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
        assert payload["n_active_branches"] == 2
        assert payload["active_slots"]["used"] == 2
        assert payload["active_slots"]["max"] == 2
        assert payload["active_slots"]["branch_ids"] == ["branch-a", "branch-b"]
        assert payload["active_slots"]["overflow_branch_ids"] == ["branch-c"]


def test_campaign_summary_branch_cards_keep_runtime_evidence_pressure_count(
    tmp_path: Path,
) -> None:
    branch_card = {
        "branch_id": "runtime-pressure-card",
        "status": "explore",
        "active_slot_status": "active_slot",
        "counts_toward_active_slots": True,
        "runtime_evidence_pressure_count": 2,
        "generic_evidence_summary": {
            "tier": "marginal",
            "runtime_evidence_pressure_count": 2,
        },
    }
    recorder = EvidenceRecorder(
        campaign_id="camp-runtime-pressure",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "n_experiments": 0,
            "proposal_attempts": 0,
            "screened_experiments": 0,
            "n_active_branches": 1,
            "branches": [{"id": "branch-1", "branch_card": branch_card}],
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[],
        round_num=0,
        champion=_champion(),
        stopped_reason="max_rounds",
    )

    [summary_card] = summary["branch_cards"]
    assert summary_card["runtime_evidence_pressure_count"] == 2
    assert summary_card["generic_evidence_summary"][
        "runtime_evidence_pressure_count"
    ] == 2


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
        runtime_confidence="low_cached_champion",
        opportunity_status="opportunity_poor",
        mechanism_evidence={
            "primary_activation_status": "observed",
            "primary_effect_status": "regressed",
        },
        case_feedback=(
            CaseAggregateFeedback(
                case_id="case-loss",
                n_pairs=3,
                wins=0,
                losses=3,
                ties=0,
                win_rate=0.0,
                dominant_result="loss",
                decisive_metric="objective_delta",
                median_deltas={"objective_delta": -0.31},
            ),
        ),
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
        "active_slot_status": "active_slot",
        "counts_toward_active_slots": True,
    }
    parked_card = {
        "branch_id": "parked-branch",
        "status": "parked_lineage",
        "active_slot_status": "parked_lineage",
        "counts_toward_active_slots": False,
    }
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "n_active_branches": 0,
            "active_slots": {
                "used": 0,
                "max": 3,
                "available": 3,
                "branch_ids": [],
                "parked_lineages": 0,
                "parked_lineage_ids": [],
            },
            "branches": [
                {"id": "active-branch", "branch_card": active_card},
                {"id": "parked-branch", "branch_card": parked_card},
            ],
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
    assert abandoned_card["runtime_evidence_confidence"] == "low_cached_champion"
    assert abandoned_card["phase_activation_summary"] == {
        "stage": "screening",
        "activation_status": "observed",
        "effect_status": "regressed",
        "activation_evidence_status": "activation_observed",
        "objective_effect_status": "regressed",
        "opportunity_status": "opportunity_poor",
        "telemetry_outcome": "fail",
    }
    assert abandoned_card["case_level_winners"] == []
    assert abandoned_card["case_level_losses"] == [
        {
            "case_id": "case-loss",
            "result": "loss",
            "delta": -0.31,
            "effect_counters": {"wins": 0, "losses": 3, "ties": 0, "pairs": 3},
        }
    ]
    assert abandoned_card["why_abandoned_reason_codes"] == [
        "BRANCH_LIFECYCLE_PARK_LINEAGE",
        "SCREENING_REGRESSION",
    ]
    assert abandoned_card["gate_observation_reason_codes"] == [
        "SCREENING_REGRESSION"
    ]
    assert abandoned_card["lifecycle_action_reason_codes"] == [
        "BRANCH_LIFECYCLE_PARK_LINEAGE"
    ]
    assert summary["checkpoint_inventory"]["lineage-active"][
        "best_quality_checkpoint_id"
    ] == "checkpoint-best"
    assert summary["active_slots"]["used"] == 1
    assert summary["active_slots"]["branch_ids"] == ["active-branch"]
    assert summary["active_slots"]["parked_lineage_ids"] == ["parked-branch"]
    assert summary["current_progress"]["last_valid_checkpoint_id"] == (
        "checkpoint-last"
    )
    assert summary["rollback_events"][0]["rollback_count"] == 2


def test_branch_history_card_text_rerenders_structured_reason_codes(
    tmp_path: Path,
) -> None:
    active_protocol = replace(
        _protocol_result("/tmp/active-metrics.json"),
        gate_outcome="fail",
        reason_codes=("SCREENING_NEUTRAL_SIGNAL_CONTINUE",),
    )
    parked_protocol = replace(
        _protocol_result("/tmp/parked-metrics.json"),
        gate_outcome="fail",
        reason_codes=(
            "SCREENING_FAIL_WIN_RATE",
            "SCREENING_SOFT_ABANDON_NON_POSITIVE_CI",
        ),
    )
    abandoned_protocol = replace(
        _protocol_result("/tmp/abandoned-metrics.json"),
        gate_outcome="fail",
        reason_codes=("SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN",),
    )
    active_step = replace(
        _step("/tmp/active-metrics.json"),
        branch_id="active-branch",
        protocol_result=active_protocol,
        decision=Decision.CONTINUE_EXPLORE,
        decision_reason_codes=(
            "SCREENING_FAIL_WIN_RATE",
            "TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
        ),
    )
    parked_step = replace(
        _step("/tmp/parked-metrics.json"),
        branch_id="parked-branch",
        protocol_result=parked_protocol,
        decision=Decision.CONTINUE_EXPLORE,
        decision_reason_codes=("BRANCH_LIFECYCLE_PARK_LINEAGE",),
    )
    abandoned_step = replace(
        _step("/tmp/abandoned-metrics.json"),
        branch_id="abandoned-branch",
        protocol_result=abandoned_protocol,
        decision=Decision.ABANDON,
        decision_reason_codes=("SCREENING_FAIL_WIN_RATE",),
    )
    stale_text = "branch_id={branch_id} why_not_promoted_reason_codes=none"
    branch_cards = [
        {
            "branch_id": "active-branch",
            "status": "explore",
            "branch_card_text": stale_text.format(branch_id="active-branch"),
        },
        {
            "branch_id": "parked-branch",
            "status": "parked_lineage",
            "branch_code_status": "parked_lineage",
            "current_head_status": "parked_lineage",
            "branch_card_text": stale_text.format(branch_id="parked-branch"),
        },
        {
            "branch_id": "abandoned-branch",
            "status": "abandoned",
            "branch_card_text": stale_text.format(branch_id="abandoned-branch"),
        },
    ]
    recorder = EvidenceRecorder(
        campaign_id="camp-branch-card-text",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "branches": [
                {"id": card["branch_id"], "branch_card": card}
                for card in branch_cards
            ],
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[active_step, parked_step, abandoned_step],
        round_num=3,
        champion=_champion(),
    )

    history = {
        card["branch_id"]: card for card in summary["branch_history_cards"]
    }
    active_text = history["active-branch"]["branch_card_text"]
    parked_text = history["parked-branch"]["branch_card_text"]
    abandoned_text = history["abandoned-branch"]["branch_card_text"]

    assert history["active-branch"]["why_not_promoted_reason_codes"] == [
        "SCREENING_FAIL_WIN_RATE",
        "TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
        "SCREENING_NEUTRAL_SIGNAL_CONTINUE",
    ]
    assert history["parked-branch"]["status"] == "parked_lineage"
    assert history["parked-branch"]["current_head_status"] == "parked_lineage"
    assert history["parked-branch"]["gate_observation_reason_codes"] == [
        "SCREENING_FAIL_WIN_RATE"
    ]
    assert history["parked-branch"]["lifecycle_action_reason_codes"] == [
        "BRANCH_LIFECYCLE_PARK_LINEAGE",
        "SCREENING_SOFT_ABANDON_NON_POSITIVE_CI",
    ]
    assert "why_not_promoted_reason_codes=SCREENING_FAIL_WIN_RATE" in active_text
    assert "TELEMETRY_EFFECT_ZERO_DIAGNOSTIC" in active_text
    assert "SCREENING_NEUTRAL_SIGNAL_CONTINUE" in active_text
    assert "why_not_promoted_reason_codes=BRANCH_LIFECYCLE_PARK_LINEAGE" in parked_text
    assert "SCREENING_SOFT_ABANDON_NON_POSITIVE_CI" in parked_text
    assert "why_abandoned_reason_codes=SCREENING_FAIL_WIN_RATE" in abandoned_text
    assert "SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN" in abandoned_text


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


def test_summary_cache_helper_preserves_step_record_fallback_schema(
    tmp_path: Path,
) -> None:
    cache_stats = _campaign_cache_stats(
        [_step("/tmp/metrics-round-3.json")],
        campaign_dir=tmp_path,
    )

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


def test_campaign_summary_uses_provider_aware_openai_cache_accounting(
    tmp_path: Path,
) -> None:
    trace_dir = tmp_path / "llm_traces"
    trace_dir.mkdir()

    def _write_trace(
        name: str,
        *,
        request_kind: str,
        prompt_total: int,
        output_tokens: int,
        cache_read: int,
        cache_miss: int,
        cache_hash: str,
    ) -> None:
        (trace_dir / name).write_text(
            json.dumps(
                {
                    "request_kind": request_kind,
                    "model": "gpt-5.5",
                    "llm_usage": {
                        "provider": "openai_compatible",
                        "model": "gpt-5.5",
                        "request_kind": request_kind,
                        "cache_accounting_mode": (
                            "provider_prompt_tokens_include_cache_read"
                        ),
                        "input_tokens": prompt_total,
                        "prompt_tokens_total": prompt_total,
                        "output_tokens": output_tokens,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": cache_read,
                        "cache_miss_input_tokens": cache_miss,
                    },
                    "prompt_cache_audit": {
                        "provider": "openai_compatible",
                        "cacheable_system_blocks_hash": cache_hash,
                        "tool_schema_hash": "schema-a",
                        "cacheable_system_chars": 1000,
                    },
                }
            ),
            encoding="utf-8",
        )

    _write_trace(
        "0001_code.json",
        request_kind="code",
        prompt_total=100,
        output_tokens=10,
        cache_read=40,
        cache_miss=60,
        cache_hash="code-cache-key",
    )
    _write_trace(
        "0002_code.json",
        request_kind="code",
        prompt_total=90,
        output_tokens=9,
        cache_read=0,
        cache_miss=90,
        cache_hash="code-cache-key",
    )
    _write_trace(
        "0003_hypothesis.json",
        request_kind="hypothesis",
        prompt_total=50,
        output_tokens=5,
        cache_read=0,
        cache_miss=50,
        cache_hash="hypothesis-cache-key",
    )
    _write_trace(
        "0004_hypothesis.json",
        request_kind="hypothesis",
        prompt_total=70,
        output_tokens=7,
        cache_read=0,
        cache_miss=70,
        cache_hash="hypothesis-cache-key",
    )
    (trace_dir / "0005_code_pending.json").write_text(
        json.dumps(
            {
                "request_kind": "code",
                "model": "gpt-5.5",
                "prompt_cache_audit": {"provider": "openai_compatible"},
            }
        ),
        encoding="utf-8",
    )

    recorder = EvidenceRecorder(
        campaign_id="camp-cache-openai",
        campaign_dir=tmp_path,
    )
    summary = recorder.write_campaign_summary(
        step_history=[_step("/tmp/metrics-round-3.json")],
        round_num=1,
        champion=_champion(),
    )

    cache_stats = summary["cache_stats"]
    assert cache_stats["source"] == "llm_traces"
    assert cache_stats["calls"] == 4
    assert cache_stats["total_tokens"] == 310
    assert cache_stats["prompt_tokens_total"] == 310
    assert cache_stats["cache_read_tokens"] == 40
    assert cache_stats["cache_miss_tokens"] == 270
    assert cache_stats["cache_create_tokens"] == 0
    assert cache_stats["cache_hit_rate"] == 0.129
    assert cache_stats["cache_accounting_modes"] == {
        "provider_prompt_tokens_include_cache_read": 4
    }

    by_kind = {
        (row["request_kind"], row["provider"]): row
        for row in cache_stats["by_request_kind_provider"]
    }
    code = by_kind[("code", "openai_compatible")]
    assert code["calls"] == 2
    assert code["prompt_tokens_total"] == 190
    assert code["cache_read_tokens"] == 40
    assert code["cache_miss_tokens"] == 150
    assert code["hit_rate"] == 0.2105
    assert code["pending_no_usage_traces"] == 1
    hypothesis = by_kind[("hypothesis", "openai_compatible")]
    assert hypothesis["calls"] == 2
    assert hypothesis["hit_rate"] == 0.0

    no_read = cache_stats["repeated_cache_key_no_read"]
    assert len(no_read) == 1
    assert no_read[0]["request_kind"] == "hypothesis"
    assert no_read[0]["calls"] == 2
    assert no_read[0]["cache_read_calls"] == 0
    assert no_read[0]["cacheable_system_blocks_hash"] == "hypothesis-cache-key"


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
            "material_difference_requirement": {
                "record_type": "material_difference_requirement",
                "schema_version": "material_difference_requirement.v1",
                "record_id": "mdr:session-3",
                "record_digest": "digest:session-3",
                "reason_codes": ["MATERIAL_DIFFERENCE_REQUIRED"],
                "proposal_visibility_only": True,
                "decision_features_excluded": True,
                "summary": "raw proposal-facing detail must not be copied",
            },
            "cross_branch_research_payload": {
                "cross_branch_research_audit_records": [
                    {
                        "record_type": "cross_branch_research_audit",
                        "schema_version": "cross_branch_research_audit.v1",
                        "record_id": "cbr:session-3",
                        "record_digest": "digest:cbr-session-3",
                        "proposal_visibility_only": True,
                        "decision_features_excluded": True,
                        "hypothesis_text": "raw proposal text must not be copied",
                    }
                ],
                "hypothesis_text": "raw proposal text must not be copied",
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
    assert summary_step["proposal_session_ref"]["material_difference_requirement"][
        "record_id"
    ] == "mdr:session-3"
    assert "summary" not in summary_step["proposal_session_ref"][
        "material_difference_requirement"
    ]
    session_payload = summary_step["proposal_session_ref"][
        "cross_branch_research_payload"
    ]
    assert session_payload["cross_branch_research_audit_records"][0][
        "record_id"
    ] == "cbr:session-3"
    assert "hypothesis_text" not in json.dumps(session_payload)
    step_audit = summary_step["step_visibility_audit"]
    assert step_audit["cross_branch_research_visibility"]["status"] == "available"
    assert step_audit["material_difference_requirement_visibility"]["status"] == (
        "available"
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
        },
    )

    validity = status["run_validity"]
    assert validity["status"] == "valid"
    assert validity["reason"] == RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED
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
    assert status["run_validity"]["partial_in_flight"] is False
    assert status["run_validity"]["completeness_status"] == "interrupted_incomplete"


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
    assert summary["run_validity"]["partial_in_flight"] is False
    assert summary["run_validity"]["completeness_status"] == "interrupted_incomplete"
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
        },
    )
    loop_status = {
        "requested_rounds": 12,
        "total_rounds": 1,
        "proposal_attempts": 1,
        "proposal_attempts_consumed": 1,
        "effective_rounds_completed": 0,
        "failure_categories": {"infra": 1},
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
        counts_toward_max_rounds=False,
        attempt_kind="proposal_block",
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
    assert status["run_validity"]["completeness_status"] == "interrupted_incomplete"
    assert summary["run_validity"]["partial_in_flight"] is False
    assert summary["run_completeness_status"] == "interrupted_incomplete"


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

    summary = recorder.write_campaign_summary(
        step_history=steps,
        round_num=7,
        champion=_champion(),
        stopped_reason="api_balance_exhausted",
    )

    validity = summary["run_validity"]
    assert summary["requested_rounds"] == 12
    assert summary["effective_rounds_completed"] == 6
    assert validity["reason"] == RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED
    assert validity["completed_requested_rounds"] is False
    assert validity["complete"] is False
    assert validity["partial_in_flight"] is True
    assert validity["completeness_status"] == "partial_interrupted"
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
        },
    )
    loop_status = {
        "requested_rounds": 12,
        "total_rounds": 7,
        "proposal_attempts": 7,
        "proposal_attempts_consumed": 7,
        "effective_rounds_completed": 6,
        "failure_categories": {"infra": 1},
    }

    status = recorder.write_status(
        stopped_reason="api_balance_exhausted",
        loop_status=loop_status,
    )
    steps = [
        replace(_step(f"/tmp/metrics-round-{idx}.json"), round_num=idx)
        for idx in range(1, 7)
    ]
    summary = recorder.write_campaign_summary(
        step_history=steps,
        round_num=7,
        champion=_champion(),
        stopped_reason="api_balance_exhausted",
    )

    assert _run_validity_completion_projection(status) == (
        _run_validity_completion_projection(summary)
    )
    assert status["run_validity"]["reason"] == RUN_VALIDITY_VALID_PARTIAL_INTERRUPTED
    assert status["run_validity"]["partial_in_flight"] is True
    assert status["run_validity"]["completeness_status"] == "partial_interrupted"
    assert summary["run_validity"]["partial_in_flight"] is True
    assert summary["run_completeness_status"] == "partial_interrupted"


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
            scheduler_audit_metadata={
                "pre_finalizer_scheduler_slot": "repair_diagnostic",
                "post_finalizer_actual_branch_action": "soft_abandon",
            },
        )
    )

    assert status["proposal_attempts"] == 2
    assert status["screened_experiments"] == 0
    assert status["last_result"]["counts_toward_max_rounds"] is False
    assert status["last_result"]["scheduler_slot"] == "repair_diagnostic"
    assert status["last_result"]["scheduler_reason"] == "retry_branch_selected"
    assert status["last_result"]["scheduler_audit_metadata"] == {
        "pre_finalizer_scheduler_slot": "repair_diagnostic",
        "post_finalizer_actual_branch_action": "soft_abandon",
    }


def test_research_process_guidance_audit_is_queryable_in_summary_and_status(
    tmp_path: Path,
) -> None:
    audit = _research_process_guidance_audit()
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    step = replace(
        _step("/tmp/metrics-guidance-audit.json"),
        proposal_session_ref={
            "schema_version": "proposal-context-ref.v1",
            "session_id": "session-1",
            "research_process_guidance_audit": audit,
        },
    )
    step_history = [step]

    summary = recorder.write_campaign_summary(
        step_history=step_history,
        round_num=3,
        champion=_champion(),
        stopped_reason="max_rounds",
    )
    summary_step = summary["steps"][0]

    assert summary_step["research_process_guidance_audit"] == audit
    assert summary_step["proposal_session_ref"]["research_process_guidance_audit"] == (
        audit
    )
    assert summary_step["research_process_guidance_audit"]["taint"] == (
        "proposal_guidance"
    )
    assert summary_step["research_process_guidance_audit"][
        "decision_input_policy"
    ] == "excluded_from_decision_features"
    rendered = json.dumps(summary_step["research_process_guidance_audit"])
    assert "Improve route insertion" not in rendered
    assert "hypothesis_text" not in rendered

    result = StepResult(
        action="explore",
        branch_id="branch-1",
        decision=Decision.CONTINUE_EXPLORE,
        reason="decision=continue_explore; scheduler_slot=refine_active",
        scheduler_slot="refine_active",
        scheduler_reason="existing_branch_selected",
        scheduler_audit_metadata={
            "scheduler_action": "run_existing",
        },
    )
    recorder.record_scheduler_result(result, step_history)
    status = recorder.write_status(last_result=result)

    assert status["last_result"]["scheduler_audit_metadata"][
        "scheduler_action"
    ] == "run_existing"
    assert status["last_result"]["scheduler_audit_metadata"][
        "research_process_guidance_audit"
    ] == audit
    assert status["last_result"]["research_process_guidance_audit"] == audit
    assert status["last_result"]["research_process_guidance_audit"]["taint"] == (
        "proposal_guidance"
    )
    assert status["last_result"]["research_process_guidance_audit"][
        "decision_input_policy"
    ] == "excluded_from_decision_features"


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
        "loop_steps": 5,
        "campaign_steps": 5,
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
        "quality_block_ledger": [
            {
                "sequence": 1,
                "index": 0,
                "branch_id": "branch-1",
                "hypothesis_id": "hyp-1",
                "attempt_kind": "proposal_block",
                "failure_stage": "agent_quality_blocked",
                "failure_category": "agent_quality_blocked",
                "failure_reason": "proposal_premise_contradicted",
                "source_result_reason": "agent_quality_blocked",
                "counts_toward_max_rounds": False,
                "pre_protocol": True,
            }
        ],
        "quality_block_ledger_count": 1,
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
    assert status["campaign_steps"] == 5
    assert status["proposal_attempts"] == 2
    assert status["effective_rounds_completed"] == 0
    assert status["telemetry_diagnostic_attempts"] == 1
    assert status["branch_lifecycle_policy_blocks"] == 1
    assert status["reconcile_lifecycle_steps"] == 1
    assert status["non_counted_lifecycle_steps"] == 2
    assert status["quality_blocks"] == 4
    assert status["quality_block_ledger_count"] == 4
    assert status["quality_block_ledger"][0]["branch_id"] == "branch-1"
    assert status["quality_block_ledger"][-1]["schema_version"] == (
        "quality_block_attempt.v1"
    )
    assert status["quality_block_ledger"][-1]["source"] == (
        "aggregate_reconciliation"
    )
    assert status["proposal_accounting"]["quality_block_ledger_count"] == 4
    assert status["blocked_attempts"] == 4
    assert status["campaign_loop"]["attempt_limit"] == 3
    assert status["campaign_loop"]["effective_rounds_completed"] == 0
    assert status["campaign_loop"]["proposal_quality_limit"] == 6
    assert status["campaign_loop"]["proposal_quality_blocks_consumed"] == 4
    assert summary["requested_rounds"] == 3
    assert summary["campaign_steps"] == 5
    assert summary["screened_rounds"] == 0
    assert summary["telemetry_diagnostic_attempts"] == 1
    assert summary["branch_lifecycle_policy_blocks"] == 1
    assert summary["reconcile_lifecycle_steps"] == 1
    assert summary["non_counted_lifecycle_steps"] == 2
    assert summary["counted_experiment_steps"] == 0
    assert summary["quality_block_ledger_count"] == 4
    assert summary["quality_block_ledger"][0]["hypothesis_id"] == "hyp-1"
    assert summary["quality_block_ledger"][-1]["schema_version"] == (
        "quality_block_attempt.v1"
    )
    assert summary["quality_block_ledger"][-1]["source"] == (
        "aggregate_reconciliation"
    )
    assert summary["proposal_accounting"]["quality_block_ledger_count"] == 4
    assert summary["campaign_loop"]["proposal_quality_blocks_remaining"] == 2


def test_branch_lifecycle_routing_diagnostic_does_not_enter_run_validity(
    tmp_path: Path,
) -> None:
    detail = (
        "branch_lifecycle_policy_violation: "
        "new_mechanism_requires_clean_fork; "
        "protected_mechanism_ids=bounded_probe; "
        "proposed_mechanism_ids=different_probe"
    )
    lifecycle_step = replace(
        _step("/tmp/metrics-lifecycle.json"),
        round_num=2,
        patch=None,
        contract_passed=False,
        verification_passed=False,
        protocol_result=None,
        decision=None,
        failure_stage="proposal",
        failure_detail=detail,
        counts_toward_max_rounds=False,
        attempt_kind="branch_lifecycle_policy",
        repair_policy_reason=detail,
        repair_mechanism_ids=("bounded_probe",),
        proposal_session_ref={
            "session_id": "branch-routing-session",
            "primary_failure": {
                "stage": "self_check",
                "reason": "schema_or_target_preview_failed",
                "category": "contract_boundary_failure",
                "code": "same_mechanism_only_violation",
                "detail": detail,
            },
            "failure_category": "contract_boundary_failure",
            "failure_code": "same_mechanism_only_violation",
        },
    )
    counted_step = replace(_step("/tmp/metrics-counted.json"), round_num=3)
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-1",
            "n_experiments": 1,
            "screened_experiments": 1,
        },
    )

    status = recorder.write_status(
        stopped_reason="max_rounds_exhausted",
        loop_status={
            "requested_rounds": 1,
            "total_rounds": 2,
            "proposal_attempts": 1,
            "proposal_attempts_consumed": 1,
            "effective_rounds_completed": 1,
            "branch_lifecycle_policy_blocks": 1,
            "non_counted_lifecycle_steps": 1,
            "failure_categories": {},
            "infra_failure_attempts": 0,
            "noninfra_failure_attempts": 0,
        },
    )
    summary = recorder.write_campaign_summary(
        step_history=[lifecycle_step, counted_step],
        round_num=3,
        champion=_champion(),
        stopped_reason="max_rounds_exhausted",
    )

    assert status["run_validity"]["failure_categories"] == {}
    assert status["run_validity"]["noninfra_failure_attempts"] == 0
    assert summary["failure_categories"] == {}
    assert summary["run_validity"]["failure_categories"] == {}
    assert summary["run_validity"]["noninfra_failure_attempts"] == 0
    assert summary["branch_lifecycle_policy_blocks"] == 1
    assert summary["counted_experiment_steps"] == 1


def test_status_and_summary_expose_proposal_accounting_fields(
    tmp_path: Path,
) -> None:
    trace_dir = tmp_path / "llm_traces"
    trace_dir.mkdir()
    for index, request_kind in enumerate(("hypothesis", "code", "code"), start=1):
        (trace_dir / f"{index:04d}_{request_kind}.json").write_text(
            json.dumps(
                {
                    "request_kind": request_kind,
                    "llm_usage": {
                        "request_kind": request_kind,
                        "input_tokens": 10,
                        "output_tokens": 2,
                    },
                }
            ),
            encoding="utf-8",
        )
    agentic_dir = tmp_path / "agentic_sessions"
    agentic_dir.mkdir()
    (agentic_dir / "agentic_session_index.json").write_text(
        json.dumps(
            [
                {"session_id": "session-1", "branch_id": "branch-1"},
                {"session_id": "session-2", "branch_id": "branch-2"},
            ]
        ),
        encoding="utf-8",
    )
    (agentic_dir / "agentic_session_trace_index.json").write_text(
        json.dumps(
            {
                "schema_version": "agentic-session-trace-index.v1",
                "artifact_kind": "agentic_session_trace_index",
                "session_count": 2,
                "trace_count": 3,
                "sessions": [
                    {
                        "session_id": "session-1",
                        "hypothesis_trace_ids": ["trace-hyp"],
                        "code_trace_ids": ["trace-code"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-1",
            "screened_experiments": 2,
            "n_steps": 7,
            "n_active_branches": 1,
            "branches": [],
        },
    )
    loop_status = {
        "requested_rounds": 4,
        "loop_steps": 7,
        "proposal_attempts": 5,
        "proposal_attempts_consumed": 5,
        "proposal_attempts_total": 7,
        "formal_screened_candidates": 2,
        "protocol_evaluated_candidates": 2,
        "protocol_stage_counts": {
            "screening": 2,
            "validation": 0,
            "frozen": 0,
        },
        "quality_blocks": 3,
    }

    status = recorder.write_status(loop_status=loop_status)
    step = replace(
        _step("/tmp/accounting-metrics.json"),
        proposal_session_ref={"session_id": "session-1"},
    )
    summary = recorder.write_campaign_summary(
        step_history=[step],
        round_num=5,
        champion=_champion(),
    )

    for payload in (status, summary):
        assert payload["campaign_steps"] == 7
        assert payload["screened_rounds"] == 2
        assert payload["proposal_attempts_total"] == 7
        assert payload["formal_screened_candidates"] == 2
        assert payload["protocol_evaluated_candidates"] == 2
        assert payload["protocol_stage_counts"] == {
            "screening": 2,
            "validation": 0,
            "frozen": 0,
        }
        assert payload["quality_blocks"] == 3
        assert payload["agentic_sessions"] == 2
        assert payload["hypothesis_calls"] == 1
        assert payload["code_calls"] == 2
        assert payload["proposal_accounting"]["campaign_steps"] == 7
        assert payload["proposal_accounting"]["screened_rounds"] == 2
        assert payload["proposal_accounting"]["proposal_attempts_total"] == 7
        assert payload["proposal_accounting"]["formal_screened_candidates"] == 2
        assert payload["proposal_accounting"]["protocol_evaluated_candidates"] == 2
        assert payload["proposal_accounting"]["quality_blocks"] == 3
        assert payload["proposal_accounting"]["agentic_sessions"] == 2
        assert payload["proposal_accounting"]["hypothesis_calls"] == 1
        assert payload["proposal_accounting"]["code_calls"] == 2
        trace_index = payload["proposal_accounting"]["agentic_session_trace_index"]
        assert payload["agentic_session_trace_index"] == trace_index
        assert trace_index["artifact_ref"] == (
            "agentic_sessions/agentic_session_trace_index.json"
        )
        assert trace_index["digest"]
        assert trace_index["session_count"] == 2
        assert trace_index["trace_count"] == 3


def test_campaign_summary_reconciles_screened_and_effective_rounds(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(
        campaign_id="camp-1",
        campaign_dir=tmp_path,
        state_provider=lambda: {
            "campaign_id": "camp-1",
            "screened_experiments": 2,
            "n_steps": 3,
            "n_active_branches": 1,
            "branches": [],
            "telemetry_failed_experiments": 1,
        },
    )
    accepted_step = _step("/tmp/accounting-accepted.json")
    repair_step = replace(
        _step("/tmp/accounting-repair.json"),
        round_num=4,
        decision=Decision.CONTINUE_EXPLORE,
        decision_reason_codes=("TELEMETRY_VALIDATION_REPAIRABLE",),
        counts_toward_max_rounds=False,
        attempt_kind="telemetry_repairable",
    )
    repair_step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=replace(accepted_step.protocol_result.stats, wins=0, losses=0, ties=6),
        gate_outcome="fail",
        reason_codes=(
            "TELEMETRY_VALIDATION_REPAIRABLE",
            "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
        ),
        exposed_summary="screening telemetry repairable",
        raw_metrics_ref="/tmp/accounting-repair.json",
        candidate_surface_runtime_summary={
            "telemetry_guard": {
                "passed": False,
                "failures": [
                    {
                        "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                        "severity": "fail",
                        "category": "activation",
                        "mechanism": "generic_probe",
                    }
                ],
            }
        },
    )
    recorder.campaign_loop_status = {
        "requested_rounds": 2,
        "total_rounds": 3,
        "campaign_steps": 3,
        "proposal_attempts": 2,
        "proposal_attempts_consumed": 2,
        "effective_rounds_completed": 1,
        "telemetry_repairable_attempts": 1,
        "telemetry_repair_attempts": 1,
        "failure_categories": {"model_repair_failed": 1},
        "quality_blocks": 1,
    }

    summary = recorder.write_campaign_summary(
        step_history=[accepted_step, repair_step],
        round_num=3,
        champion=_champion(),
    )

    reconciliation = summary["accounting_reconciliation"]
    assert reconciliation["requested_rounds"] == 2
    assert reconciliation["screened_rounds"] == 2
    assert reconciliation["formal_screened_candidates"] == 1
    assert reconciliation["protocol_evaluated_candidates"] == 2
    assert reconciliation["protocol_stage_counts"] == {
        "screening": 2,
        "validation": 0,
        "frozen": 0,
    }
    assert reconciliation["effective_rounds_completed"] == 1
    assert reconciliation["screened_minus_effective"] == 1
    assert reconciliation["non_effective_screening_count"] == 1
    non_effective = reconciliation["non_effective_screenings"][0]
    assert non_effective["branch_id"] == "branch-1"
    assert non_effective["hypothesis_id"] == "hyp-1"
    assert "TELEMETRY_VALIDATION_REPAIRABLE" in non_effective["reason_codes"]
    assert non_effective["decision"] == "continue_explore"
    assert non_effective["protocol_stage"] == "screening"
    assert non_effective["effective"] is False
    assert not str(non_effective["raw_metrics_ref"]).startswith("/")
    assert reconciliation["accepted_experiments"] == 1
    assert reconciliation["accepted_screening_experiments"] == 1
    assert reconciliation["model_repair_attempts"] == 0
    assert reconciliation["model_repair_failures"] == 1
    assert reconciliation["telemetry_repairable_attempts"] == 1
    assert reconciliation["quality_blocks"] == 1
    assert reconciliation["quality_block_ledger_count"] == 1
    assert reconciliation["quality_block_ledger"][0]["source"] == (
        "aggregate_reconciliation"
    )
    assert reconciliation["attempt_breakdown"]["non_effective_screening_count"] == 1
    assert reconciliation["attempt_breakdown"]["quality_block_ledger_count"] == 1
    assert {
        "relation": "screened_rounds_minus_effective_rounds",
        "delta": 1,
        "primary_reason": "screened_formal_results_excluded_from_effective_rounds",
        "telemetry_failed_experiments": 1,
    } in reconciliation["reconciliation"]
    assert summary["proposal_accounting"]["accounting_reconciliation"] == (
        reconciliation
    )
    assert summary["proposal_accounting"]["non_effective_screening_count"] == 1


def test_campaign_summary_separates_formal_screening_from_holdout_protocol_counts(
    tmp_path: Path,
) -> None:
    recorder = EvidenceRecorder(campaign_id="camp-1", campaign_dir=tmp_path)
    screening_step = replace(
        _step("/tmp/accounting-screening.json"),
        round_num=1,
        decision=Decision.QUEUE_VALIDATE,
    )
    validation_step = replace(
        _step("/tmp/accounting-validation.json"),
        round_num=2,
        decision=Decision.QUEUE_FROZEN,
    )
    validation_step.protocol_result = replace(
        validation_step.protocol_result,
        stage=ExperimentStage.VALIDATION,
        raw_metrics_ref="/tmp/accounting-validation.json",
    )
    frozen_step = replace(
        _step("/tmp/accounting-frozen.json"),
        round_num=3,
        decision=Decision.PROMOTE,
    )
    frozen_step.protocol_result = replace(
        frozen_step.protocol_result,
        stage=ExperimentStage.FROZEN,
        raw_metrics_ref="/tmp/accounting-frozen.json",
    )
    repair_step = replace(
        _step("/tmp/accounting-repairable.json"),
        round_num=4,
        decision=Decision.CONTINUE_EXPLORE,
        decision_reason_codes=("TELEMETRY_VALIDATION_REPAIRABLE",),
        counts_toward_max_rounds=False,
        attempt_kind="telemetry_repairable",
    )
    repair_step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=replace(
            screening_step.protocol_result.stats,
            wins=0,
            losses=0,
            ties=6,
        ),
        gate_outcome="fail",
        reason_codes=(
            "TELEMETRY_VALIDATION_REPAIRABLE",
            "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
        ),
        exposed_summary="screening telemetry repairable",
        raw_metrics_ref="/tmp/accounting-repairable.json",
        candidate_surface_runtime_summary={
            "telemetry_guard": {
                "passed": False,
                "failures": [
                    {
                        "code": "TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED",
                        "severity": "fail",
                        "category": "activation",
                        "mechanism": "generic_probe",
                    }
                ],
            }
        },
    )

    summary = recorder.write_campaign_summary(
        step_history=[screening_step, validation_step, frozen_step, repair_step],
        round_num=4,
        champion=_champion(),
        stopped_reason="max_rounds_exhausted",
    )

    assert summary["screened_experiments"] == 2
    assert summary["effective_rounds_completed"] == 3
    assert summary["formal_screened_candidates"] == 1
    assert summary["protocol_evaluated_candidates"] == 4
    assert summary["protocol_stage_counts"] == {
        "screening": 2,
        "validation": 1,
        "frozen": 1,
    }
    assert summary["proposal_accounting"]["formal_screened_candidates"] == 1
    assert summary["proposal_accounting"]["protocol_evaluated_candidates"] == 4
    reconciliation = summary["accounting_reconciliation"]
    assert reconciliation["formal_screened_candidates"] == 1
    assert reconciliation["protocol_evaluated_candidates"] == 4
    assert reconciliation["attempt_breakdown"]["formal_screened_candidates"] == 1
    assert reconciliation["attempt_breakdown"]["protocol_evaluated_candidates"] == 4


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
