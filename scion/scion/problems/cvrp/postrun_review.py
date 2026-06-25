"""CVRP-owned postrun summary providers."""

from __future__ import annotations

from typing import Any, Mapping

from scion.postrun import (
    ProblemPostrunReviewContext,
    ProblemReviewSummary,
    ProblemSummaryActionabilitySpec,
    problem_summary_common_input_consistency_detail,
)
from scion.problems.cvrp.large_twoopt_review import (
    CVRP_LARGE_TWOOPT_REVIEW_AXES,
    cvrp_large_twoopt_evidence_gaps,
    cvrp_large_twoopt_handoff_requirements,
    cvrp_large_twoopt_interpretation,
    cvrp_large_twoopt_mechanism_signal,
    problem_research_continuity_signal,
)
from scion.problems.cvrp.research_guidance import CVRP_PROBLEM_FAMILY


_BLOCKING_CVRP_LARGE_TWOOPT_GAPS = frozenset(
    {
        "cvrp_large_twoopt_handoff_requirements_incomplete",
        "invalid_infra_only_no_research_conclusion",
        "launch_required_before_bounded_twoopt_conclusion",
        "missing_measurement_effect_summary",
        "missing_research_continuity_summary",
        "missing_runtime_feedback_summary",
        "no_protocol_evaluated_candidates",
    }
)

CVRP_LARGE_TWOOPT_ACTIONABILITY_SPEC = ProblemSummaryActionabilitySpec(
    summary_key="cvrp_large_twoopt_summary",
    problem_family=CVRP_PROBLEM_FAMILY,
    schema_version="scion.postrun_cvrp_large_twoopt_summary.v1",
    delegated_interpretations=frozenset(
        {
            "bounded_twoopt_review_ready",
            "quality_blocked_no_protocol_twoopt_conclusion",
            "protocol_evaluated_without_large_twoopt_direct_evidence",
            "protocol_evaluated_without_large_twoopt_signal",
        }
    ),
    blocking_evidence_gaps=_BLOCKING_CVRP_LARGE_TWOOPT_GAPS,
    launch_required_field="launch_required_before_twoopt_conclusion",
    nonblocking_gaps_by_interpretation={
        "quality_blocked_no_protocol_twoopt_conclusion": frozenset(
            {
                "missing_measurement_effect_summary",
                "missing_research_continuity_summary",
                "missing_runtime_feedback_summary",
            }
        )
    },
)


