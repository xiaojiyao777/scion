from __future__ import annotations

from dataclasses import fields

from scion.core.branch_hygiene import (
    branch_hygiene_context,
    branch_hygiene_guidance,
    campaign_branch_lifecycle_reroute_status,
    record_branch_lifecycle_policy_block,
)
from scion.core.branch_repair_policy import validate_branch_continuation_patch
from scion.core.decision_lifecycle_actions import (
    update_branch_screening_evidence_summary,
)
from scion.core.explore_step.pipeline import ExploreStepPipeline
from scion.core.models import (
    Branch,
    BranchState,
    CaseAggregateFeedback,
    DecisionFeatures,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    PatchProposal,
    ProtocolResult,
)
from scion.core.branch_cards import branch_prompt_card
from scion.proposal.screening_feedback import screening_feedback_summary


def test_explore_status_progress_includes_suspect_branch_hygiene() -> None:
    branch = Branch(
        branch_id="suspect-1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        current_code_hash="candidate-hash",
        last_clean_code_hash="candidate-hash",
        branch_code_status="telemetry_wiring_suspect",
        last_screening_feedback_tier="inactive",
        last_telemetry_outcome="activation_missing_or_wiring_suspect",
        telemetry_repair_mechanism_ids=("probe",),
        telemetry_repair_attempts={"probe": 1},
    )
    updates: list[dict] = []
    pipeline = ExploreStepPipeline(
        branch_controller=None,
        contract_gate=None,
        verification_gate=None,
        hypothesis_store=None,
        registry=None,
        campaign_id="camp-1",
        get_champion=lambda: None,
        pending_hypotheses={},
        branch_hypotheses={},
        branch_patches={},
        branch_current_hypothesis={},
        branch_workspaces={},
        failure_streak={},
        increment_round=lambda: 1,
        increment_rounds_since_last_promote=lambda: None,
        generate_hypothesis=lambda _branch: (None, None),
        generate_code=lambda *_args, **_kwargs: None,
        attempt_fix=lambda *_args, **_kwargs: None,
        handle_failure=lambda *_args, **_kwargs: None,
        record_step=lambda _step: None,
        setup_workspace=lambda _branch: None,
        apply_patch=lambda *_args, **_kwargs: None,
        record_verification_pass=lambda *_args, **_kwargs: None,
        archive_failed_workspace=lambda *_args, **_kwargs: None,
        evaluate=lambda *_args, **_kwargs: (None, None, None),
        apply_decision_and_finalize=lambda *_args, **_kwargs: None,
        decision_reason_codes_for=lambda *_args, **_kwargs: None,
        update_status_progress=lambda payload: updates.append(payload),
    )

    pipeline._emit_status_progress(
        branch,
        phase="proposal_hypothesis",
        round_num=4,
    )

    assert updates
    payload = updates[0]
    assert payload["branch_code_status"] == "telemetry_wiring_suspect"
    assert payload["last_telemetry_outcome"] == (
        "activation_missing_or_wiring_suspect"
    )
    assert payload["repair_focus_required"] is True
    assert payload["repair_focus_reason"] == "wiring_suspect_requires_repair"
    assert payload["repair_policy"] == "repair_first_same_mechanism_or_clean_fork"
    assert payload["repair_mechanism_ids"] == ["probe"]
    assert payload["telemetry_repair_attempts"] == {"probe": 1}


def test_activation_missing_outcome_requires_repair_even_if_status_is_clean() -> None:
    branch = Branch(
        branch_id="suspect-by-outcome",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="clean",
        last_telemetry_outcome="activation_missing_or_wiring_suspect",
    )

    payload = branch_hygiene_context(branch)

    assert payload["repair_focus_required"] is True
    assert payload["baseline_policy"] == "champion_required_for_repair"


def test_parked_lineage_context_exposes_inactive_slot_policy() -> None:
    branch = Branch(
        branch_id="parked-1",
        state=BranchState.PARKED_LINEAGE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="parked_lineage",
        best_quality_checkpoint_id="checkpoint-best",
    )

    payload = branch_hygiene_context(branch)

    assert payload["status"] == "parked_lineage"
    assert payload["lineage_status"] == "parked"
    assert payload["active_slot_status"] == "parked_lineage"
    assert payload["counts_toward_active_slots"] is False
    assert payload["allowed_next_actions"] == ["clean_fork"]
    assert "consume_active_slot" in payload["forbidden_next_actions"]
    assert payload["baseline_policy"] == "parked_lineage_clean_fork_required"


