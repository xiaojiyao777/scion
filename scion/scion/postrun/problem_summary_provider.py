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


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