class CvrpPostrunSummaryProvider:
    """Build legacy-compatible CVRP analysis-brief summaries."""

    problem_family = CVRP_PROBLEM_FAMILY

    def build_summaries(
        self,
        context: ProblemPostrunReviewContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        return {
            "cvrp_large_twoopt_summary": cvrp_large_twoopt_summary(
                context.inventory,
                protocol_accounting_summary=context.protocol_accounting_summary,
                measurement_effect_summary=context.measurement_effect_summary,
                runtime_feedback_summary=context.runtime_feedback_summary,
                failure_taxonomy_summary=context.failure_taxonomy_summary,
                research_continuity_summary=context.research_continuity_summary,
            )
        }


class CvrpLargeTwoOptReviewPort:
    """Problem-owned readiness adapter for the CVRP large-twoopt summary."""

    problem_family = CVRP_PROBLEM_FAMILY
    review_key = "cvrp_large_twoopt_summary"

    def review(self, inventory: Mapping[str, Any]) -> ProblemReviewSummary:
        summary = _summary_from_inventory(inventory, self.review_key)
        if not summary:
            return ProblemReviewSummary(
                problem_family=self.problem_family,
                review_key=self.review_key,
                status="missing",
                interpretation="missing_cvrp_large_twoopt_summary",
                ready=False,
                failed_required_checks=("missing_cvrp_large_twoopt_summary",),
                detail={"summary_available": False},
            )
        gaps = _string_items(summary.get("evidence_gaps"))
        failed = tuple(
            gap for gap in gaps if gap in _BLOCKING_CVRP_LARGE_TWOOPT_GAPS
        )
        ready = summary.get("available") is True and not failed
        return ProblemReviewSummary(
            problem_family=self.problem_family,
            review_key=self.review_key,
            status="ready" if ready else "not_ready",
            interpretation=str(summary.get("interpretation") or ""),
            ready=ready,
            failed_required_checks=failed,
            detail={
                "summary_schema_version": summary.get("schema_version"),
                "current_run_evidence": summary.get("current_run_evidence"),
                "evidence_gaps": gaps,
                "review_axes_actionability": summary.get(
                    "review_axes_actionability"
                ),
            },
        )


def cvrp_large_twoopt_summary(
    inventory: Mapping[str, Any],
    *,
    protocol_accounting_summary: Mapping[str, Any],
    measurement_effect_summary: Mapping[str, Any],
    runtime_feedback_summary: Mapping[str, Any],
    failure_taxonomy_summary: Mapping[str, Any],
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
    launcher = _mapping_or_empty(inventory.get("launcher"))
    contract = _mapping_or_empty(launcher.get("prepared_run_contract"))
    problem_family = contract.get("problem_family")
    current_run_evidence = phase4.get("current_run_evidence") is True
    invalid_infra_only = phase4.get("invalid_infra_only") is True
    base = {
        "schema_version": "scion.postrun_cvrp_large_twoopt_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "problem_family": problem_family,
        "current_run_evidence": current_run_evidence,
        "invalid_infra_only": invalid_infra_only,
        "available": False,
        "handoff_complete": False,
        "handoff_requirements": {},
        "launch_required_before_twoopt_conclusion": False,
        "interpretation": "not_cvrp",
        "evidence": {},
        "evidence_gaps": [],
        "required_review_axes": list(CVRP_LARGE_TWOOPT_REVIEW_AXES),
        "deferred_review_axes": [],
        "review_axes_actionability": "not_applicable",
    }
    if problem_family != CVRP_PROBLEM_FAMILY:
        return base

    handoff_requirements = cvrp_large_twoopt_handoff_requirements(
        phase4=phase4,
        contract=contract,
    )
    handoff_complete = bool(handoff_requirements) and all(
        item.get("available") is True for item in handoff_requirements.values()
    )
    counters = _mapping_or_empty(inventory.get("counters"))
    accounting = _mapping_or_empty(protocol_accounting_summary.get("aggregate"))
    protocol_rows = _mapping_or_empty(accounting.get("protocol_rows"))
    formal_artifacts = _mapping_or_empty(
        accounting.get("formal_candidate_artifacts")
    )
    formal_screened_candidates = max(
        _int_or_zero(accounting.get("formal_screened_candidates")),
        _int_or_zero(counters.get("formal_screened_candidates")),
        _int_or_zero(counters.get("screened_experiments")),
    )
    protocol_evaluated_candidates = max(
        _int_or_zero(protocol_rows.get("protocol_evaluated_candidates")),
        _int_or_zero(accounting.get("formal_protocol_evaluated_candidates")),
        _int_or_zero(counters.get("protocol_evaluated_candidates")),
    )
    measurement = _mapping_or_empty(measurement_effect_summary.get("aggregate"))
    runtime = _mapping_or_empty(runtime_feedback_summary.get("aggregate"))
    runtime_budget = _mapping_or_empty(runtime.get("runtime_budget_diagnostics"))
    failure = _mapping_or_empty(failure_taxonomy_summary.get("aggregate"))
    proposal_quality = _mapping_or_empty(failure.get("proposal_quality"))
    quality_block_signal = max(
        _int_or_zero(proposal_quality.get("proposal_quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_block_ledger_count")),
    )
    large_twoopt_mechanism = cvrp_large_twoopt_mechanism_signal(
        measurement_effect_summary=measurement_effect_summary,
        research_continuity_summary=research_continuity_summary,
    )
    continuity_signal = problem_research_continuity_signal(
        research_continuity_summary
    )
    measurement_available = measurement_effect_summary.get("available") is True
    runtime_available = _runtime_feedback_review_ready(runtime_feedback_summary)
    continuity_available = research_continuity_summary.get("available") is True
    large_twoopt_available = large_twoopt_mechanism.get("available") is True
    large_twoopt_family_available = (
        large_twoopt_mechanism.get("mechanism_family_available") is True
    )
    large_twoopt_direct_evidence_ready = (
        large_twoopt_mechanism.get("direct_evidence_ready") is True
    )
    evidence = {
        "protocol": {
            "formal_screened_candidates": formal_screened_candidates,
            "protocol_evaluated_candidates": protocol_evaluated_candidates,
            "protocol_metric_results": _int_or_zero(
                protocol_rows.get("protocol_metric_results")
            ),
            "formal_candidate_artifact_rows": _int_or_zero(
                formal_artifacts.get("row_count")
            ),
            "stage_rows": _mapping_or_empty(accounting.get("stage_rows")),
        },
        "measurement_effect": {
            "available": measurement_available,
            "protocol_row_count": _int_or_zero(
                measurement.get("protocol_row_count")
            ),
            "rows_at_or_above_mde": _int_or_zero(
                measurement.get("rows_at_or_above_mde")
            ),
            "rows_with_ci_high_below_mde": _int_or_zero(
                measurement.get("rows_with_ci_high_below_mde")
            ),
            "max_effect_to_mde_ratio": measurement.get("max_effect_to_mde_ratio"),
            "interpretation_counts": _int_mapping(
                measurement.get("interpretation_counts")
            ),
            "mechanism_family_mapped_row_count": _int_or_zero(
                measurement.get("mechanism_family_mapped_row_count")
            ),
            "mechanism_family_unmapped_row_count": _int_or_zero(
                measurement.get("mechanism_family_unmapped_row_count")
            ),
        },
        "large_twoopt_mechanism": large_twoopt_mechanism,
        "quality_blocks": {
            "proposal_quality_blocks": _int_or_zero(
                proposal_quality.get("proposal_quality_blocks")
            ),
            "quality_blocks": _int_or_zero(proposal_quality.get("quality_blocks")),
            "quality_block_ledger_count": _int_or_zero(
                proposal_quality.get("quality_block_ledger_count")
            ),
            "reason_counts": _int_mapping(
                proposal_quality.get("quality_block_reason_counts")
            ),
        },
        "runtime": {
            "available": runtime_available,
            "raw_available": runtime_feedback_summary.get("available") is True,
            "drain_status_complete": runtime_feedback_summary.get(
                "drain_status_complete"
            )
            is True,
            "runtime_model_counts": _int_mapping(
                runtime_budget.get("runtime_model_counts")
            ),
            "runtime_budget_diagnostic_count": _int_or_zero(
                runtime_budget.get("diagnostic_count")
            ),
        },
        "research_continuity": {
            "available": continuity_available,
            "continuity_report_count": _int_or_zero(
                research_continuity_summary.get("continuity_report_count")
            ),
            **continuity_signal,
        },
    }
    interpretation = cvrp_large_twoopt_interpretation(
        current_run_evidence=current_run_evidence,
        invalid_infra_only=invalid_infra_only,
        handoff_complete=handoff_complete,
        protocol_evaluated_candidates=protocol_evaluated_candidates,
        formal_screened_candidates=formal_screened_candidates,
        quality_block_signal=quality_block_signal,
        measurement_available=measurement_available,
        runtime_available=runtime_available,
        continuity_available=continuity_available,
        large_twoopt_available=large_twoopt_available,
        large_twoopt_family_available=large_twoopt_family_available,
        large_twoopt_direct_evidence_ready=large_twoopt_direct_evidence_ready,
    )
    return {
        **base,
        "available": True,
        "handoff_complete": handoff_complete,
        "handoff_requirements": handoff_requirements,
        "launch_required_before_twoopt_conclusion": not current_run_evidence,
        "interpretation": interpretation,
        "evidence": evidence,
        "evidence_gaps": cvrp_large_twoopt_evidence_gaps(
            current_run_evidence=current_run_evidence,
            invalid_infra_only=invalid_infra_only,
            handoff_complete=handoff_complete,
            protocol_evaluated_candidates=protocol_evaluated_candidates,
            quality_block_signal=quality_block_signal,
            measurement_available=measurement_available,
            runtime_available=runtime_available,
            continuity_available=continuity_available,
            large_twoopt_available=large_twoopt_available,
            large_twoopt_family_available=large_twoopt_family_available,
            large_twoopt_direct_evidence_ready=large_twoopt_direct_evidence_ready,
        ),
        "deferred_review_axes": (
            list(CVRP_LARGE_TWOOPT_REVIEW_AXES)
            if not current_run_evidence
            else []
        ),
        "review_axes_actionability": _review_axes_actionability(
            current_run_evidence=current_run_evidence,
            invalid_infra_only=invalid_infra_only,
        ),
    }


def cvrp_large_twoopt_input_consistency(
    inventory: Mapping[str, Any],
    *,
    summary: Mapping[str, Any],
    protocol_accounting_summary: Mapping[str, Any],
    measurement_effect_summary: Mapping[str, Any],
    runtime_feedback_summary: Mapping[str, Any],
    failure_taxonomy_summary: Mapping[str, Any],
    research_continuity_summary: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    expected_summary = cvrp_large_twoopt_summary(
        inventory,
        protocol_accounting_summary=protocol_accounting_summary,
        measurement_effect_summary=measurement_effect_summary,
        runtime_feedback_summary=runtime_feedback_summary,
        failure_taxonomy_summary=failure_taxonomy_summary,
        research_continuity_summary=research_continuity_summary,
    )
    detail = problem_summary_common_input_consistency_detail(
        problem_family=CVRP_PROBLEM_FAMILY,
        summary_key=CVRP_LARGE_TWOOPT_ACTIONABILITY_SPEC.summary_key,
        summary=summary,
        expected_problem_summary=expected_summary,
        inventory=inventory,
        protocol_accounting_summary=protocol_accounting_summary,
        measurement_effect_summary=measurement_effect_summary,
        runtime_feedback_summary=runtime_feedback_summary,
        failure_taxonomy_summary=failure_taxonomy_summary,
        research_continuity_summary=research_continuity_summary,
    )
    failures = detail["failures"]
    evidence = _mapping_or_empty(summary.get("evidence"))
    measurement_evidence = _mapping_or_empty(evidence.get("measurement_effect"))
    large_twoopt_evidence = _mapping_or_empty(evidence.get("large_twoopt_mechanism"))
    continuity_evidence = _mapping_or_empty(evidence.get("research_continuity"))
    interpretation = str(summary.get("interpretation") or "")
    measurement_aggregate = _mapping_or_empty(
        _mapping_or_empty(measurement_effect_summary).get("aggregate")
    )
    large_twoopt_signal = cvrp_large_twoopt_mechanism_signal(
        measurement_effect_summary=measurement_effect_summary,
        research_continuity_summary=research_continuity_summary,
    )
    continuity_signal = problem_research_continuity_signal(research_continuity_summary)
    continuity_fields = (
        "substantive",
        "max_branch_depth",
        "same_mechanism_selected",
        "same_mechanism_observed",
        "same_mechanism_missed",
        "branch_lessons_required",
        "branch_lessons_satisfied",
        "weak_positive_observed",
        "weak_positive_accepted",
    )
    continuity_present = (
        continuity_evidence.get("available") is True
        or _mapping_or_empty(research_continuity_summary).get("available") is True
        or any(field in continuity_evidence for field in continuity_fields)
    )
    if continuity_present:
        for field in continuity_fields:
            summary_value = continuity_evidence.get(field)
            input_value = continuity_signal.get(field)
            if isinstance(input_value, bool):
                if summary_value is not input_value:
                    failures.append(f"problem_summary_cvrp_continuity_{field}_mismatch")
            elif _int_or_zero(summary_value) != _int_or_zero(input_value):
                failures.append(f"problem_summary_cvrp_continuity_{field}_mismatch")
    if large_twoopt_evidence:
        for field in (
            "available",
            "mechanism_family_available",
            "direct_evidence_ready",
        ):
            if large_twoopt_evidence.get(field) is not large_twoopt_signal.get(field):
                failures.append(f"problem_summary_large_twoopt_{field}_mismatch")
        if _int_or_zero(large_twoopt_evidence.get("protocol_row_count")) != (
            _int_or_zero(large_twoopt_signal.get("protocol_row_count"))
        ):
            failures.append("problem_summary_large_twoopt_protocol_rows_mismatch")
        if interpretation == "bounded_twoopt_review_ready":
            for field in (
                "mechanism_family_mapped_row_count",
                "mechanism_family_unmapped_row_count",
            ):
                if _int_or_zero(measurement_evidence.get(field)) != _int_or_zero(
                    measurement_aggregate.get(field)
                ):
                    failures.append(f"problem_summary_measurement_{field}_mismatch")
            if _large_twoopt_direct_evidence_signature(
                large_twoopt_evidence.get("direct_evidence")
            ) != _large_twoopt_direct_evidence_signature(
                large_twoopt_signal.get("direct_evidence")
            ):
                failures.append("problem_summary_large_twoopt_direct_evidence_mismatch")
            for field in (
                "families",
                "protocol_families",
                "continuity_families",
                "rejected_protocol_families",
                "rejected_continuity_families",
            ):
                if _string_items(large_twoopt_evidence.get(field)) != _string_items(
                    large_twoopt_signal.get(field)
                ):
                    failures.append(f"problem_summary_large_twoopt_{field}_mismatch")
            if _int_mapping(large_twoopt_evidence.get("rejection_reason_counts")) != (
                _int_mapping(large_twoopt_signal.get("rejection_reason_counts"))
            ):
                failures.append(
                    "problem_summary_large_twoopt_rejection_reason_counts_mismatch"
                )
            if _int_or_zero(large_twoopt_evidence.get("top_row_signal_count")) != (
                _int_or_zero(large_twoopt_signal.get("top_row_signal_count"))
            ):
                failures.append(
                    "problem_summary_large_twoopt_top_row_signal_count_mismatch"
                )
    if interpretation == "bounded_twoopt_review_ready":
        if large_twoopt_evidence.get("available") is not True:
            failures.append("problem_summary_large_twoopt_available_missing")
        if large_twoopt_signal.get("available") is not True:
            failures.append("review_input_large_twoopt_direct_evidence_missing")

    detail.update(
        {
            "summary_cvrp_continuity_substantive": continuity_evidence.get(
                "substantive"
            ),
            "input_cvrp_continuity_substantive": continuity_signal.get(
                "substantive"
            ),
            "summary_cvrp_continuity_max_branch_depth": continuity_evidence.get(
                "max_branch_depth"
            ),
            "input_cvrp_continuity_max_branch_depth": continuity_signal.get(
                "max_branch_depth"
            ),
            "summary_cvrp_continuity_same_mechanism_selected": (
                continuity_evidence.get("same_mechanism_selected")
            ),
            "input_cvrp_continuity_same_mechanism_selected": (
                continuity_signal.get("same_mechanism_selected")
            ),
            "summary_cvrp_continuity_same_mechanism_missed": (
                continuity_evidence.get("same_mechanism_missed")
            ),
            "input_cvrp_continuity_same_mechanism_missed": (
                continuity_signal.get("same_mechanism_missed")
            ),
            "summary_cvrp_continuity_branch_lessons_satisfied": (
                continuity_evidence.get("branch_lessons_satisfied")
            ),
            "input_cvrp_continuity_branch_lessons_satisfied": (
                continuity_signal.get("branch_lessons_satisfied")
            ),
            "summary_cvrp_continuity_weak_positive_accepted": (
                continuity_evidence.get("weak_positive_accepted")
            ),
            "input_cvrp_continuity_weak_positive_accepted": (
                continuity_signal.get("weak_positive_accepted")
            ),
            "summary_large_twoopt_available": large_twoopt_evidence.get("available"),
            "input_large_twoopt_available": large_twoopt_signal.get("available"),
            "summary_large_twoopt_mechanism_family_available": (
                large_twoopt_evidence.get("mechanism_family_available")
            ),
            "input_large_twoopt_mechanism_family_available": (
                large_twoopt_signal.get("mechanism_family_available")
            ),
            "summary_large_twoopt_direct_evidence_ready": (
                large_twoopt_evidence.get("direct_evidence_ready")
            ),
            "input_large_twoopt_direct_evidence_ready": (
                large_twoopt_signal.get("direct_evidence_ready")
            ),
            "summary_large_twoopt_protocol_row_count": (
                large_twoopt_evidence.get("protocol_row_count")
            ),
            "input_large_twoopt_protocol_row_count": (
                large_twoopt_signal.get("protocol_row_count")
            ),
            "summary_large_twoopt_direct_evidence": (
                _large_twoopt_direct_evidence_signature(
                    large_twoopt_evidence.get("direct_evidence")
                )
            ),
            "input_large_twoopt_direct_evidence": (
                _large_twoopt_direct_evidence_signature(
                    large_twoopt_signal.get("direct_evidence")
                )
            ),
            "summary_large_twoopt_families": _string_items(
                large_twoopt_evidence.get("families")
            ),
            "input_large_twoopt_families": _string_items(
                large_twoopt_signal.get("families")
            ),
            "summary_large_twoopt_protocol_families": _string_items(
                large_twoopt_evidence.get("protocol_families")
            ),
            "input_large_twoopt_protocol_families": _string_items(
                large_twoopt_signal.get("protocol_families")
            ),
            "summary_large_twoopt_continuity_families": _string_items(
                large_twoopt_evidence.get("continuity_families")
            ),
            "input_large_twoopt_continuity_families": _string_items(
                large_twoopt_signal.get("continuity_families")
            ),
            "summary_large_twoopt_rejected_protocol_families": _string_items(
                large_twoopt_evidence.get("rejected_protocol_families")
            ),
            "input_large_twoopt_rejected_protocol_families": _string_items(
                large_twoopt_signal.get("rejected_protocol_families")
            ),
            "summary_large_twoopt_rejected_continuity_families": _string_items(
                large_twoopt_evidence.get("rejected_continuity_families")
            ),
            "input_large_twoopt_rejected_continuity_families": _string_items(
                large_twoopt_signal.get("rejected_continuity_families")
            ),
            "summary_large_twoopt_rejection_reason_counts": _int_mapping(
                large_twoopt_evidence.get("rejection_reason_counts")
            ),
            "input_large_twoopt_rejection_reason_counts": _int_mapping(
                large_twoopt_signal.get("rejection_reason_counts")
            ),
            "summary_large_twoopt_top_row_signal_count": _int_or_zero(
                large_twoopt_evidence.get("top_row_signal_count")
            ),
            "input_large_twoopt_top_row_signal_count": _int_or_zero(
                large_twoopt_signal.get("top_row_signal_count")
            ),
        }
    )
    return "ok" if not failures else "failed", detail


def _summary_from_inventory(
    inventory: Mapping[str, Any],
    key: str,
) -> dict[str, Any]:
    summary = _mapping_or_empty(inventory.get(key))
    if summary:
        return summary
    analysis = _mapping_or_empty(inventory.get("analysis_brief"))
    return _mapping_or_empty(analysis.get(key))


def _runtime_feedback_review_ready(summary: Mapping[str, Any]) -> bool:
    return (
        summary.get("available") is True
        and summary.get("drain_status_complete") is True
    )


def _large_twoopt_direct_evidence_signature(value: Any) -> dict[str, Any]:
    evidence = _mapping_or_empty(value)
    return {
        "ready": evidence.get("ready") is True,
        "missing": _string_items(evidence.get("missing")),
        "required_protected_cases": _string_items(
            evidence.get("required_protected_cases")
        ),
        "protected_cases_observed": _string_items(
            evidence.get("protected_cases_observed")
        ),
        "top_rows_checked": _int_or_zero(evidence.get("top_rows_checked")),
        "complete_direct_evidence_row_count": _int_or_zero(
            evidence.get("complete_direct_evidence_row_count")
        ),
        "positive_effect_row_count": _int_or_zero(
            evidence.get("positive_effect_row_count")
        ),
        "activation_observed_count": _int_or_zero(
            evidence.get("activation_observed_count")
        ),
        "objective_effect_observed_count": _int_or_zero(
            evidence.get("objective_effect_observed_count")
        ),
        "phase_telemetry_observed_count": _int_or_zero(
            evidence.get("phase_telemetry_observed_count")
        ),
        "protected_case_evidence_row_count": _int_or_zero(
            evidence.get("protected_case_evidence_row_count")
        ),
        "protected_case_complete_row_count": _int_or_zero(
            evidence.get("protected_case_complete_row_count")
        ),
    }


def _review_axes_actionability(
    *,
    current_run_evidence: bool,
    invalid_infra_only: bool,
) -> str:
    if invalid_infra_only:
        return "not_actionable_invalid_infra_only"
    if not current_run_evidence:
        return "not_actionable_before_launch_current_run_evidence_required"
    return "actionable_current_run_evidence_present"


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _int_or_zero(item) for key, item in sorted(value.items())}


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "CvrpLargeTwoOptReviewPort",
    "CvrpPostrunSummaryProvider",
    "cvrp_large_twoopt_summary",
]
