from __future__ import annotations

from scion.core import scheduler as scheduler_facade
from scion.core.branch_lifecycle_policy import (
    BRANCH_LIFECYCLE_PARK_LINEAGE,
    SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE,
)
from scion.core.branch_hygiene import ACTIVATION_MISSING_OR_WIRING_SUSPECT
from scion.core.decision_lifecycle_actions import (
    update_branch_screening_evidence_summary,
)
from scion.core.models import (
    Branch,
    BranchState,
    EvalStats,
    ExperimentStage,
    ProtocolResult,
)
from scion.core.scheduler import (
    PLATEAU_GATE_MATERIAL_DIFFERENCE_REASON,
    PLATEAU_GATE_SAME_BRANCH_REFINEMENT_REASON,
    RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON,
    Scheduler,
    active_slot_inventory,
    reclaim_active_slot_for_new_branch,
    reconcile_active_slot_overflow,
)
from scion.core.scheduling.runtime_pressure import (
    branch_runtime_evidence_clean_fork_pressure_summary,
)
from scion.proposal.screening_feedback import screening_feedback_summary


def _runtime_pressure_protocol() -> ProtocolResult:
    return ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            runtime_pairs=0,
            valid_pairs=4,
        ),
        gate_outcome="fail",
        reason_codes=("SCREENING_FAIL_WIN_RATE",),
        exposed_summary="screening runtime evidence incomplete",
        raw_metrics_ref="/tmp/metrics.json",
        runtime_confidence="low_cached_champion",
        runtime_evidence_status="insufficient",
        champion_cached_runtime_pairs=4,
    )


def test_runtime_pressure_summary_module_matches_scheduler_facade() -> None:
    branch = Branch(
        branch_id="runtime-pressure-summary-facade",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
        direction="tainted proposal text must not appear",
        branch_evidence_summary={
            "wins": "0",
            "losses": "-1",
            "runtime_evidence_confidence": " low_cached_champion ",
            "runtime_evidence_status": "fresh_required",
            "runtime_aggregate_exclusion": {"excluded": True},
            "runtime_evidence_pressure_count": "2",
        },
    )

    summary = branch_runtime_evidence_clean_fork_pressure_summary(branch)

    assert (
        summary
        == scheduler_facade.branch_runtime_evidence_clean_fork_pressure_summary(
            branch
        )
    )
    assert summary["reason"] == RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
    assert summary["policy"] == "prefer_clean_fork"
    assert summary["runtime_evidence_pressure_count"] == 2
    assert summary["case_wins"] == 0
    assert summary["case_losses"] == 0
    assert summary["case_balance"] == "no_case_win"
    assert summary["runtime_evidence_confidence"] == "low_cached_champion"
    assert summary["runtime_evidence_status"] == "fresh_required"
    assert summary["runtime_aggregate_excluded"] is True
    assert summary["runtime_evidence_pressure_triggers"] == [
        "low_or_cached_runtime_confidence",
        "runtime_evidence_status:fresh_required",
        "runtime_aggregate_excluded",
    ]
    assert summary["tainted_proposal_guidance"] is True
    assert summary["decision_features_excluded"] is True
    assert "tainted proposal text" not in str(summary)


def test_active_slot_reclaim_requires_decision_origin_park_marker() -> None:
    branch = Branch(
        branch_id="low-value-without-marker",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        lifecycle_no_effect_diagnostic_followups=1,
    )

    reconciliation = reclaim_active_slot_for_new_branch(
        [branch],
        max_active_branches=1,
    )
    inventory = active_slot_inventory([branch], max_active_branches=1)

    assert reconciliation.changed is False
    assert reconciliation.blocked is True
    assert reconciliation.after_used == 1
    assert reconciliation.candidate_branch_ids == (branch.branch_id,)
    assert reconciliation.marker_missing_branch_ids == (branch.branch_id,)
    assert branch.state == BranchState.EXPLORE
    assert inventory["used"] == 1
    assert inventory["parked_lineage_ids"] == []
    audit = reconciliation.as_audit_metadata()
    assert audit["decision_origin_marker_required"] is True
    assert audit["blocked_reason"] == "decision_origin_lifecycle_marker_missing"