def test_active_branch_card_separates_proposal_blocks_from_algorithm_reasons() -> None:
    branch = Branch(
        branch_id="active-with-schema-block",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_marginal",
        last_screening_feedback_tier="marginal",
        failure_codes=[
            "SCHEMA_QUALITY_BLOCK",
            "MECHANISM_CHANGES_DUPLICATE_ID_CONFLICT",
            "PROPOSAL_PREMISE_CONTRADICTED",
            "SCREENING_FAIL_LOW_WIN_RATE",
        ],
        branch_evidence_summary={
            "reason_codes": [
                "C11_EXPECTED_TELEMETRY",
                "SCREENING_MARGINAL_SIGNAL_CONTINUE",
            ],
        },
    )

    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)

    assert payload["active_slot_status"] == "active_slot"
    assert payload["counts_toward_active_slots"] is True
    assert payload["why_not_promoted_reason_codes"] == [
        "SCREENING_FAIL_LOW_WIN_RATE",
        "SCREENING_MARGINAL_SIGNAL_CONTINUE",
    ]
    assert payload["proposal_block_reason_codes"] == [
        "SCHEMA_QUALITY_BLOCK",
        "MECHANISM_CHANGES_DUPLICATE_ID_CONFLICT",
        "PROPOSAL_PREMISE_CONTRADICTED",
        "C11_EXPECTED_TELEMETRY",
    ]
    assert "why_not_promoted_reason_codes=SCREENING_FAIL_LOW_WIN_RATE" in text
    assert "SCHEMA_QUALITY_BLOCK" not in text.split(
        "why_not_promoted_reason_codes=",
        1,
    )[1].split(" ", 1)[0]
    assert "proposal_block_reason_codes=SCHEMA_QUALITY_BLOCK" in text


def test_branch_card_uses_structured_decision_reason_codes_when_block_empty() -> None:
    branch = Branch(
        branch_id="structured-reasons",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_marginal",
        branch_evidence_summary={
            "decision_reason_codes": ["SCREENING_FAIL_LOW_WIN_RATE"],
            "terminal_reason_codes": ["BRANCH_LIFECYCLE_PARK_LINEAGE"],
        },
    )

    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)

    assert payload["why_not_promoted_reason_codes"] == [
        "SCREENING_FAIL_LOW_WIN_RATE",
        "BRANCH_LIFECYCLE_PARK_LINEAGE",
    ]
    assert (
        "why_not_promoted_reason_codes=SCREENING_FAIL_LOW_WIN_RATE,"
        "BRANCH_LIFECYCLE_PARK_LINEAGE"
    ) in text


def test_active_branch_card_renders_latest_screening_decision_reason_codes() -> None:
    branch = Branch(
        branch_id="active-latest-reasons",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_neutral",
        last_screening_feedback_tier="neutral",
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=12,
            wins=0,
            losses=0,
            ties=12,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="continue",
        reason_codes=("TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",),
        exposed_summary="screening summary",
        raw_metrics_ref="/safe/screening.json",
    )
    decision_codes = (
        "SCREENING_FAIL_WIN_RATE",
        "SCREENING_NEUTRAL_SIGNAL_CONTINUE",
    )
    feedback = screening_feedback_summary(
        protocol,
        decision_reason_codes=decision_codes,
    )

    update_branch_screening_evidence_summary(
        branch,
        protocol_result=protocol,
        screening_feedback=feedback,
        decision_reason_codes=decision_codes,
    )
    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)

    assert payload["why_not_promoted_reason_codes"] == [
        "SCREENING_FAIL_WIN_RATE",
        "SCREENING_NEUTRAL_SIGNAL_CONTINUE",
        "TELEMETRY_EFFECT_ZERO_DIAGNOSTIC",
    ]
    assert "why_not_promoted_reason_codes=SCREENING_FAIL_WIN_RATE" in text
    assert "SCREENING_NEUTRAL_SIGNAL_CONTINUE" in text
    assert "TELEMETRY_EFFECT_ZERO_DIAGNOSTIC" in text


