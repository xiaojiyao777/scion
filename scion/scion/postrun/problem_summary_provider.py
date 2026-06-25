"""Problem-owned postrun summary provider contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class ProblemPostrunReviewContext:
    """Report-only inputs supplied to problem-owned postrun summaries."""

    inventory: Mapping[str, Any]
    protocol_accounting_summary: Mapping[str, Any]
    measurement_effect_summary: Mapping[str, Any]
    runtime_feedback_summary: Mapping[str, Any]
    failure_taxonomy_summary: Mapping[str, Any]
    research_continuity_summary: Mapping[str, Any]
    prompt_context_visibility_summary: Mapping[str, Any] = field(default_factory=dict)
    proposal_trajectory_manifests: Sequence[Mapping[str, Any]] = ()


class ProblemPostrunSummaryProvider(Protocol):
    """Problem-owned builder for legacy-compatible postrun summary payloads."""

    problem_family: str

    def build_summaries(
        self,
        context: ProblemPostrunReviewContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        """Return summary payloads keyed by their legacy analysis-brief field."""


@dataclass(frozen=True)
class ProblemSummaryActionabilitySpec:
    """Problem-owned policy for one legacy postrun summary."""

    summary_key: str
    problem_family: str
    schema_version: str
    delegated_interpretations: frozenset[str]
    blocking_evidence_gaps: frozenset[str]
    launch_required_field: str | None = None
    nonblocking_gaps_by_interpretation: Mapping[str, frozenset[str]] = field(
        default_factory=dict
    )


def problem_summary_actionability_detail(
    spec: ProblemSummaryActionabilitySpec,
    summary: Mapping[str, Any],
    *,
    expected_family: str | None = None,
    expected_current_run_evidence: bool | None = None,
) -> dict[str, Any]:
    evidence_gaps = _string_items(summary.get("evidence_gaps"))
    schema_version = summary.get("schema_version")
    interpretation = summary.get("interpretation")
    summary_failures: list[str] = []
    if schema_version != spec.schema_version:
        summary_failures.append("stale_problem_summary_schema")
    if summary.get("report_only") is not True:
        summary_failures.append("problem_summary_not_report_only")
    if summary.get("quality_judgment") is not False:
        summary_failures.append("problem_summary_quality_judgment_not_false")
    if summary.get("decision_features_excluded") is not True:
        summary_failures.append("problem_summary_decision_features_not_excluded")
    if interpretation not in spec.delegated_interpretations:
        summary_failures.append("unsupported_problem_summary_interpretation")
    problem_family = summary.get("problem_family")
    if expected_family is not None and problem_family != expected_family:
        summary_failures.append("problem_summary_family_mismatch")
    if (
        expected_current_run_evidence is not None
        and summary.get("current_run_evidence") is not expected_current_run_evidence
    ):
        summary_failures.append("problem_summary_current_run_evidence_mismatch")
    if (
        summary.get("current_run_evidence") is True
        and not _mapping_or_empty(summary.get("evidence"))
    ):
        summary_failures.append("problem_summary_evidence_missing")
    if (
        spec.launch_required_field is not None
        and summary.get("current_run_evidence") is True
        and summary.get(spec.launch_required_field) is not False
    ):
        summary_failures.append("problem_summary_launch_required_flag_stale")
    return {
        "summary": spec.summary_key,
        "problem_family": problem_family,
        "expected_problem_family": expected_family,
        "problem_family_matches_expected": (
            True if expected_family is None else problem_family == expected_family
        ),
        "schema_version": schema_version,
        "expected_schema_version": spec.schema_version,
        "schema_current": schema_version == spec.schema_version,
        "current_run_evidence": summary.get("current_run_evidence"),
        "expected_current_run_evidence": expected_current_run_evidence,
        "launch_required_field": spec.launch_required_field,
        "launch_required_before_conclusion": (
            summary.get(spec.launch_required_field)
            if spec.launch_required_field is not None
            else None
        ),
        "report_only": summary.get("report_only"),
        "quality_judgment": summary.get("quality_judgment"),
        "decision_features_excluded": summary.get("decision_features_excluded"),
        "interpretation": interpretation,
        "interpretation_supported": interpretation in spec.delegated_interpretations,
        "review_axes_actionability": summary.get("review_axes_actionability"),
        "evidence_gaps": evidence_gaps,
        "blocking_evidence_gaps": problem_summary_blocking_gaps(
            spec,
            evidence_gaps,
            interpretation=str(interpretation or ""),
        ),
        "summary_failures": summary_failures,
    }


def problem_summary_actionability_status(
    summaries: Sequence[Mapping[str, Any]],
) -> str:
    ok = all(
        item.get("current_run_evidence") is True
        and item.get("schema_current") is True
        and item.get("interpretation_supported") is True
        and item.get("review_axes_actionability")
        == "actionable_current_run_evidence_present"
        and not item.get("summary_failures")
        and not item.get("blocking_evidence_gaps")
        for item in summaries
    )
    return "ok" if ok else "failed"


def problem_summary_blocking_gaps(
    spec: ProblemSummaryActionabilitySpec,
    evidence_gaps: Sequence[str],
    *,
    interpretation: str,
) -> list[str]:
    nonblocking_for_interpretation = spec.nonblocking_gaps_by_interpretation.get(
        interpretation,
        frozenset(),
    )
    return [
        gap
        for gap in evidence_gaps
        if gap in spec.blocking_evidence_gaps
        and gap not in nonblocking_for_interpretation
    ]


def problem_summary_common_input_consistency_detail(
    *,
    problem_family: str,
    summary_key: str,
    summary: Mapping[str, Any],
    expected_problem_summary: Mapping[str, Any],
    inventory: Mapping[str, Any],
    protocol_accounting_summary: Mapping[str, Any],
    measurement_effect_summary: Mapping[str, Any],
    runtime_feedback_summary: Mapping[str, Any],
    failure_taxonomy_summary: Mapping[str, Any],
    research_continuity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = _mapping_or_empty(summary.get("evidence"))
    protocol_evidence = _mapping_or_empty(evidence.get("protocol"))
    measurement_evidence = _mapping_or_empty(evidence.get("measurement_effect"))
    runtime_evidence = _mapping_or_empty(evidence.get("runtime"))
    continuity_evidence = _mapping_or_empty(evidence.get("research_continuity"))
    quality_evidence = _mapping_or_empty(evidence.get("quality_blocks"))

    protocol_summary = _mapping_or_empty(protocol_accounting_summary)
    protocol_aggregate = _mapping_or_empty(protocol_summary.get("aggregate"))
    protocol_rows = _mapping_or_empty(protocol_aggregate.get("protocol_rows"))
    protocol_formal_artifacts = _mapping_or_empty(
        protocol_aggregate.get("formal_candidate_artifacts")
    )
    protocol_stage_rows = _mapping_or_empty(protocol_aggregate.get("stage_rows"))
    counters = _mapping_or_empty(inventory.get("counters"))
    input_formal_screened_candidates = max(
        _int_or_zero(protocol_aggregate.get("formal_screened_candidates")),
        _int_or_zero(counters.get("formal_screened_candidates")),
        _int_or_zero(counters.get("screened_experiments")),
    )
    input_protocol_evaluated = max(
        _int_or_zero(protocol_rows.get("protocol_evaluated_candidates")),
        _int_or_zero(protocol_aggregate.get("formal_protocol_evaluated_candidates")),
        _int_or_zero(counters.get("protocol_evaluated_candidates")),
    )
    summary_protocol_evaluated = _int_or_zero(
        protocol_evidence.get("protocol_evaluated_candidates")
    )
    summary_formal_screened_candidates = _int_or_zero(
        protocol_evidence.get("formal_screened_candidates")
    )
    input_protocol_metric_results = _int_or_zero(
        protocol_rows.get("protocol_metric_results")
    )
    summary_protocol_metric_results = _int_or_zero(
        protocol_evidence.get("protocol_metric_results")
    )
    input_formal_candidate_artifact_rows = _int_or_zero(
        protocol_formal_artifacts.get("row_count")
    )
    summary_formal_candidate_artifact_rows = _int_or_zero(
        protocol_evidence.get("formal_candidate_artifact_rows")
    )
    summary_protocol_stage_rows = _mapping_or_empty(protocol_evidence.get("stage_rows"))

    measurement_summary = _mapping_or_empty(measurement_effect_summary)
    measurement_aggregate = _mapping_or_empty(measurement_summary.get("aggregate"))
    runtime_summary = _mapping_or_empty(runtime_feedback_summary)
    continuity_summary = _mapping_or_empty(research_continuity_summary)
    failure_summary = _mapping_or_empty(failure_taxonomy_summary)
    failure_aggregate = _mapping_or_empty(failure_summary.get("aggregate"))
    proposal_quality = _mapping_or_empty(failure_aggregate.get("proposal_quality"))
    input_quality_block_signal = max(
        _int_or_zero(proposal_quality.get("proposal_quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_blocks")),
        _int_or_zero(proposal_quality.get("quality_block_ledger_count")),
    )
    summary_quality_block_signal = max(
        _int_or_zero(quality_evidence.get("proposal_quality_blocks")),
        _int_or_zero(quality_evidence.get("quality_blocks")),
        _int_or_zero(quality_evidence.get("quality_block_ledger_count")),
    )
    input_quality_block_reason_counts = _int_mapping(
        proposal_quality.get("quality_block_reason_counts")
    )
    summary_quality_block_reason_counts = _int_mapping(
        quality_evidence.get("reason_counts")
    )
    input_reports_with_quality_blocks = _int_or_zero(
        proposal_quality.get("reports_with_quality_blocks")
    )
    summary_reports_with_quality_blocks = _int_or_zero(
        quality_evidence.get("reports_with_quality_blocks")
    )

    failures: list[str] = []
    interpretation = str(summary.get("interpretation") or "")
    expected_interpretation = str(expected_problem_summary.get("interpretation") or "")
    summary_evidence_gaps = _string_items(summary.get("evidence_gaps"))
    expected_evidence_gaps = _string_items(expected_problem_summary.get("evidence_gaps"))
    if interpretation != expected_interpretation:
        failures.append("problem_summary_interpretation_mismatch")
    if sorted(summary_evidence_gaps) != sorted(expected_evidence_gaps):
        failures.append("problem_summary_evidence_gaps_mismatch")
    if summary.get("review_axes_actionability") != expected_problem_summary.get(
        "review_axes_actionability"
    ):
        failures.append("problem_summary_review_axes_actionability_mismatch")
    launch_required_field = {
        "warehouse_followup_summary": "launch_required_before_plateau_conclusion",
        "cvrp_large_twoopt_summary": "launch_required_before_twoopt_conclusion",
    }.get(summary_key)
    if (
        launch_required_field is not None
        and summary.get(launch_required_field)
        != expected_problem_summary.get(launch_required_field)
    ):
        failures.append("problem_summary_launch_required_flag_mismatch")
    if not evidence:
        failures.append("problem_summary_evidence_missing")
    if summary_protocol_evaluated != input_protocol_evaluated:
        failures.append("problem_summary_protocol_evaluated_mismatch")
    if _is_protocol_evaluated_interpretation(interpretation):
        if summary_formal_screened_candidates != input_formal_screened_candidates:
            failures.append("problem_summary_formal_screened_candidates_mismatch")
        if summary_protocol_metric_results != input_protocol_metric_results:
            failures.append("problem_summary_protocol_metric_results_mismatch")
        if (
            summary_formal_candidate_artifact_rows
            != input_formal_candidate_artifact_rows
        ):
            failures.append("problem_summary_formal_candidate_artifact_rows_mismatch")
        if _json_comparison_value(summary_protocol_stage_rows) != _json_comparison_value(
            protocol_stage_rows
        ):
            failures.append("problem_summary_protocol_stage_rows_mismatch")
        if summary_protocol_evaluated <= 0:
            failures.append("problem_summary_protocol_evaluated_missing")
        if input_protocol_evaluated <= 0:
            failures.append("review_input_protocol_evaluated_missing")
    if _is_quality_blocked_interpretation(interpretation):
        if summary_protocol_evaluated > 0 or input_protocol_evaluated > 0:
            failures.append(
                "quality_blocked_no_protocol_has_protocol_evaluated_candidates"
            )
        if summary_quality_block_signal <= 0:
            failures.append("problem_summary_quality_block_signal_missing")
        if input_quality_block_signal <= 0:
            failures.append("failure_taxonomy_quality_block_signal_missing")
        if summary_reports_with_quality_blocks != input_reports_with_quality_blocks:
            failures.append("problem_summary_reports_with_quality_blocks_mismatch")
        if summary_quality_block_reason_counts != input_quality_block_reason_counts:
            failures.append("problem_summary_quality_block_reason_counts_mismatch")
    if (
        measurement_evidence.get("available")
        is not measurement_summary.get("available")
    ):
        failures.append("problem_summary_measurement_available_mismatch")
    if _int_or_zero(measurement_evidence.get("protocol_row_count")) != _int_or_zero(
        measurement_aggregate.get("protocol_row_count")
    ):
        failures.append("problem_summary_measurement_protocol_rows_mismatch")
    for field in ("rows_at_or_above_mde", "rows_with_ci_high_below_mde"):
        if _int_or_zero(measurement_evidence.get(field)) != _int_or_zero(
            measurement_aggregate.get(field)
        ):
            failures.append(f"problem_summary_measurement_{field}_mismatch")
    if _int_mapping(measurement_evidence.get("interpretation_counts")) != _int_mapping(
        measurement_aggregate.get("interpretation_counts")
    ):
        failures.append("problem_summary_measurement_interpretation_counts_mismatch")
    if not _numeric_or_value_equal(
        measurement_evidence.get("max_effect_to_mde_ratio"),
        measurement_aggregate.get("max_effect_to_mde_ratio"),
    ):
        failures.append("problem_summary_measurement_max_effect_to_mde_ratio_mismatch")
    runtime_ready = runtime_summary.get("review_ready") is True
    runtime_evidence_ready = (
        runtime_evidence.get("review_ready")
        if "review_ready" in runtime_evidence
        else runtime_evidence.get("available")
    )
    runtime_raw_available = runtime_summary.get("available") is True
    runtime_evidence_raw_available = (
        runtime_evidence.get("raw_available")
        if "raw_available" in runtime_evidence
        else runtime_evidence.get("available")
    )
    runtime_aggregate = _mapping_or_empty(runtime_summary.get("aggregate"))
    runtime_budget = _mapping_or_empty(
        runtime_aggregate.get("runtime_budget_diagnostics")
    )
    if runtime_evidence_ready is not runtime_ready:
        failures.append("problem_summary_runtime_review_ready_mismatch")
    if runtime_evidence_raw_available is not runtime_raw_available:
        failures.append("problem_summary_runtime_raw_available_mismatch")
    if (
        runtime_evidence.get("drain_status_complete")
        is not runtime_summary.get("drain_status_complete")
    ):
        failures.append("problem_summary_runtime_drain_status_mismatch")
    if _int_mapping(runtime_evidence.get("runtime_model_counts")) != _int_mapping(
        runtime_budget.get("runtime_model_counts")
    ):
        failures.append("problem_summary_runtime_model_counts_mismatch")
    if _int_or_zero(
        runtime_evidence.get("runtime_budget_diagnostic_count")
    ) != _int_or_zero(runtime_budget.get("diagnostic_count")):
        failures.append("problem_summary_runtime_budget_diagnostic_count_mismatch")
    if (
        continuity_evidence.get("available")
        is not continuity_summary.get("available")
    ):
        failures.append("problem_summary_continuity_available_mismatch")
    if _int_or_zero(
        continuity_evidence.get("continuity_report_count")
    ) != _int_or_zero(continuity_summary.get("continuity_report_count")):
        failures.append("problem_summary_continuity_report_count_mismatch")

    return {
        "problem_family": problem_family,
        "summary": summary_key,
        "interpretation": interpretation,
        "expected_interpretation": expected_interpretation,
        "summary_evidence_gaps": summary_evidence_gaps,
        "expected_evidence_gaps": expected_evidence_gaps,
        "summary_review_axes_actionability": summary.get(
            "review_axes_actionability"
        ),
        "expected_review_axes_actionability": expected_problem_summary.get(
            "review_axes_actionability"
        ),
        "launch_required_field": launch_required_field,
        "summary_launch_required_before_conclusion": (
            summary.get(launch_required_field)
            if launch_required_field is not None
            else None
        ),
        "expected_launch_required_before_conclusion": (
            expected_problem_summary.get(launch_required_field)
            if launch_required_field is not None
            else None
        ),
        "failures": failures,
        "summary_protocol_evaluated_candidates": summary_protocol_evaluated,
        "input_protocol_evaluated_candidates": input_protocol_evaluated,
        "summary_formal_screened_candidates": (
            summary_formal_screened_candidates
        ),
        "input_formal_screened_candidates": input_formal_screened_candidates,
        "summary_protocol_metric_results": summary_protocol_metric_results,
        "input_protocol_metric_results": input_protocol_metric_results,
        "summary_formal_candidate_artifact_rows": (
            summary_formal_candidate_artifact_rows
        ),
        "input_formal_candidate_artifact_rows": (
            input_formal_candidate_artifact_rows
        ),
        "summary_protocol_stage_rows": summary_protocol_stage_rows,
        "input_protocol_stage_rows": protocol_stage_rows,
        "summary_quality_block_signal": summary_quality_block_signal,
        "input_quality_block_signal": input_quality_block_signal,
        "summary_reports_with_quality_blocks": summary_reports_with_quality_blocks,
        "input_reports_with_quality_blocks": input_reports_with_quality_blocks,
        "summary_quality_block_reason_counts": summary_quality_block_reason_counts,
        "input_quality_block_reason_counts": input_quality_block_reason_counts,
        "summary_measurement_available": measurement_evidence.get("available"),
        "input_measurement_available": measurement_summary.get("available"),
        "summary_measurement_protocol_row_count": measurement_evidence.get(
            "protocol_row_count"
        ),
        "input_measurement_protocol_row_count": measurement_aggregate.get(
            "protocol_row_count"
        ),
        "summary_measurement_rows_at_or_above_mde": measurement_evidence.get(
            "rows_at_or_above_mde"
        ),
        "input_measurement_rows_at_or_above_mde": measurement_aggregate.get(
            "rows_at_or_above_mde"
        ),
        "summary_measurement_rows_with_ci_high_below_mde": measurement_evidence.get(
            "rows_with_ci_high_below_mde"
        ),
        "input_measurement_rows_with_ci_high_below_mde": measurement_aggregate.get(
            "rows_with_ci_high_below_mde"
        ),
        "summary_measurement_interpretation_counts": _int_mapping(
            measurement_evidence.get("interpretation_counts")
        ),
        "input_measurement_interpretation_counts": _int_mapping(
            measurement_aggregate.get("interpretation_counts")
        ),
        "summary_measurement_max_effect_to_mde_ratio": measurement_evidence.get(
            "max_effect_to_mde_ratio"
        ),
        "input_measurement_max_effect_to_mde_ratio": measurement_aggregate.get(
            "max_effect_to_mde_ratio"
        ),
        "summary_measurement_mechanism_family_mapped_row_count": _int_or_zero(
            measurement_evidence.get("mechanism_family_mapped_row_count")
        ),
        "input_measurement_mechanism_family_mapped_row_count": _int_or_zero(
            measurement_aggregate.get("mechanism_family_mapped_row_count")
        ),
        "summary_measurement_mechanism_family_unmapped_row_count": _int_or_zero(
            measurement_evidence.get("mechanism_family_unmapped_row_count")
        ),
        "input_measurement_mechanism_family_unmapped_row_count": _int_or_zero(
            measurement_aggregate.get("mechanism_family_unmapped_row_count")
        ),
        "summary_runtime_review_ready": runtime_evidence_ready,
        "input_runtime_review_ready": runtime_summary.get("review_ready"),
        "summary_runtime_raw_available": runtime_evidence_raw_available,
        "input_runtime_raw_available": runtime_summary.get("available"),
        "summary_runtime_drain_status_complete": runtime_evidence.get(
            "drain_status_complete"
        ),
        "input_runtime_drain_status_complete": runtime_summary.get(
            "drain_status_complete"
        ),
        "summary_runtime_model_counts": _int_mapping(
            runtime_evidence.get("runtime_model_counts")
        ),
        "input_runtime_model_counts": _int_mapping(
            runtime_budget.get("runtime_model_counts")
        ),
        "summary_runtime_budget_diagnostic_count": _int_or_zero(
            runtime_evidence.get("runtime_budget_diagnostic_count")
        ),
        "input_runtime_budget_diagnostic_count": _int_or_zero(
            runtime_budget.get("diagnostic_count")
        ),
        "summary_continuity_available": continuity_evidence.get("available"),
        "input_continuity_available": continuity_summary.get("available"),
        "summary_continuity_report_count": continuity_evidence.get(
            "continuity_report_count"
        ),
        "input_continuity_report_count": continuity_summary.get(
            "continuity_report_count"
        ),
    }


def _is_protocol_evaluated_interpretation(interpretation: str) -> bool:
    return (
        interpretation.startswith("protocol_evaluated_")
        or interpretation == "bounded_twoopt_review_ready"
    )


def _is_quality_blocked_interpretation(interpretation: str) -> bool:
    return interpretation.startswith("quality_blocked_")


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _string_list(value: Any) -> list[str]:
    return _string_items(value)


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _int_or_zero(count) for key, count in sorted(value.items())}


def _json_comparison_value(value: Any) -> Any:
    import json

    return json.loads(json.dumps(value, sort_keys=True))


def _numeric_or_value_equal(actual: Any, expected: Any) -> bool:
    if actual == expected:
        return True
    try:
        return abs(float(actual) - float(expected)) <= 1e-9
    except (TypeError, ValueError):
        return False