def test_active_slot_reclaim_parks_branch_with_decision_origin_marker() -> None:
    branch = Branch(
        branch_id="decision-marked-low-value",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        lifecycle_no_effect_diagnostic_followups=1,
        branch_lifecycle_policy_blocks=1,
        last_branch_lifecycle_policy_block={
            "reason": "park_lineage",
            "block_count": 1,
            "lifecycle_action_reason_codes": [BRANCH_LIFECYCLE_PARK_LINEAGE],
        },
    )

    reconciliation = reclaim_active_slot_for_new_branch(
        [branch],
        max_active_branches=1,
    )
    inventory = active_slot_inventory([branch], max_active_branches=1)

    assert reconciliation.changed is True
    assert reconciliation.blocked is False
    assert reconciliation.after_used == 0
    assert reconciliation.parked_branch_ids == (branch.branch_id,)
    assert branch.state == BranchState.PARKED_LINEAGE
    assert branch.last_branch_lifecycle_policy_block[
        "lifecycle_action_reason_codes"
    ] == [BRANCH_LIFECYCLE_PARK_LINEAGE]
    assert inventory["used"] == 0
    assert inventory["parked_lineage_ids"] == [branch.branch_id]


def test_no_effect_exhausted_head_releases_active_slot_without_parking() -> None:
    branch = Branch(
        branch_id="no-effect-slot-release",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        lifecycle_no_effect_diagnostic_followups=2,
    )

    action = Scheduler(max_active_branches=1).select_next([branch])
    inventory = active_slot_inventory([branch], max_active_branches=1)

    assert action.action == "create_new"
    assert action.reason == "new_exploration_slot_available"
    assert branch.state == BranchState.EXPLORE
    assert inventory["used"] == 0
    assert inventory["released_active_slot_ids"] == [branch.branch_id]
    assert inventory["released_active_slot_reasons"][branch.branch_id] == (
        "repeated_no_effect_zero_effect_slot_release"
    )
    assert inventory["parked_lineage_ids"] == []


def test_active_slot_overflow_does_not_park_without_decision_marker() -> None:
    branches = [
        Branch(
            branch_id=f"active-{index}",
            state=BranchState.EXPLORE,
            base_champion_id=1,
            base_champion_hash="champion",
        )
        for index in range(2)
    ]

    reconciliation = reconcile_active_slot_overflow(
        branches,
        max_active_branches=1,
    )

    assert reconciliation.changed is False
    assert reconciliation.blocked is True
    assert reconciliation.after_used == 2
    assert reconciliation.marker_missing_branch_ids == (
        "active-0",
        "active-1",
    )
    assert [branch.state for branch in branches] == [
        BranchState.EXPLORE,
        BranchState.EXPLORE,
    ]