def test_branch_card_current_reason_codes_do_not_mix_prior_head() -> None:
    branch = Branch(
        branch_id="active-two-round-reasons",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
    )
    weak_protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=12,
            wins=4,
            losses=2,
            ties=6,
            win_rate=1 / 3,
            median_delta=0.2,
            ci_low=0.1,
            ci_high=0.6,
        ),
        gate_outcome="continue",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="weak positive screening",
        raw_metrics_ref="/safe/weak.json",
    )
    weak_codes = (
        "SCREENING_FAIL_WIN_RATE",
        "SCREENING_WEAK_SIGNAL_CONTINUE",
    )
    weak_feedback = screening_feedback_summary(
        weak_protocol,
        decision_reason_codes=weak_codes,
    )
    update_branch_screening_evidence_summary(
        branch,
        protocol_result=weak_protocol,
        screening_feedback=weak_feedback,
        decision_reason_codes=weak_codes,
    )

    branch.best_quality_checkpoint_id = "checkpoint-rn"
    branch.last_branch_lifecycle_policy_block = {
        "gate_observation_reason_codes": list(weak_codes),
        "why_not_promoted_reason_codes": list(weak_codes),
        "reason_codes": list(weak_codes),
    }
    branch.branch_code_status = "active_marginal"
    branch.last_screening_feedback_tier = "marginal"
    marginal_protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=12,
            wins=3,
            losses=3,
            ties=6,
            win_rate=0.25,
            median_delta=0.0,
            ci_low=-0.5,
            ci_high=1.5,
        ),
        gate_outcome="continue",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="marginal follow-up screening",
        raw_metrics_ref="/safe/marginal.json",
    )
    marginal_codes = (
        "SCREENING_FAIL_WIN_RATE",
        "SCREENING_MARGINAL_SIGNAL_CONTINUE",
    )
    marginal_feedback = screening_feedback_summary(
        marginal_protocol,
        decision_reason_codes=marginal_codes,
    )

    update_branch_screening_evidence_summary(
        branch,
        protocol_result=marginal_protocol,
        screening_feedback=marginal_feedback,
        decision_reason_codes=marginal_codes,
    )
    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)
    campaign_payload = campaign_branch_lifecycle_reroute_status([branch])

    assert payload["gate_observation_reason_codes"] == list(marginal_codes)
    assert payload["why_not_promoted_reason_codes"] == list(marginal_codes)
    assert payload["best_checkpoint_reason_codes"] == list(weak_codes)
    assert "SCREENING_WEAK_SIGNAL_CONTINUE" in payload["history_reason_codes"]
    assert payload["last_branch_lifecycle_policy_block"] == {}
    assert campaign_payload == {}
    assert "SCREENING_MARGINAL_SIGNAL_CONTINUE" in text
    assert "SCREENING_WEAK_SIGNAL_CONTINUE" not in text
    assert branch.failure_codes == []


