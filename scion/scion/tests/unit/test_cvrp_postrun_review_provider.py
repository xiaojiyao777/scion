from __future__ import annotations

from typing import Any

from scion.postrun import ProblemPostrunReviewContext
from scion.problems.cvrp.large_twoopt_review import (
    CVRP_LARGE_TWOOPT_REQUIREMENT_KEYS,
)
from scion.problems.cvrp.postrun_review import (
    CvrpLargeTwoOptReviewPort,
    CvrpPostrunSummaryProvider,
)
from scion.problems.cvrp.research_guidance import CVRP_PROBLEM_FAMILY


def test_cvrp_postrun_provider_keeps_legacy_summary_shape_problem_owned() -> None:
    summary = _build_cvrp_large_twoopt_summary()

    assert summary["schema_version"] == "scion.postrun_cvrp_large_twoopt_summary.v1"
    assert summary["report_only"] is True
    assert summary["quality_judgment"] is False
    assert summary["decision_features_excluded"] is True
    assert summary["available"] is True
    assert summary["problem_family"] == CVRP_PROBLEM_FAMILY
    assert summary["current_run_evidence"] is True
    assert summary["handoff_complete"] is True
    assert summary["interpretation"] == "protocol_evaluated_without_large_twoopt_signal"
    assert "missing_large_twoopt_mechanism_signal" in summary["evidence_gaps"]
    assert summary["review_axes_actionability"] == (
        "actionable_current_run_evidence_present"
    )
    assert summary["evidence"]["protocol"]["protocol_evaluated_candidates"] == 1


def test_cvrp_postrun_review_port_uses_existing_summary_without_raw_prompt_parse() -> None:
    summary = _build_cvrp_large_twoopt_summary()
    review = CvrpLargeTwoOptReviewPort().review(
        {"analysis_brief": {"cvrp_large_twoopt_summary": summary}}
    )

    assert review.problem_family == CVRP_PROBLEM_FAMILY
    assert review.review_key == "cvrp_large_twoopt_summary"
    assert review.ready is True
    assert review.failed_required_checks == ()
    assert review.decision_features_excluded is True
    assert review.proposal_visibility_only is True


def test_cvrp_postrun_review_port_fails_required_review_input_gaps() -> None:
    summary = _build_cvrp_large_twoopt_summary()
    stale_summary = {
        **summary,
        "evidence_gaps": ["missing_measurement_effect_summary"],
    }

    review = CvrpLargeTwoOptReviewPort().review(
        {"analysis_brief": {"cvrp_large_twoopt_summary": stale_summary}}
    )

    assert review.ready is False
    assert review.failed_required_checks == ("missing_measurement_effect_summary",)


def test_cvrp_postrun_provider_returns_not_applicable_for_other_problem() -> None:
    context = _context(
        inventory={
            "phase4_evidence_coverage": {"current_run_evidence": True},
            "launcher": {
                "prepared_run_contract": {"problem_family": "warehouse_delivery"}
            },
        }
    )

    summaries = CvrpPostrunSummaryProvider().build_summaries(context)
    summary = summaries["cvrp_large_twoopt_summary"]

    assert summary["available"] is False
    assert summary["interpretation"] == "not_cvrp"
    assert summary["quality_judgment"] is False
    assert summary["decision_features_excluded"] is True


def _build_cvrp_large_twoopt_summary() -> dict[str, Any]:
    summaries = CvrpPostrunSummaryProvider().build_summaries(_context())
    return dict(summaries["cvrp_large_twoopt_summary"])


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
                "mechanism_family_mapped_row_count": 0,
                "mechanism_family_unmapped_row_count": 1,
                "mechanism_family_effects": {},
            },
        },
        runtime_feedback_summary={
            "available": True,
            "drain_status_complete": True,
            "aggregate": {
                "runtime_budget_diagnostics": {
                    "runtime_model_counts": {"budget_exhausting": 1},
                    "diagnostic_count": 1,
                }
            },
        },
        failure_taxonomy_summary={
            "aggregate": {
                "proposal_quality": {
                    "proposal_quality_blocks": 0,
                    "quality_blocks": 0,
                    "quality_block_ledger_count": 0,
                    "quality_block_reason_counts": {},
                }
            }
        },
        research_continuity_summary={
            "available": True,
            "continuity_report_count": 1,
            "aggregate": {"entries": []},
        },
    )


def _inventory() -> dict[str, Any]:
    return {
        "phase4_evidence_coverage": {
            "current_run_evidence": True,
            "invalid_infra_only": False,
            "problem_specific_requirements": {
                key: {"available": True, "count": 1, "source": "fixture"}
                for key in CVRP_LARGE_TWOOPT_REQUIREMENT_KEYS
            },
        },
        "launcher": {
            "prepared_run_contract": {
                "problem_family": CVRP_PROBLEM_FAMILY,
            }
        },
        "counters": {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
        },
    }