def test_repeated_runtime_evidence_pressure_prefers_plateau_refinement_then_material_clean_fork() -> None:
    branch = Branch(
        branch_id="runtime-pressure",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_marginal",
        last_screening_feedback_tier="marginal",
        direction="generic established research direction",
    )
    protocol = _runtime_pressure_protocol()
    feedback = screening_feedback_summary(
        protocol,
        decision_reason_codes=(SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE,),
    )

    update_branch_screening_evidence_summary(
        branch,
        protocol_result=protocol,
        screening_feedback=feedback,
        decision_reason_codes=(SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE,),
    )
    first = Scheduler(max_active_branches=2).select_next([branch])

    update_branch_screening_evidence_summary(
        branch,
        protocol_result=protocol,
        screening_feedback=feedback,
        decision_reason_codes=(SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE,),
    )
    second = Scheduler(max_active_branches=2).select_next([branch])
    branch.branch_evidence_summary["same_branch_refinement_sampling"] = True
    branch.branch_evidence_summary["plateau_gate"][
        "same_branch_refinement_sampled"
    ] = True
    third = Scheduler(max_active_branches=2).select_next([branch])

    assert branch.branch_evidence_summary["runtime_evidence_pressure_count"] == 2
    plateau_gate = branch.branch_evidence_summary["plateau_gate"]
    assert plateau_gate["schema_version"] == "plateau_gate.v1"
    assert plateau_gate["tier"] == "no_effect"
    assert plateau_gate["effective_screened_no_effect_count"] == 2
    assert plateau_gate["runtime_evidence_pressure_count"] == 2
    assert plateau_gate["threshold_met"] is True
    assert plateau_gate["proposal_guidance_only"] is True
    assert plateau_gate["audit_only"] is True
    assert plateau_gate["decision_features_excluded"] is True
    assert "PLATEAU_GATE_THRESHOLD_MET" in plateau_gate["reason_codes"]
    assert "generic established research direction" not in str(plateau_gate)
    assert branch.branch_evidence_summary["runtime_evidence_pressure"]["triggers"] == [
        "low_or_cached_runtime_confidence",
        "runtime_evidence_status:insufficient",
        "runtime_aggregate_excluded",
    ]
    assert branch.branch_evidence_summary["runtime_evidence_pressure"][
        "proposal_guidance_only"
    ] is True
    assert branch.branch_evidence_summary["runtime_evidence_pressure"][
        "decision_features_excluded"
    ] is True
    policy = branch.branch_evidence_summary["runtime_evidence_policy"]
    assert policy["schema_version"] == "runtime_evidence_policy.v1"
    assert policy["runtime_evidence_confidence"] == "low_cached_champion"
    assert policy["runtime_evidence_status"] == "insufficient"
    assert policy["runtime_aggregate_excluded"] is True
    assert policy["standalone_optimization_signal"] is False
    assert policy["runtime_signal_role"] == "audit_or_proposal_guidance_only"
    assert policy["proposal_guidance_only"] is True
    assert policy["decision_features_excluded"] is True
    assert "RUNTIME_EVIDENCE_LOW_OR_CACHED_CONFIDENCE" in (
        policy["policy_reason_codes"]
    )
    assert (
        branch.branch_evidence_summary["runtime_evidence_pressure"][
            "runtime_signal_role"
        ]
        == "audit_or_proposal_guidance_only"
    )
    assert branch.branch_evidence_summary["runtime_evidence_pressure"][
        "standalone_optimization_signal"
    ] is False
    assert first.action == "run_existing"
    assert first.branch is branch
    assert first.slot == "refine_active"
    assert second.action == "run_existing"
    assert second.branch is branch
    assert second.slot == "refine_active"
    assert second.reason == PLATEAU_GATE_SAME_BRANCH_REFINEMENT_REASON
    assert second.audit_metadata["same_branch_refinement_selected"] is True
    assert second.audit_metadata[
        "plateau_gate_same_branch_refinement_selected"
    ] is True
    assert second.audit_metadata["same_branch_refinement_reason"] == (
        "plateau_gate_diagnostic_refinement"
    )
    assert third.action == "create_new"
    assert third.branch is None
    assert third.slot == "explore_new"
    assert third.reason == RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
    assert third.audit_metadata["runtime_evidence_clean_fork_selected"] is True
    assert (
        third.audit_metadata["runtime_evidence_clean_fork_reason"]
        == RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
    )
    assert third.audit_metadata["runtime_evidence_pressure_count_max"] == 2
    assert third.audit_metadata["material_difference_required"] is True
    assert third.audit_metadata["plateau_gate_reason"] == (
        PLATEAU_GATE_MATERIAL_DIFFERENCE_REASON
    )
    assert third.audit_metadata["material_difference_requirement"][
        "schema_version"
    ] == "material_difference_requirement.v1"
    assert third.audit_metadata["material_difference_requirement"][
        "record_type"
    ] == "material_difference_requirement"
    assert third.audit_metadata["material_difference_requirement"][
        "record_id"
    ].startswith("material_difference_requirement:")
    assert third.audit_metadata["material_difference_requirement"][
        "record_digest"
    ].startswith("sha256:")
    assert third.audit_metadata["material_difference_requirement"][
        "proposal_visibility_only"
    ] is True
    assert third.audit_metadata["material_difference_requirement"][
        "decision_features_excluded"
    ] is True
    assert third.audit_metadata["material_difference_audit_records"] == [
        third.audit_metadata["material_difference_requirement"]
    ]
    assert "PLATEAU_GATE_CLEAN_FORK_REQUIRES_MATERIAL_DIFFERENCE" in (
        third.audit_metadata["material_difference_requirement"]["reason_codes"]
    )
    assert "generic established research direction" not in str(
        third.audit_metadata["material_difference_requirement"]
    )
    assert third.audit_metadata["runtime_evidence_clean_fork_candidates"] == [
        {
            "branch_id": "runtime-pressure",
            "lineage_status": "active_marginal",
            "runtime_evidence_pressure_count": 2,
            "runtime_evidence_pressure_triggers": [
                "low_or_cached_runtime_confidence",
                "runtime_evidence_status:insufficient",
                "runtime_aggregate_excluded",
            ],
        }
    ]