def test_branch_card_telemetry_summaries_are_current_best_history_scoped() -> None:
    branch = Branch(
        branch_id="telemetry-layering",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
    )
    weak_protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=12,
            wins=2,
            losses=0,
            ties=10,
            win_rate=1 / 6,
            median_delta=0.2,
            ci_low=0.0,
            ci_high=0.5,
        ),
        gate_outcome="continue",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="weak positive screening",
        raw_metrics_ref="/safe/weak.json",
    )
    weak_codes = (
        "SCREENING_FAIL_WIN_RATE",
        "SCREENING_WEAK_SIGNAL_CONTINUE",
    )
    update_branch_screening_evidence_summary(
        branch,
        protocol_result=weak_protocol,
        screening_feedback=screening_feedback_summary(
            weak_protocol,
            decision_reason_codes=weak_codes,
        ),
        decision_reason_codes=weak_codes,
    )

    branch.best_quality_checkpoint_id = "checkpoint-best"
    branch.last_valid_checkpoint_id = "checkpoint-best"
    branch.branch_code_status = "active_no_effect"
    branch.last_screening_feedback_tier = "no_effect"
    no_effect_protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=12,
            wins=0,
            losses=0,
            ties=12,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
        ),
        gate_outcome="continue",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="no-effect follow-up screening",
        raw_metrics_ref="/safe/no-effect.json",
    )
    no_effect_codes = (
        "SCREENING_FAIL_WIN_RATE",
        "SCREENING_NEUTRAL_SIGNAL_CONTINUE",
    )

    update_branch_screening_evidence_summary(
        branch,
        protocol_result=no_effect_protocol,
        screening_feedback=screening_feedback_summary(
            no_effect_protocol,
            decision_reason_codes=no_effect_codes,
        ),
        decision_reason_codes=no_effect_codes,
    )
    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)

    assert payload["generic_evidence_summary"]["tier"] == "no_effect"
    assert payload["current_head_generic_evidence_summary"]["wins"] == 0
    assert payload["active_slot_status"] == "active_slot"
    assert payload["counts_toward_active_slots"] is True
    assert payload["current_head_active_slot_release_reason"] == ""
    assert (
        payload.get("retained_checkpoint_no_effect_current_head_released")
        is not True
    )
    assert payload["phase_activation_summary"]["effect_status"] == (
        "no_objective_effect"
    )
    assert payload["current_head_phase_activation_summary"] == (
        payload["phase_activation_summary"]
    )
    assert payload["best_checkpoint_reason_codes"] == list(weak_codes)
    assert payload["best_checkpoint_generic_evidence_summary"]["tier"] == (
        "weak_positive"
    )
    assert payload["best_checkpoint_generic_evidence_summary"]["wins"] == 2
    assert payload["best_checkpoint_phase_activation_summary"]["effect_status"] == (
        "case_level_positive_signal"
    )
    assert payload["history_phase_activation_summaries"] == [
        payload["best_checkpoint_phase_activation_summary"]
    ]
    assert "generic_evidence_summary=tier:no_effect" in text
    assert "best_checkpoint_generic_evidence_summary=tier:weak_positive" in text
    assert "best_checkpoint_phase_activation_summary=stage:screening" in text
    assert "current_head_active_slot_release_reason=" not in text
    assert "retained_checkpoint_no_effect_current_head_released=true" not in text
    assert "history_phase_activation_summaries=stage:screening" in text


def test_branch_card_exposes_case_activation_and_runtime_confidence() -> None:
    branch = Branch(
        branch_id="case-card",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=3,
            wins=1,
            losses=1,
            ties=1,
            win_rate=1 / 3,
            median_delta=0.05,
            ci_low=-0.01,
            ci_high=0.12,
            runtime_ratio_median=1.08,
            runtime_delta_median_ms=12.0,
            runtime_regression_rate=0.34,
            runtime_pairs=3,
            statistical_metric="objective_delta",
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_LOW_WIN_RATE",),
        exposed_summary="screening failed",
        raw_metrics_ref="/tmp/metrics.json",
        case_feedback=(
            CaseAggregateFeedback(
                case_id="case-a",
                n_pairs=3,
                wins=2,
                losses=0,
                ties=1,
                win_rate=2 / 3,
                dominant_result="win",
                decisive_metric="objective_delta",
                median_deltas={"objective_delta": 0.40},
            ),
            CaseAggregateFeedback(
                case_id="case-b",
                n_pairs=3,
                wins=0,
                losses=2,
                ties=1,
                win_rate=0.0,
                dominant_result="loss",
                decisive_metric="objective_delta",
                median_deltas={"objective_delta": -0.20},
            ),
        ),
        candidate_operator_attempts=4,
        runtime_confidence="low_cached_champion",
        champion_cache_hits=3,
        champion_cached_runtime_pairs=3,
    )
    feedback = screening_feedback_summary(
        protocol,
        decision_reason_codes=("SCREENING_WEAK_SIGNAL_CONTINUE",),
    )

    update_branch_screening_evidence_summary(
        branch,
        protocol_result=protocol,
        screening_feedback=feedback,
    )
    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)
    evidence_summary = branch.branch_evidence_summary

    assert payload["case_level_winners"] == [
        {
            "case_id": "case-a",
            "result": "win",
            "delta": 0.4,
            "effect_counters": {"wins": 2, "losses": 0, "ties": 1, "pairs": 3},
        }
    ]
    assert evidence_summary["case_level_positive_cases"] == evidence_summary[
        "case_level_winners"
    ]
    assert payload["case_level_losses"][0]["case_id"] == "case-b"
    assert evidence_summary["case_level_negative_cases"] == evidence_summary[
        "case_level_losses"
    ]
    assert payload["phase_activation_summary"]["stage"] == "screening"
    assert payload["phase_activation_summary"]["activation_status"] == "observed"
    assert payload["runtime_evidence_confidence"] == "low_cached_champion"
    assert payload["generic_evidence_summary"]["runtime_evidence_confidence"] == (
        "low_cached_champion"
    )
    assert "case_level_positive_cases=case-a:win:delta=0.4:w2l0t1" in text
    assert "case_level_negative_cases=case-b:loss:delta=-0.2:w0l2t1" in text
    assert "case_level_winners=" not in text
    assert "case_level_losses=" not in text
    assert "phase_activation_summary=stage:screening" in text
    assert "runtime_evidence_confidence=low_cached_champion" in text


