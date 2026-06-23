from __future__ import annotations

from scion.core.branch_lifecycle_policy import (
    SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE,
)
from scion.core.branch_cards import branch_hygiene_context, branch_prompt_card
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
from scion.core.scheduling.runtime_pressure import (
    branch_runtime_evidence_clean_fork_pressure_summary,
)
from scion.core.scheduling.signals import branch_runtime_evidence_pressure_preferred
from scion.proposal.screening_feedback import screening_feedback_summary


def _budget_exhausting_runtime_pressure_protocol() -> ProtocolResult:
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
        candidate_surface_runtime_summary={
            "runtime_model": "budget_exhausting",
            "runtime_budget_diagnostic": {
                "schema": "scion.runtime_budget_diagnostic.v1",
                "runtime_model": "budget_exhausting",
            },
        },
        runtime_confidence="low_cached_champion",
        runtime_evidence_status="insufficient",
        champion_cached_runtime_pairs=4,
    )


def test_budget_exhausting_runtime_evidence_does_not_accumulate_pressure() -> None:
    branch = Branch(
        branch_id="budget-exhausting-runtime-pressure",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_marginal",
        last_screening_feedback_tier="marginal",
    )
    protocol = _budget_exhausting_runtime_pressure_protocol()
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
    update_branch_screening_evidence_summary(
        branch,
        protocol_result=protocol,
        screening_feedback=feedback,
        decision_reason_codes=(SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE,),
    )

    summary = branch.branch_evidence_summary
    assert summary["runtime_model"] == "budget_exhausting"
    assert summary["runtime_evidence_confidence"] == "low_cached_champion"
    assert summary["runtime_evidence_status"] == "insufficient"
    assert summary["runtime_cache"]["champion_cached_runtime_pairs"] == 4
    assert summary["runtime_aggregate_exclusion"]["excluded"] is True
    assert summary["runtime_evidence_pressure_count"] == 0
    assert "runtime_evidence_pressure" not in summary

    policy = summary["runtime_evidence_policy"]
    assert policy["runtime_model"] == "budget_exhausting"
    assert policy["runtime_model_interpretation"] == (
        "budget_exhausting_runtime_aggregates_observational_not_standalone"
    )
    assert policy["fresh_champion_required"] is False
    assert "RUNTIME_BUDGET_EXHAUSTING_OBSERVATIONAL" in (
        policy["policy_reason_codes"]
    )


def test_budget_exhausting_legacy_pressure_count_does_not_create_clean_fork() -> None:
    branch = Branch(
        branch_id="budget-exhausting-stale-pressure",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_marginal",
        last_screening_feedback_tier="marginal",
        direction="generic runtime evidence pressure direction",
        branch_evidence_summary={
            "wins": 0,
            "losses": 1,
            "runtime_model": "budget_exhausting",
            "runtime_evidence_confidence": "low_cached_champion",
            "runtime_evidence_status": "insufficient",
            "runtime_aggregate_exclusion": {"excluded": True},
            "runtime_evidence_pressure_count": 2,
            "runtime_evidence_pressure": {
                "triggers": [
                    "low_or_cached_runtime_confidence",
                    "runtime_evidence_status:insufficient",
                    "runtime_aggregate_excluded",
                ],
                "count": 2,
                "proposal_guidance_only": True,
                "decision_features_excluded": True,
            },
        },
    )

    assert branch_runtime_evidence_clean_fork_pressure_summary(branch) == {}
    assert branch_runtime_evidence_pressure_preferred(branch) is False
    action = Scheduler(max_active_branches=2).select_next([branch])

    assert action.reason != RUNTIME_EVIDENCE_COMPLETENESS_CLEAN_FORK_REASON
    assert action.action != "create_new"
    assert "runtime_evidence_clean_fork_selected" not in action.audit_metadata


def test_budget_exhausting_branch_card_hides_numeric_runtime_regression() -> None:
    branch = Branch(
        branch_id="budget-exhausting-card",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_marginal",
        last_screening_feedback_tier="marginal",
        branch_evidence_summary={
            "tier": "marginal",
            "wins": 0,
            "losses": 0,
            "ties": 4,
            "runtime_model": "budget_exhausting",
            "runtime_ratio_median": 1.0,
            "runtime_delta_median_ms": 0.0,
            "runtime_regression_rate": 1.0,
            "runtime_pairs": 0,
            "runtime_evidence_policy": {
                "runtime_model": "budget_exhausting",
                "runtime_model_interpretation": (
                    "budget_exhausting_runtime_aggregates_observational_not_standalone"
                ),
            },
        },
    )

    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)
    runtime = payload["generic_evidence_summary"]["runtime"]

    assert "runtime_regression_rate" not in runtime
    assert runtime["runtime_model"] == "budget_exhausting"
    assert (
        runtime["runtime_regression_rate_interpretation"]
        == "not_applicable_budget_exhausting"
    )
    assert "runtime_regression_rate:1" not in text
    assert "runtime_regression_rate=1" not in text


def test_budget_exhausting_branch_card_suppresses_stale_fresh_runtime_followup() -> None:
    branch = Branch(
        branch_id="budget-exhausting-stale-fresh-runtime",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="champion",
        branch_code_status="active_marginal",
        last_screening_feedback_tier="marginal",
        branch_evidence_summary={
            "tier": "marginal",
            "runtime_model": "budget_exhausting",
            "runtime_evidence_status": "fresh_champion_required",
            "fresh_runtime_required": True,
            "fresh_runtime_pending": True,
            "reason_codes": ["RUNTIME_TIE_FRESH_CHAMPION_REQUIRED"],
            "fresh_runtime_followup": {
                "schema_version": "fresh_runtime_followup.v1",
                "queue_intent": "fresh_champion_runtime_replay",
                "trigger": "fresh_runtime_required",
                "fresh_runtime_pending": True,
                "fresh_runtime_required": True,
            },
        },
    )

    payload = branch_hygiene_context(branch)
    text = branch_prompt_card(branch)

    assert payload["fresh_runtime_pending"] is False
    assert payload["fresh_runtime_required"] is False
    assert payload["fresh_runtime_followup"] == {}
    assert "fresh_runtime_pending" not in payload["generic_evidence_summary"]
    assert "fresh_runtime_required" not in payload["generic_evidence_summary"]
    assert "fresh_runtime_followup=" not in text
    assert "fresh_runtime_pending=true" not in text
