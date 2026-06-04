from __future__ import annotations

from scion.core.branch_lifecycle_policy import (
    SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE,
)
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
    RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON,
    Scheduler,
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


def test_repeated_runtime_evidence_pressure_prefers_clean_fork_over_refine() -> None:
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

    assert branch.branch_evidence_summary["runtime_evidence_pressure_count"] == 2
    assert first.action == "run_existing"
    assert first.branch is branch
    assert first.slot == "refine_active"
    assert second.action == "create_new"
    assert second.branch is None
    assert second.slot == "explore_new"
    assert second.reason == RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
    assert second.audit_metadata["runtime_evidence_clean_fork_selected"] is True
    assert (
        second.audit_metadata["runtime_evidence_clean_fork_reason"]
        == RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
    )
    assert second.audit_metadata["runtime_evidence_pressure_count_max"] == 2
    assert second.audit_metadata["runtime_evidence_clean_fork_candidates"] == [
        {
            "branch_id": "runtime-pressure",
            "lineage_status": "active_marginal",
            "runtime_evidence_pressure_count": 2,
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