def test_branch_card_exposes_runtime_evidence_pressure_count() -> None:
    branch = Branch(
        branch_id="runtime-pressure-card",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_marginal",
        last_screening_feedback_tier="marginal",
        branch_evidence_summary={
            "tier": "marginal",
            "wins": 1,
            "losses": 1,
            "runtime_evidence_pressure_count": "2",
        },
    )

    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)

    assert payload["runtime_evidence_pressure_count"] == 2
    assert payload["current_head_runtime_evidence_pressure_count"] == 2
    assert payload["generic_evidence_summary"][
        "runtime_evidence_pressure_count"
    ] == 2
    assert "runtime_evidence_pressure_count:2" in text
    assert "runtime_evidence_pressure_count=2" in text


def test_branch_card_separates_discarded_head_from_retained_evidence_followup() -> None:
    branch = Branch(
        branch_id="discarded-weak-positive-fresh-runtime",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="discarded",
        last_screening_feedback_tier="weak_positive",
        branch_evidence_summary={
            "stage": "screening",
            "tier": "weak_positive",
            "evidence_retention_status": "retained",
            "wins": 0,
            "losses": 0,
            "ties": 4,
            "pair_wins": 1,
            "pair_losses": 0,
            "pair_ties": 3,
            "runtime_evidence_confidence": "low_cached_champion",
            "runtime_evidence_status": "fresh_champion_required",
            "fresh_runtime_followup": {
                "schema_version": "fresh_runtime_followup.v1",
                "queue_intent": "fresh_champion_runtime_replay",
                "scheduler_marker": "fresh_champion_runtime_replay_pending",
                "trigger": "pair_level_win_no_loss",
                "fresh_runtime_pending": True,
                "fresh_runtime_required": True,
                "followup_recommended": True,
                "followup_required": True,
                "followup_policy": (
                    "fresh_champion_runtime_required_before_runtime_based_escalation"
                ),
                "decision_features_excluded": True,
            },
        },
    )

    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)

    assert payload["candidate_code_retention_status"] == "discarded"
    assert payload["candidate_code_retained"] is False
    assert payload["evidence_retention_status"] == "retained"
    assert payload["candidate_evidence_retained"] is True
    assert payload["followup_recommended"] is True
    assert payload["followup_required"] is True
    assert payload["fresh_runtime_pending"] is True
    assert payload["fresh_runtime_required"] is True
    assert payload["generic_evidence_summary"]["fresh_runtime_pending"] is True
    assert payload["generic_evidence_summary"]["fresh_runtime_required"] is True
    assert "current_head_status=discarded" in text
    assert "candidate_code_retention=discarded" in text
    assert "evidence_retention=retained" in text
    assert "followup_required=true" in text
    assert "fresh_runtime_pending=true" in text
    assert "fresh_runtime_followup=pair_level_win_no_loss" in text


