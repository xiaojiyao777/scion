"""Warehouse-owned postrun summary providers."""

from __future__ import annotations

from typing import Any, Mapping

from scion.postrun import (
    ProblemPostrunReviewContext,
    ProblemReviewSummary,
    ProblemSummaryActionabilitySpec,
    problem_summary_common_input_consistency_detail,
)
from scion.problems.warehouse_delivery.postrun_handoff import (
    WAREHOUSE_FOLLOWUP_REQUIREMENT_KEYS,
)
from scion.problems.warehouse_delivery.research_guidance import (
    WAREHOUSE_PROBLEM_FAMILY,
)


WAREHOUSE_FOLLOWUP_REVIEW_AXES = (
    "preserve_or_improve_champion_v2_promotion_behavior",
    "separate_quality_blocked_proposals_from_protocol_evaluated_no_effect",
    "compare_cost_delta_and_improving_move_telemetry_before_split_delta_only_claims",
    "explain_fast_completion_against_warehouse_runtime_model",
    "judge_continuous_improvement_vs_real_plateau_only_after_current_run_postrun_evidence",
)

_BLOCKING_WAREHOUSE_FOLLOWUP_GAPS = frozenset(
    {
        "warehouse_handoff_requirements_incomplete",
        "invalid_infra_only_no_research_conclusion",
        "launch_required_before_plateau_conclusion",
        "missing_measurement_effect_summary",
        "missing_research_continuity_summary",
        "missing_runtime_feedback_summary",
        "no_protocol_evaluated_candidates",
    }
)

WAREHOUSE_FOLLOWUP_ACTIONABILITY_SPEC = ProblemSummaryActionabilitySpec(
    summary_key="warehouse_followup_summary",
    problem_family=WAREHOUSE_PROBLEM_FAMILY,
    schema_version="scion.postrun_warehouse_followup_summary.v1",
    delegated_interpretations=frozenset(
        {
            "quality_blocked_no_protocol_plateau_conclusion",
            "protocol_evaluated_measurement_effect_inconclusive",
            "protocol_evaluated_plateau_review_ready",
            "protocol_evaluated_positive_effect_review_ready",
            "protocol_evaluated_research_continuity_too_shallow",
        }
    ),
    blocking_evidence_gaps=_BLOCKING_WAREHOUSE_FOLLOWUP_GAPS,
    launch_required_field="launch_required_before_plateau_conclusion",
    nonblocking_gaps_by_interpretation={
        "quality_blocked_no_protocol_plateau_conclusion": frozenset(
            {
                "missing_measurement_effect_summary",
                "missing_research_continuity_summary",
                "missing_runtime_feedback_summary",
            }
        )
    },
)