def test_weak_positive_branch_exploit_survives_runtime_evidence_pressure() -> None:
    branch = Branch(
        branch_id="weak-positive-runtime-pressure",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
        direction="generic weak-positive research direction",
        branch_evidence_summary={
            "wins": 1,
            "losses": 0,
            "runtime_evidence_confidence": "low_cached_champion",
            "runtime_evidence_status": "insufficient",
            "runtime_evidence_pressure_count": 2,
        },
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.slot == "exploit_weak_positive"
    assert action.reason == "weak_positive_signal_followup"
    assert action.audit_metadata["runtime_evidence_clean_fork_suppression"] == (
        "weak_positive_exception"
    )
    assert action.audit_metadata["runtime_evidence_pressure_count"] == 2
    assert action.audit_metadata["case_wins"] == 1
    assert action.audit_metadata["case_losses"] == 0
    assert action.audit_metadata["runtime_evidence_pressure_triggers"] == [
        "low_or_cached_runtime_confidence",
        "runtime_evidence_status:insufficient",
    ]


def test_weak_positive_runtime_pressure_with_loss_prefers_clean_fork() -> None:
    branch = Branch(
        branch_id="weak-positive-loss-runtime-pressure",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_weak_positive",
        last_screening_feedback_tier="weak_positive",
        direction="generic weak-positive research direction",
        branch_evidence_summary={
            "wins": 1,
            "losses": 1,
            "runtime_evidence_confidence": "low_cached_champion",
            "runtime_evidence_status": "insufficient",
            "runtime_aggregate_exclusion": {"excluded": True},
            "runtime_evidence_pressure_count": 2,
        },
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "create_new"
    assert action.branch is None
    assert action.slot == "explore_new"
    assert action.reason == RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
    assert action.audit_metadata["runtime_evidence_clean_fork_selected"] is True
    assert action.audit_metadata["weak_positive_followup_suppressed"] is True
    assert action.audit_metadata["weak_positive_followup_suppression_audit"] == [
        {
            "branch_id": "weak-positive-loss-runtime-pressure",
            "lineage_status": "active_weak_positive",
            "branch_state": "explore",
            "branch_code_status": "active_weak_positive",
            "screening_tier": "weak_positive",
            "reason": RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON,
            "runtime_evidence_pressure_count": 2,
        }
    ]


def test_weak_positive_runtime_pressure_without_case_win_prefers_clean_fork() -> None:
    branch = Branch(
        branch_id="weak-positive-zero-win-runtime-pressure",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="restored_weak_positive",
        last_screening_feedback_tier="weak_positive",
        direction="generic weak-positive research direction",
        branch_evidence_summary={
            "wins": 0,
            "losses": 0,
            "runtime_evidence_confidence": "low_cached_champion",
            "runtime_evidence_status": "incomplete",
            "runtime_evidence_pressure_count": 2,
        },
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "create_new"
    assert action.branch is None
    assert action.slot == "explore_new"
    assert action.reason == RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON


def test_no_effect_branch_gets_one_same_branch_sample_before_clean_fork() -> None:
    branch = Branch(
        branch_id="no-effect-sample",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        direction="generic no-effect research direction",
        branch_mechanism_ids=("generic_probe",),
        lifecycle_no_effect_diagnostic_followups=1,
        branch_evidence_summary={
            "tier": "no_effect",
            "wins": 0,
            "losses": 0,
            "ties": 4,
        },
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.slot == "repair_diagnostic"
    assert action.reason == "same_branch_low_signal_observation_sample"
    assert action.audit_metadata["same_branch_refinement_selected"] is True
    assert action.audit_metadata["same_branch_refinement_sampling"] is True
    assert action.audit_metadata["same_branch_refinement_reason"] == (
        "no_effect_observation"
    )
    assert action.audit_metadata[
        "clean_fork_suppressed_for_same_branch_sample"
    ] is True
    assert action.audit_metadata["same_branch_refinement_sampling_candidate"][
        "lifecycle_no_effect_diagnostic_followups"
    ] == 1


def test_sampled_no_effect_branch_still_allows_clean_fork() -> None:
    branch = Branch(
        branch_id="sampled-no-effect",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        direction="generic no-effect research direction",
        branch_mechanism_ids=("generic_probe",),
        lifecycle_no_effect_diagnostic_followups=1,
        branch_evidence_summary={
            "tier": "no_effect",
            "same_branch_refinement_sampling": True,
        },
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "create_new"
    assert action.branch is None
    assert action.slot == "explore_new"
    assert action.reason in {
        "clean_fork_required_for_new_mechanism",
        "plateau_reroute_clean_fork",
    }
    assert "same_branch_refinement_sampling" not in action.audit_metadata
    assert "material_difference_required" not in action.audit_metadata


def test_repeated_no_effect_clean_fork_requires_material_difference_without_plateau_threshold() -> None:
    branch = Branch(
        branch_id="repeated-no-effect-clean-fork",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        direction="generic no-effect direction",
        branch_mechanism_ids=("generic_probe",),
        lifecycle_no_effect_diagnostic_followups=2,
        branch_evidence_summary={
            "tier": "no_effect",
            "wins": 0,
            "losses": 0,
            "ties": 4,
            "same_branch_refinement_sampling": True,
            "plateau_gate": {
                "schema_version": "plateau_gate.v1",
                "tier": "no_effect",
                "threshold_met": False,
                "effective_screened_no_effect_count": 1,
                "runtime_evidence_pressure_count": 0,
                "proposal_guidance_only": True,
                "audit_only": True,
                "decision_features_excluded": True,
            },
        },
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "create_new"
    assert action.branch is None
    assert action.slot == "explore_new"
    assert action.reason == "new_exploration_slot_available"
    assert action.audit_metadata["low_value_active_slot_release"] is True
    assert (
        action.audit_metadata["low_value_active_slot_release_candidates"][0][
            "release_reason"
        ]
        == "repeated_no_effect_zero_effect_slot_release"
    )
    assert action.audit_metadata["material_difference_required"] is True
    requirement = action.audit_metadata["material_difference_requirement"]
    assert requirement["schema_version"] == "material_difference_requirement.v1"
    assert requirement["record_type"] == "material_difference_requirement"
    assert requirement["record_id"].startswith("material_difference_requirement:")
    assert requirement["record_digest"].startswith("sha256:")
    assert requirement["proposal_visibility_only"] is True
    assert requirement["decision_features_excluded"] is True
    assert requirement["requirement_source"] == "low_value_clean_fork_pressure"
    assert requirement["candidate_branch_ids"] == [
        "repeated-no-effect-clean-fork"
    ]
    assert "LOW_VALUE_CLEAN_FORK_PRESSURE" in requirement["reason_codes"]
    assert "generic no-effect direction" not in str(requirement)


def test_retained_checkpoint_no_effect_clean_fork_requires_material_difference() -> None:
    branch = Branch(
        branch_id="retained-no-effect-clean-fork",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        direction="generic retained checkpoint direction",
        branch_mechanism_ids=("generic_retained_probe",),
        best_quality_checkpoint_id="checkpoint-best",
        last_valid_checkpoint_id="checkpoint-last",
        branch_evidence_summary={
            "tier": "no_effect",
            "wins": 0,
            "losses": 0,
            "ties": 4,
            "plateau_gate": {
                "schema_version": "plateau_gate.v1",
                "tier": "no_effect",
                "threshold_met": False,
                "effective_screened_no_effect_count": 1,
                "runtime_evidence_pressure_count": 0,
                "proposal_guidance_only": True,
                "audit_only": True,
                "decision_features_excluded": True,
            },
        },
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "create_new"
    assert action.branch is None
    assert action.slot == "explore_new"
    assert action.reason == "new_exploration_slot_available"
    assert action.audit_metadata["low_value_active_slot_release"] is True
    assert (
        action.audit_metadata["low_value_active_slot_release_candidates"][0][
            "release_reason"
        ]
        == "retained_checkpoint_no_effect_current_head"
    )
    assert action.audit_metadata["material_difference_required"] is True
    requirement = action.audit_metadata["material_difference_requirement"]
    assert requirement["schema_version"] == "material_difference_requirement.v1"
    assert requirement["record_type"] == "material_difference_requirement"
    assert requirement["record_id"].startswith("material_difference_requirement:")
    assert requirement["record_digest"].startswith("sha256:")
    assert requirement["proposal_visibility_only"] is True
    assert requirement["decision_features_excluded"] is True
    assert requirement["requirement_source"] == "low_value_clean_fork_pressure"
    assert requirement["candidate_branch_ids"] == [
        "retained-no-effect-clean-fork"
    ]
    assert action.audit_metadata["material_difference_audit_records"] == [
        requirement
    ]
    assert "LOW_VALUE_CLEAN_FORK_PRESSURE" in requirement["reason_codes"]
    assert "generic retained checkpoint direction" not in str(requirement)


def test_low_confidence_runtime_branch_gets_same_branch_sample_once() -> None:
    branch = Branch(
        branch_id="runtime-low-confidence-sample",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_marginal",
        last_screening_feedback_tier="marginal",
        direction="generic runtime-low-confidence direction",
        branch_evidence_summary={
            "tier": "marginal",
            "wins": 0,
            "losses": 0,
            "runtime_evidence_confidence": "low_cached_champion",
            "runtime_evidence_status": "insufficient",
            "runtime_evidence_pressure_count": 1,
            "runtime_evidence_pressure": {
                "triggers": [
                    "low_or_cached_runtime_confidence",
                    "runtime_evidence_status:insufficient",
                ],
            },
        },
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.reason == "same_branch_low_signal_observation_sample"
    assert action.audit_metadata["same_branch_refinement_reason"] == (
        "runtime_low_confidence_observation"
    )
    assert action.audit_metadata[
        "clean_fork_suppressed_for_same_branch_sample"
    ] is True


def test_weak_signal_reason_code_gets_same_branch_refinement_sample() -> None:
    branch = Branch(
        branch_id="weak-signal-sample",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_marginal",
        last_screening_feedback_tier="marginal",
        direction="generic weak-signal direction",
        branch_evidence_summary={
            "tier": "marginal",
            "wins": 0,
            "losses": 0,
            "reason_codes": ["SCREENING_WEAK_SIGNAL_CONTINUE"],
        },
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.reason == "same_branch_low_signal_observation_sample"
    assert action.audit_metadata["same_branch_refinement_reason"] == (
        "weak_signal_refinement_observation"
    )
    assert action.audit_metadata[
        "clean_fork_suppressed_for_same_branch_sample"
    ] is True


def test_activation_gap_branch_runs_same_branch_telemetry_diagnostic() -> None:
    branch = Branch(
        branch_id="activation-gap",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="clean",
        last_telemetry_outcome=ACTIVATION_MISSING_OR_WIRING_SUSPECT,
        branch_mechanism_ids=("generic_probe",),
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch
    assert action.slot == "repair_diagnostic"
    assert action.reason == "telemetry_diagnostic_followup"
    assert action.audit_metadata == {}


def test_same_branch_sample_does_not_preempt_pending_retry() -> None:
    retry = Branch(
        branch_id="pending-retry",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        pending_retry=True,
    )
    low_signal = Branch(
        branch_id="low-signal",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        direction="generic low-signal direction",
        lifecycle_no_effect_diagnostic_followups=1,
    )

    action = Scheduler(max_active_branches=3).select_next([low_signal, retry])

    assert action.action == "run_existing"
    assert action.branch is retry
    assert action.reason == "pending_retry_diagnostic_followup"
    assert action.audit_metadata == {}


def test_same_branch_sample_does_not_preempt_validation_priority() -> None:
    validate = Branch(
        branch_id="validate-first",
        state=BranchState.READY_VALIDATE,
        base_champion_id=1,
        base_champion_hash="champion",
    )
    low_signal = Branch(
        branch_id="low-signal",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_no_effect",
        last_screening_feedback_tier="no_effect",
        direction="generic low-signal direction",
        lifecycle_no_effect_diagnostic_followups=1,
    )

    action = Scheduler(max_active_branches=3).select_next([low_signal, validate])

    assert action.action == "run_existing"
    assert action.branch is validate
    assert action.slot == "refine_active"
    assert action.reason == "active_branch_refinement"
    assert action.audit_metadata == {}


def test_fresh_required_runtime_pressure_is_explained_in_scheduler_audit() -> None:
    branch = Branch(
        branch_id="fresh-required-runtime-pressure",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_marginal",
        last_screening_feedback_tier="marginal",
        direction="generic runtime evidence pressure direction",
        branch_evidence_summary={
            "wins": 0,
            "losses": 0,
            "runtime_evidence_confidence": "unknown",
            "runtime_evidence_status": "fresh_required",
            "runtime_evidence_pressure_count": 2,
            "runtime_evidence_pressure": {
                "triggers": ["runtime_evidence_status:fresh_required"],
                "count": 2,
                "proposal_guidance_only": True,
                "decision_features_excluded": True,
            },
        },
    )

    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.action == "create_new"
    assert action.reason == RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
    assert action.audit_metadata["runtime_evidence_clean_fork_candidates"][0][
        "runtime_evidence_pressure_triggers"
    ] == ["runtime_evidence_status:fresh_required"]