def test_branch_card_and_prompt_guidance_include_runtime_low_confidence_advisory() -> None:
    branch = Branch(
        branch_id="runtime-clean-fork-card",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
        branch_evidence_summary={
            "tier": "weak_positive",
            "wins": 1,
            "losses": 1,
            "runtime_evidence_confidence": "low_cached_champion",
            "runtime_evidence_status": "insufficient",
            "runtime_aggregate_exclusion": {"excluded": True},
            "runtime_evidence_pressure_count": 2,
        },
    )

    payload = branch_hygiene_context(branch)
    card = branch_prompt_card(branch)
    guidance = branch_hygiene_guidance(branch)
    decision_field_names = {field.name for field in fields(DecisionFeatures)}

    assert "clean_fork" not in payload["allowed_next_actions"]
    assert "refine_checkpoint" in payload["allowed_next_actions"]
    assert payload["runtime_evidence_low_confidence_advisory"] == {
        "reason": "runtime_evidence_completeness_clean_fork",
        "policy": "fresh_runtime_advisory",
        "runtime_evidence_pressure_count": 2,
        "case_wins": 1,
        "case_losses": 1,
        "case_balance": "case_loss",
        "runtime_evidence_confidence": "low_cached_champion",
        "runtime_evidence_status": "insufficient",
        "runtime_aggregate_excluded": True,
        "runtime_evidence_pressure_triggers": [
            "low_or_cached_runtime_confidence",
            "runtime_evidence_status:insufficient",
            "runtime_aggregate_excluded",
        ],
        "runtime_signal_role": "low_confidence_advisory",
        "strong_branch_constraint": False,
        "proposal_guidance": (
            "Need fresh champion runtime before runtime-based conclusions; do not "
            "treat runtime saturation/pressure as a strong diagnostic when "
            "runtime aggregate evidence is excluded or low confidence."
        ),
        "tainted_proposal_guidance": True,
        "decision_features_excluded": True,
    }
    assert (
        "runtime_evidence_low_confidence_advisory="
        "runtime_evidence_completeness_clean_fork"
    ) in card
    assert "Low-confidence runtime evidence advisory is active" in guidance
    assert "Need fresh champion runtime before runtime-based conclusions" in guidance
    assert "prefer a clean branch/fork" not in guidance
    assert "excluded from DecisionFeatures" in guidance
    assert "runtime_evidence_clean_fork_guidance" not in payload
    assert "runtime_evidence_clean_fork_guidance" not in decision_field_names
    assert "runtime_evidence_clean_fork_reason" not in decision_field_names


def test_branch_card_explains_low_confidence_runtime_aggregate_exclusion() -> None:
    branch = Branch(
        branch_id="runtime-exclusion-card",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
    )
    protocol = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=3,
            wins=0,
            losses=0,
            ties=3,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            runtime_pairs=0,
            statistical_metric="objective_delta",
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_LOW_WIN_RATE",),
        exposed_summary="screening no effect",
        raw_metrics_ref="/tmp/metrics.json",
        runtime_confidence="low_cached_champion",
        champion_cached_runtime_pairs=3,
        mechanism_evidence={
            "primary_activation_status": "zero",
            "primary_effect_status": "zero",
        },
        candidate_surface_runtime_summary={
            "fields": {
                "candidate_elapsed_ms": {
                    "present": 3,
                    "missing": 0,
                    "empty": 0,
                    "failed": 0,
                }
            }
        },
    )
    feedback = screening_feedback_summary(protocol)

    update_branch_screening_evidence_summary(
        branch,
        protocol_result=protocol,
        screening_feedback=feedback,
    )
    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)

    exclusion = payload["generic_evidence_summary"]["runtime_aggregate_exclusion"]
    assert exclusion["reason"] == "low_cached_champion"
    assert exclusion["candidate_runtime_pair_evidence_count"] == 3
    assert payload["phase_activation_summary"]["activation_evidence_status"] == (
        "zero_activation"
    )
    assert payload["phase_activation_summary"]["objective_effect_status"] == (
        "zero_objective_effect"
    )
    assert "runtime_aggregate_excluded:low_cached_champion" in text
    assert "activation_evidence_status:zero_activation" in text
    assert "objective_effect_status:zero_objective_effect" in text


def test_active_no_effect_context_exposes_same_mechanism_followup_policy() -> None:
    branch = Branch(
        branch_id="active-no-effect",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        last_telemetry_outcome="no_objective_effect",
        branch_mechanism_ids=("bounded_probe",),
    )

    payload = branch_hygiene_context(branch)

    assert payload["repair_focus_required"] is False
    assert payload["hypothesis_generation_mode"] == "same_mechanism_only"
    assert payload["branch_followup_policy"] == "same_mechanism_followup_only"
    assert payload["clean_fork_policy"] == "clean_fork_required_for_new_mechanism"
    assert payload["branch_mechanism_ids"] == ["bounded_probe"]
    assert payload["allowed_mechanism_ids"] == ["bounded_probe"]
    assert payload["protected_mechanism_ids"] == ["bounded_probe"]
    assert payload["forbidden_mechanism_policy"] == "no_unrelated_mechanism_ids"
    assert payload["same_mechanism_allowed_actions"] == [
        "diagnostic",
        "observability",
        "refine",
        "tune",
        "integrate",
        "repair",
        "parameterize",
        "telemetry_wiring",
    ]
    assert payload["diversity_reroute_guidance"]["policy"] == (
        "runtime_saturated_diversity_reroute"
    )
    assert "mechanism family" in payload["diversity_reroute_guidance"]["guidance"]
    assert payload["baseline_policy"] == (
        "branch_workspace_same_mechanism_followup_only"
    )