class WarehousePostrunSummaryProvider:
    """Build legacy-compatible warehouse analysis-brief summaries."""

    problem_family = WAREHOUSE_PROBLEM_FAMILY

    def build_summaries(
        self,
        context: ProblemPostrunReviewContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        return {
            "warehouse_followup_summary": warehouse_followup_summary(
                context.inventory,
                protocol_accounting_summary=context.protocol_accounting_summary,
                measurement_effect_summary=context.measurement_effect_summary,
                runtime_feedback_summary=context.runtime_feedback_summary,
                failure_taxonomy_summary=context.failure_taxonomy_summary,
                research_continuity_summary=context.research_continuity_summary,
            )
        }


class WarehouseFollowupReviewPort:
    """Expose the historical warehouse follow-up as report-only context."""

    problem_family = WAREHOUSE_PROBLEM_FAMILY
    review_key = "warehouse_followup_summary"

    def review(self, inventory: Mapping[str, Any]) -> ProblemReviewSummary:
        summary = _summary_from_inventory(inventory, self.review_key)
        if not summary:
            return ProblemReviewSummary(
                problem_family=self.problem_family,
                review_key=self.review_key,
                status="not_reported",
                interpretation="missing_warehouse_followup_summary",
                ready=True,
                detail={
                    "summary_available": False,
                    "readiness_input": False,
                },
            )
        gaps = _string_items(summary.get("evidence_gaps"))
        return ProblemReviewSummary(
            problem_family=self.problem_family,
            review_key=self.review_key,
            status="reported",
            interpretation=str(summary.get("interpretation") or ""),
            ready=True,
            detail={
                "summary_schema_version": summary.get("schema_version"),
                "current_run_evidence": summary.get("current_run_evidence"),
                "evidence_gaps": gaps,
                "readiness_input": False,
                "review_axes_actionability": summary.get(
                    "review_axes_actionability"
                ),
            },
        )


def warehouse_followup_summary(
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
        "schema_version": "scion.postrun_warehouse_followup_summary.v1",
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
        "launch_required_before_plateau_conclusion": False,
        "interpretation": "not_warehouse_delivery",
        "evidence": {},
        "evidence_gaps": [],
        "required_review_axes": list(WAREHOUSE_FOLLOWUP_REVIEW_AXES),
        "deferred_review_axes": [],
        "review_axes_actionability": "not_applicable",
    }
    if problem_family != WAREHOUSE_PROBLEM_FAMILY:
        return base

    handoff_requirements = warehouse_handoff_requirements(
        phase4=phase4,
        contract=contract,
    )
    handoff_complete = all(
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
    measurement_signal = warehouse_followup_measurement_signal(
        measurement_effect_summary
    )
    runtime = _mapping_or_empty(runtime_feedback_summary.get("aggregate"))
    runtime_budget = _mapping_or_empty(runtime.get("runtime_budget_diagnostics"))
    continuity_signal = warehouse_followup_continuity_signal(
        research_continuity_summary
    )
    failure = _mapping_or_empty(failure_taxonomy_summary.get("aggregate"))
    proposal_quality = _mapping_or_empty(failure.get("proposal_quality"))
    quality_block_signal = max(
        _int_or_zero(proposal_quality.get("proposal_quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_block_ledger_count")),
    )
    runtime_raw_available = runtime_feedback_summary.get("available") is True
    runtime_available = _runtime_feedback_review_ready(runtime_feedback_summary)
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
            "available": measurement_effect_summary.get("available") is True,
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
            **measurement_signal,
        },
        "quality_blocks": {
            "proposal_quality_blocks": _int_or_zero(
                proposal_quality.get("proposal_quality_blocks")
            ),
            "quality_blocks": _int_or_zero(proposal_quality.get("quality_blocks")),
            "quality_block_ledger_count": _int_or_zero(
                proposal_quality.get("quality_block_ledger_count")
            ),
            "reports_with_quality_blocks": _int_or_zero(
                proposal_quality.get("reports_with_quality_blocks")
            ),
            "reason_counts": _int_mapping(
                proposal_quality.get("quality_block_reason_counts")
            ),
        },
        "runtime": {
            "available": runtime_raw_available,
            "review_ready": runtime_available,
            "runtime_model_counts": _int_mapping(
                runtime_budget.get("runtime_model_counts")
            ),
            "runtime_budget_diagnostic_count": _int_or_zero(
                runtime_budget.get("diagnostic_count")
            ),
        },
        "research_continuity": {
            "available": research_continuity_summary.get("available") is True,
            "continuity_report_count": _int_or_zero(
                research_continuity_summary.get("continuity_report_count")
            ),
            **continuity_signal,
        },
    }
    interpretation = warehouse_followup_interpretation(
        current_run_evidence=current_run_evidence,
        invalid_infra_only=invalid_infra_only,
        handoff_complete=handoff_complete,
        protocol_evaluated_candidates=protocol_evaluated_candidates,
        formal_screened_candidates=formal_screened_candidates,
        quality_block_signal=quality_block_signal,
        measurement_available=measurement_effect_summary.get("available") is True,
        measurement_plateau_consistent=measurement_signal["plateau_consistent"],
        measurement_positive_effect_at_or_above_mde=measurement_signal[
            "positive_effect_at_or_above_mde"
        ],
        runtime_available=runtime_available,
        continuity_available=research_continuity_summary.get("available") is True,
        continuity_substantive=continuity_signal["substantive"],
    )
    return {
        **base,
        "available": True,
        "handoff_complete": handoff_complete,
        "handoff_requirements": handoff_requirements,
        "launch_required_before_plateau_conclusion": not current_run_evidence,
        "interpretation": interpretation,
        "evidence": evidence,
        "evidence_gaps": warehouse_followup_evidence_gaps(
            current_run_evidence=current_run_evidence,
            invalid_infra_only=invalid_infra_only,
            handoff_complete=handoff_complete,
            protocol_evaluated_candidates=protocol_evaluated_candidates,
            quality_block_signal=quality_block_signal,
            measurement_available=measurement_effect_summary.get("available")
            is True,
            measurement_plateau_consistent=measurement_signal["plateau_consistent"],
            measurement_positive_effect_at_or_above_mde=measurement_signal[
                "positive_effect_at_or_above_mde"
            ],
            runtime_available=runtime_available,
            continuity_available=research_continuity_summary.get("available")
            is True,
            continuity_substantive=continuity_signal["substantive"],
        ),
        "deferred_review_axes": (
            list(WAREHOUSE_FOLLOWUP_REVIEW_AXES)
            if not current_run_evidence
            else []
        ),
        "review_axes_actionability": _review_axes_actionability(
            current_run_evidence=current_run_evidence,
            invalid_infra_only=invalid_infra_only,
        ),
    }


