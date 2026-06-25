from __future__ import annotations

from typing import Any

from scion.postrun import ProblemPostrunReviewContext
from scion.problems.warehouse_delivery.postrun_review import (
    WAREHOUSE_FOLLOWUP_REQUIREMENT_KEYS,
    WarehouseFollowupReviewPort,
    WarehousePostrunSummaryProvider,
)
from scion.problems.warehouse_delivery.research_guidance import (
    WAREHOUSE_PROBLEM_FAMILY,
)


def test_warehouse_postrun_provider_keeps_legacy_summary_shape_problem_owned() -> None:
    summary = _build_warehouse_followup_summary()

    assert summary["schema_version"] == "scion.postrun_warehouse_followup_summary.v1"
    assert summary["report_only"] is True
    assert summary["quality_judgment"] is False
    assert summary["decision_features_excluded"] is True
    assert summary["available"] is True
    assert summary["problem_family"] == WAREHOUSE_PROBLEM_FAMILY
    assert summary["current_run_evidence"] is True
    assert summary["handoff_complete"] is True
    assert summary["interpretation"] == "protocol_evaluated_plateau_review_ready"
    assert summary["evidence_gaps"] == []
    assert summary["review_axes_actionability"] == (
        "actionable_current_run_evidence_present"
    )
    assert summary["evidence"]["protocol"]["protocol_evaluated_candidates"] == 1
    assert summary["evidence"]["measurement_effect"]["plateau_consistent"] is True


def test_warehouse_postrun_review_port_uses_existing_summary() -> None:
    summary = _build_warehouse_followup_summary()
    review = WarehouseFollowupReviewPort().review(
        {"analysis_brief": {"warehouse_followup_summary": summary}}
    )

    assert review.problem_family == WAREHOUSE_PROBLEM_FAMILY
    assert review.review_key == "warehouse_followup_summary"
    assert review.ready is True
    assert review.failed_required_checks == ()
    assert review.decision_features_excluded is True
    assert review.proposal_visibility_only is True


def test_warehouse_postrun_review_port_fails_required_review_input_gaps() -> None:
    summary = _build_warehouse_followup_summary()
    stale_summary = {
        **summary,
        "evidence_gaps": ["missing_runtime_feedback_summary"],
    }

    review = WarehouseFollowupReviewPort().review(
        {"analysis_brief": {"warehouse_followup_summary": stale_summary}}
    )

    assert review.ready is False
    assert review.failed_required_checks == ("missing_runtime_feedback_summary",)


def test_warehouse_postrun_provider_returns_not_applicable_for_other_problem() -> None:
    context = _context(
        inventory={
            "phase4_evidence_coverage": {"current_run_evidence": True},
            "launcher": {"prepared_run_contract": {"problem_family": "cvrp"}},
        }
    )

    summaries = WarehousePostrunSummaryProvider().build_summaries(context)
    summary = summaries["warehouse_followup_summary"]

    assert summary["available"] is False
    assert summary["interpretation"] == "not_warehouse_delivery"
    assert summary["quality_judgment"] is False
    assert summary["decision_features_excluded"] is True


def _build_warehouse_followup_summary() -> dict[str, Any]:
    summaries = WarehousePostrunSummaryProvider().build_summaries(_context())
    return dict(summaries["warehouse_followup_summary"])


def _context(
    *,
    inventory: dict[str, Any] | None = None,
) -> ProblemPostrunReviewContext:
    return ProblemPostrunReviewContext(
        inventory=inventory or _inventory(),
        protocol_accounting_summary={
            "aggregate": {
                "protocol_rows": {
                    "protocol_evaluated_candidates": 1,
                    "protocol_metric_results": 1,
                },
                "formal_candidate_artifacts": {"row_count": 1},
                "formal_screened_candidates": 1,
                "stage_rows": {"screening": 1},
            }
        },
        measurement_effect_summary={
            "available": True,
            "aggregate": {
                "protocol_row_count": 1,
                "rows_at_or_above_mde": 0,
                "rows_with_ci_high_below_mde": 1,
                "max_effect_to_mde_ratio": 0.0,
                "interpretation_counts": {"below_mde": 1},
            },
        },
        runtime_feedback_summary={
            "available": True,
            "drain_status_complete": True,
            "aggregate": {
                "fresh_runtime_replay_drain": {
                    "status_counts": {"executed": 1},
                    "attempts": 1,
                    "executed": 1,
                    "protocol_results": 1,
                },
                "stage_transition_drain": {"status_counts": {"executed": 1}},
                "runtime_budget_diagnostics": {
                    "runtime_model_counts": {"fast_complete": 1},
                    "diagnostic_count": 1,
                },
            },
        },
        failure_taxonomy_summary={
            "aggregate": {
                "proposal_quality": {
                    "proposal_quality_blocks": 0,
                    "quality_blocks": 0,
                    "quality_block_ledger_count": 0,
                    "reports_with_quality_blocks": 0,
                    "quality_block_reason_counts": {},
                }
            }
        },
        research_continuity_summary={
            "available": True,
            "continuity_report_count": 1,
            "aggregate": {
                "max_branch_depth": 2,
                "mechanism_family_counts": {"warehouse_operator": 1},
                "active_shape_counts": {"modify_existing": 1},
            },
            "entries": [],
        },
    )


def _inventory() -> dict[str, Any]:
    return {
        "phase4_evidence_coverage": {
            "current_run_evidence": True,
            "invalid_infra_only": False,
            "problem_specific_requirements": {
                key: {"available": True, "count": 1, "source": "fixture"}
                for key in WAREHOUSE_FOLLOWUP_REQUIREMENT_KEYS
            },
        },
        "launcher": {
            "prepared_run_contract": {
                "problem_family": WAREHOUSE_PROBLEM_FAMILY,
            }
        },
        "counters": {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
        },
    }