def test_repeated_no_effect_fresh_runtime_missing_replay_identity_is_replay_blocked() -> None:
    branch = Branch(
        branch_id="no-effect-missing-replay",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        last_telemetry_outcome="no_objective_effect",
        lifecycle_marginal_no_effect_streak=2,
        lifecycle_no_effect_diagnostic_followups=2,
        lifecycle_signal_repeat_count=2,
        branch_mechanism_ids=("bounded_probe",),
        branch_evidence_summary={
            "stage": "screening",
            "tier": "no_effect",
            "wins": 0,
            "losses": 0,
            "ties": 8,
            "pair_wins": 0,
            "pair_losses": 0,
            "pair_ties": 8,
            "runtime_evidence_confidence": "low_cached_champion",
            "runtime_evidence_status": "fresh_champion_required",
            "runtime_evidence_pressure_count": 2,
            "fresh_runtime_required": True,
            "fresh_runtime_pending": True,
            "fresh_runtime_followup": {
                "schema_version": "fresh_runtime_followup.v1",
                "queue_intent": "fresh_champion_runtime_replay",
                "scheduler_marker": "fresh_champion_runtime_replay_pending",
                "trigger": "fresh_runtime_required",
                "fresh_runtime_pending": True,
                "fresh_runtime_required": True,
                "followup_required": True,
                "decision_features_excluded": True,
            },
        },
    )

    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)
    decision_field_names = {field.name for field in fields(DecisionFeatures)}

    assert payload["lineage_status"] == "replay_blocked"
    assert payload["branch_final_classification"] == "replay_blocked"
    assert payload["final_branch_classification"]["reason"] == (
        "fresh_runtime_replay_blocked_missing_identity"
    )
    assert payload["final_branch_classification"]["detail"][
        "missing_replay_identity_keys"
    ] == ["replay_identity"]
    assert payload["active_slot_status"] == "released_active_slot"
    assert payload["counts_toward_active_slots"] is False
    assert payload["current_head_active_slot_release_reason"] in {
        "fresh_runtime_replay_blocked_missing_identity",
        "repeated_no_effect_zero_effect_slot_release",
    }
    assert payload["allowed_next_actions"] == ["clean_fork"]
    assert "replay_without_identity" in payload["forbidden_next_actions"]
    assert payload["hypothesis_generation_mode"] == "clean_fork_only"
    assert payload["baseline_policy"] == (
        "fresh_runtime_replay_blocked_clean_fork_required"
    )
    assert payload["final_branch_classification"]["decision_features_excluded"] is True
    assert "branch_final_classification" not in decision_field_names
    assert "final_branch_classification" not in decision_field_names
    assert "lineage_status=replay_blocked" in text


def test_lifecycle_policy_block_marks_branch_for_clean_fork_reroute() -> None:
    branch = Branch(
        branch_id="blocked-no-effect",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        last_telemetry_outcome="no_objective_effect",
        branch_mechanism_ids=("bounded_probe",),
    )

    block = record_branch_lifecycle_policy_block(
        branch,
        (
            "branch_lifecycle_policy_violation: "
            "new_mechanism_requires_clean_fork; "
            "protected_mechanism_ids=bounded_probe; "
            "proposed_mechanism_ids=different_probe"
        ),
    )
    payload = branch_hygiene_context(branch)
    campaign_payload = campaign_branch_lifecycle_reroute_status([branch])

    assert block["reason"] == "new_mechanism_requires_clean_fork"
    assert block["diagnostic_kind"] == "branch_routing_diagnostic"
    assert block["failure_accounting"] == "not_run_validity_failure"
    assert block["candidate_routing"] == "new_mechanism_requires_clean_fork_signal"
    assert block["clean_fork_signal"] is True
    assert payload["branch_lifecycle_policy_blocks"] == 1
    assert payload["branch_lifecycle_new_mechanism_ineligible"] is True
    assert payload["branch_lifecycle_reroute_reason"] == (
        "clean_fork_after_branch_lifecycle_policy_block"
    )
    assert payload["next_branch_selection_policy"] == (
        "clean_branch_or_clean_fork_for_new_mechanism"
    )
    assert campaign_payload["ineligible_branch_ids"] == [branch.branch_id]
    assert campaign_payload["last_policy_block"]["branch_id"] == branch.branch_id