def warehouse_followup_input_consistency(
    inventory: Mapping[str, Any],
    *,
    summary: Mapping[str, Any],
    protocol_accounting_summary: Mapping[str, Any],
    measurement_effect_summary: Mapping[str, Any],
    runtime_feedback_summary: Mapping[str, Any],
    failure_taxonomy_summary: Mapping[str, Any],
    research_continuity_summary: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    expected_summary = warehouse_followup_summary(
        inventory,
        protocol_accounting_summary=protocol_accounting_summary,
        measurement_effect_summary=measurement_effect_summary,
        runtime_feedback_summary=runtime_feedback_summary,
        failure_taxonomy_summary=failure_taxonomy_summary,
        research_continuity_summary=research_continuity_summary,
    )
    detail = problem_summary_common_input_consistency_detail(
        problem_family=WAREHOUSE_PROBLEM_FAMILY,
        summary_key=WAREHOUSE_FOLLOWUP_ACTIONABILITY_SPEC.summary_key,
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
    continuity_evidence = _mapping_or_empty(evidence.get("research_continuity"))
    interpretation = str(summary.get("interpretation") or "")
    measurement_signal = warehouse_followup_measurement_signal(
        measurement_effect_summary
    )
    for field in (
        "effect_signal",
        "positive_effect_at_or_above_mde",
        "plateau_consistent",
        "all_ci_high_below_mde",
    ):
        if not interpretation.startswith("protocol_evaluated_"):
            continue
        summary_value = measurement_evidence.get(field)
        input_value = measurement_signal.get(field)
        if isinstance(input_value, bool):
            if summary_value is not input_value:
                failures.append(
                    f"problem_summary_warehouse_measurement_{field}_mismatch"
                )
        elif str(summary_value or "") != str(input_value or ""):
            failures.append(
                f"problem_summary_warehouse_measurement_{field}_mismatch"
            )

    continuity_signal = warehouse_followup_continuity_signal(
        research_continuity_summary
    )
    for field in (
        "substantive",
        "max_branch_depth",
        "weak_positive_accepted",
        "weak_positive_observed",
    ):
        summary_value = continuity_evidence.get(field)
        input_value = continuity_signal.get(field)
        if isinstance(input_value, bool):
            if summary_value is not input_value:
                failures.append(
                    f"problem_summary_warehouse_continuity_{field}_mismatch"
                )
        elif _int_or_zero(summary_value) != _int_or_zero(input_value):
            failures.append(
                f"problem_summary_warehouse_continuity_{field}_mismatch"
            )
    if (
        interpretation == "protocol_evaluated_plateau_review_ready"
        and continuity_evidence.get("substantive") is not True
    ):
        failures.append("warehouse_plateau_continuity_not_substantive")
    if interpretation == "protocol_evaluated_plateau_review_ready":
        if measurement_signal.get("plateau_consistent") is not True:
            failures.append("review_input_warehouse_measurement_not_plateau_consistent")
        if measurement_signal.get("positive_effect_at_or_above_mde") is True:
            failures.append("review_input_warehouse_positive_effect_not_plateau")
        if continuity_signal.get("substantive") is not True:
            failures.append("review_input_warehouse_continuity_not_substantive")
    if interpretation == "protocol_evaluated_positive_effect_review_ready":
        if measurement_signal.get("positive_effect_at_or_above_mde") is not True:
            failures.append("review_input_warehouse_positive_effect_missing")
    if interpretation == "protocol_evaluated_measurement_effect_inconclusive":
        if measurement_signal.get("plateau_consistent") is True:
            failures.append(
                "review_input_warehouse_measurement_inconclusive_has_plateau_signal"
            )
        if measurement_signal.get("positive_effect_at_or_above_mde") is True:
            failures.append(
                "review_input_warehouse_measurement_inconclusive_has_positive_effect"
            )

    detail.update(
        {
            "summary_measurement_effect_signal": measurement_evidence.get(
                "effect_signal"
            ),
            "input_measurement_effect_signal": measurement_signal.get(
                "effect_signal"
            ),
            "summary_measurement_plateau_consistent": measurement_evidence.get(
                "plateau_consistent"
            ),
            "input_measurement_plateau_consistent": measurement_signal.get(
                "plateau_consistent"
            ),
            "summary_measurement_positive_effect_at_or_above_mde": (
                measurement_evidence.get("positive_effect_at_or_above_mde")
            ),
            "input_measurement_positive_effect_at_or_above_mde": (
                measurement_signal.get("positive_effect_at_or_above_mde")
            ),
            "summary_continuity_substantive": continuity_evidence.get(
                "substantive"
            ),
            "input_continuity_substantive": continuity_signal.get("substantive"),
            "summary_continuity_max_branch_depth": continuity_evidence.get(
                "max_branch_depth"
            ),
            "input_continuity_max_branch_depth": continuity_signal.get(
                "max_branch_depth"
            ),
            "summary_continuity_weak_positive_accepted": continuity_evidence.get(
                "weak_positive_accepted"
            ),
            "input_continuity_weak_positive_accepted": continuity_signal.get(
                "weak_positive_accepted"
            ),
        }
    )
    return "ok" if not failures else "failed", detail


def warehouse_handoff_requirements(
    *,
    phase4: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    problem_specific = _mapping_or_empty(phase4.get("problem_specific_requirements"))
    checks = _mapping_or_empty(contract.get("checks"))
    requirements: dict[str, Any] = {}
    for key in WAREHOUSE_FOLLOWUP_REQUIREMENT_KEYS:
        coverage = _mapping_or_empty(problem_specific.get(key))
        check = _mapping_or_empty(checks.get(key))
        requirements[key] = {
            "available": coverage.get("available") is True
            or check.get("passed") is True,
            "count": _int_or_zero(coverage.get("count")),
            "source": coverage.get("source") or check.get("detail") or "",
            "contract_check_passed": check.get("passed"),
            "contract_detail": check.get("detail"),
        }
    return requirements


def warehouse_followup_measurement_signal(
    measurement_effect_summary: Mapping[str, Any],
) -> dict[str, Any]:
    aggregate = _mapping_or_empty(measurement_effect_summary.get("aggregate"))
    available = measurement_effect_summary.get("available") is True
    protocol_row_count = _int_or_zero(aggregate.get("protocol_row_count"))
    rows_at_or_above_mde = _int_or_zero(aggregate.get("rows_at_or_above_mde"))
    rows_with_ci_high_below_mde = _int_or_zero(
        aggregate.get("rows_with_ci_high_below_mde")
    )
    positive_effect_at_or_above_mde = (
        available and protocol_row_count > 0 and rows_at_or_above_mde > 0
    )
    all_ci_high_below_mde = (
        available
        and protocol_row_count > 0
        and rows_with_ci_high_below_mde >= protocol_row_count
    )
    plateau_consistent = (
        all_ci_high_below_mde
        and not positive_effect_at_or_above_mde
    )
    if not available:
        effect_signal = "measurement_unavailable"
    elif protocol_row_count <= 0:
        effect_signal = "no_protocol_effect_rows"
    elif positive_effect_at_or_above_mde:
        effect_signal = "positive_effect_at_or_above_mde"
    elif all_ci_high_below_mde:
        effect_signal = "ci_high_below_mde_plateau_consistent"
    elif rows_with_ci_high_below_mde > 0:
        effect_signal = "partial_ci_high_below_mde_inconclusive"
    else:
        effect_signal = "protocol_effects_below_mde_or_inconclusive"
    return {
        "effect_signal": effect_signal,
        "positive_effect_at_or_above_mde": positive_effect_at_or_above_mde,
        "plateau_consistent": plateau_consistent,
        "all_ci_high_below_mde": all_ci_high_below_mde,
    }


def warehouse_followup_continuity_signal(
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    return _problem_research_continuity_signal(research_continuity_summary)


def warehouse_followup_interpretation(
    *,
    current_run_evidence: bool,
    invalid_infra_only: bool,
    handoff_complete: bool,
    protocol_evaluated_candidates: int,
    formal_screened_candidates: int,
    quality_block_signal: int,
    measurement_available: bool,
    measurement_plateau_consistent: bool,
    measurement_positive_effect_at_or_above_mde: bool,
    runtime_available: bool,
    continuity_available: bool,
    continuity_substantive: bool,
) -> str:
    if invalid_infra_only:
        return "invalid_infra_only_no_research_conclusion"
    if not current_run_evidence:
        return "prepared_only_launch_required"
    if protocol_evaluated_candidates > 0:
        if not handoff_complete:
            return "protocol_evaluated_handoff_incomplete"
        if not (
            measurement_available
            and runtime_available
            and continuity_available
        ):
            return "protocol_evaluated_review_inputs_incomplete"
        if measurement_positive_effect_at_or_above_mde:
            return "protocol_evaluated_positive_effect_review_ready"
        if not measurement_plateau_consistent:
            return "protocol_evaluated_measurement_effect_inconclusive"
        if not continuity_substantive:
            return "protocol_evaluated_research_continuity_too_shallow"
        return "protocol_evaluated_plateau_review_ready"
    if quality_block_signal > 0:
        return "quality_blocked_no_protocol_plateau_conclusion"
    if formal_screened_candidates > 0:
        return "screened_without_protocol_evaluation"
    return "insufficient_current_run_evidence"


def warehouse_followup_evidence_gaps(
    *,
    current_run_evidence: bool,
    invalid_infra_only: bool,
    handoff_complete: bool,
    protocol_evaluated_candidates: int,
    quality_block_signal: int,
    measurement_available: bool,
    measurement_plateau_consistent: bool,
    measurement_positive_effect_at_or_above_mde: bool,
    runtime_available: bool,
    continuity_available: bool,
    continuity_substantive: bool,
) -> list[str]:
    gaps: list[str] = []
    if not handoff_complete:
        gaps.append("warehouse_handoff_requirements_incomplete")
    if invalid_infra_only:
        gaps.append("invalid_infra_only_no_research_conclusion")
        return gaps
    if not current_run_evidence:
        gaps.append("launch_required_before_plateau_conclusion")
        return gaps
    if protocol_evaluated_candidates <= 0:
        if quality_block_signal > 0:
            gaps.append("quality_blocked_before_protocol_evaluation")
        else:
            gaps.append("no_protocol_evaluated_candidates")
    if not measurement_available:
        gaps.append("missing_measurement_effect_summary")
    elif (
        protocol_evaluated_candidates > 0
        and not measurement_plateau_consistent
        and not measurement_positive_effect_at_or_above_mde
    ):
        gaps.append("warehouse_measurement_effect_inconclusive")
    if not runtime_available:
        gaps.append("missing_runtime_feedback_summary")
    if not continuity_available:
        gaps.append("missing_research_continuity_summary")
    elif (
        protocol_evaluated_candidates > 0
        and measurement_plateau_consistent
        and not measurement_positive_effect_at_or_above_mde
        and not continuity_substantive
    ):
        gaps.append("warehouse_research_continuity_evidence_too_shallow")
    return gaps


def _problem_research_continuity_signal(
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    aggregate = _mapping_or_empty(research_continuity_summary.get("aggregate"))
    counts = _research_continuity_action_counts(
        research_continuity_summary.get("entries")
    )
    max_branch_depth = _int_or_zero(aggregate.get("max_branch_depth"))
    mechanism_family_counts = _int_mapping(aggregate.get("mechanism_family_counts"))
    active_shape_counts = _int_mapping(aggregate.get("active_shape_counts"))
    substantive = (
        max_branch_depth >= 2
        or counts["weak_positive_accepted"] > 0
    )
    return {
        "substantive": substantive,
        "max_branch_depth": max_branch_depth,
        "weak_positive_observed": counts["weak_positive_observed"],
        "weak_positive_accepted": counts["weak_positive_accepted"],
        "mechanism_family_counts": mechanism_family_counts,
        "active_shape_counts": active_shape_counts,
    }


def _research_continuity_action_counts(entries: Any) -> dict[str, int]:
    counts = {
        "weak_positive_accepted": 0,
        "weak_positive_observed": 0,
    }
    if not isinstance(entries, list):
        return counts
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        transfer = _mapping_or_empty(entry.get("weak_positive_transfer"))
        counts["weak_positive_accepted"] += _int_or_zero(
            transfer.get("accepted_count")
        )
        counts["weak_positive_observed"] += _int_or_zero(
            transfer.get("observed_opportunity_count")
        )
    return counts


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
    return summary.get("available") is True and summary.get("review_ready") is True


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
    "WAREHOUSE_FOLLOWUP_REQUIREMENT_KEYS",
    "WAREHOUSE_FOLLOWUP_REVIEW_AXES",
    "WarehouseFollowupReviewPort",
    "WarehousePostrunSummaryProvider",
    "warehouse_followup_continuity_signal",
    "warehouse_followup_measurement_signal",
    "warehouse_followup_summary",
]