def test_same_mechanism_followup_patch_blocks_unrelated_mechanism_ids() -> None:
    branch = Branch(
        branch_id="active-no-effect-followup",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        last_telemetry_outcome="no_objective_effect",
        branch_mechanism_ids=("bounded_probe",),
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Tune bounded_probe on the same branch.",
        target_weakness="The existing bounded_probe needs tuning.",
        expected_effect="Improve objective by tuning bounded_probe.",
        change_locus="solver_design",
        target_file="policies/baseline_algorithm.py",
        action="modify",
        mechanism_changes=({"id": "bounded_probe", "change_type": "modify"},),
    )
    protected_patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content="",
        mechanism_changes=({"id": "bounded_probe", "change_type": "modify"},),
    )
    unrelated_patch = PatchProposal(
        file_path="policies/baseline_algorithm.py",
        action="modify",
        code_content="",
        mechanism_changes=({"id": "new_restart", "change_type": "add"},),
    )

    allowed = validate_branch_continuation_patch(branch, hypothesis, protected_patch)
    blocked = validate_branch_continuation_patch(branch, hypothesis, unrelated_patch)

    assert allowed.allowed is True
    assert blocked.allowed is False
    assert blocked.reason == "new_mechanism_requires_clean_fork"
    assert blocked.protected_mechanism_ids == ("bounded_probe",)
    assert blocked.proposed_mechanism_ids == ("new_restart",)


def test_weak_positive_same_mechanism_refinement_does_not_lifecycle_block() -> None:
    branch = Branch(
        branch_id="weak-positive-followup",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
        last_telemetry_outcome="case_level_positive_signal",
        branch_mechanism_ids=("construction_multistart",),
    )
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Refine the existing construction_multistart mechanism on this "
            "same branch and target."
        ),
        target_weakness="The prior weak signal needs a tighter local schedule.",
        expected_effect="Preserve the weak signal while reducing wasted work.",
        change_locus="solver_design",
        target_file="policies/baseline_modules/scheduler.py",
        action="modify",
        mechanism_changes=(
            {"id": "construction_multistart", "change_type": "modify"},
        ),
    )
    patch = PatchProposal(
        file_path="policies/baseline_modules/scheduler.py",
        action="modify",
        code_content="",
        mechanism_changes=(
            {"id": "construction_multistart", "change_type": "modify"},
        ),
    )

    allowed = validate_branch_continuation_patch(branch, hypothesis, patch)

    assert allowed.allowed is True
    assert allowed.detail == ""
    assert allowed.protected_mechanism_ids == ("construction_multistart",)
    assert allowed.proposed_mechanism_ids == ("construction_multistart",)
    assert allowed.branch_followup_policy == (
        "branch_local_followup_or_explicit_bridge"
    )


def test_weak_positive_unknown_protected_ids_do_not_hard_block_bridge() -> None:
    branch = Branch(
        branch_id="weak-positive-bridge",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion-hash",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
    )
    hypothesis = HypothesisProposal(
        hypothesis_text=(
            "Bridge from the prior weak signal on the same branch: this tests "
            "a branch-local failure because the earlier mechanism cannot "
            "directly be refined without moving the activation point."
        ),
        target_weakness="The previous branch-local attempt needs a bridge.",
        expected_effect="Preserve the weak signal while testing a new target.",
        change_locus="solver_design",
        target_file="policies/alternate_policy.py",
        action="modify",
        mechanism_changes=({"id": "bridged_followup", "change_type": "add"},),
    )
    patch = PatchProposal(
        file_path="policies/alternate_policy.py",
        action="modify",
        code_content="",
        mechanism_changes=({"id": "bridged_followup", "change_type": "add"},),
    )

    allowed = validate_branch_continuation_patch(branch, hypothesis, patch)

    assert allowed.allowed is True
    assert allowed.detail == ""
    assert allowed.protected_mechanism_ids == ()
    assert allowed.proposed_mechanism_ids == ("bridged_followup",)
    assert allowed.branch_followup_policy == (
        "branch_local_followup_or_explicit_bridge"
    )
