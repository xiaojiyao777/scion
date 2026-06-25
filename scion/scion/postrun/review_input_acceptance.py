"""Generic review-input summary acceptance checks."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any, Mapping

from scion.postrun.acceptance_checks import (
    PostrunAcceptanceCheck,
    PostrunAcceptanceCheckBundle,
)


REVIEW_INPUT_SUMMARY_SPECS = {
    "protocol_accounting_summary": (
        "scion.postrun_protocol_accounting_summary.v1",
        "accounting_report_count",
    ),
    "measurement_effect_summary": (
        "scion.postrun_measurement_effect_summary.v1",
        "effect_report_count",
    ),
    "runtime_feedback_summary": (
        "scion.postrun_runtime_feedback_summary.v1",
        "runtime_report_count",
    ),
    "research_continuity_summary": (
        "scion.postrun_research_continuity_summary.v1",
        "continuity_report_count",
    ),
}


class PostrunReviewInputAcceptancePort:
    """Validate generic summaries consumed by problem-owned postrun reviews."""

    @staticmethod
    def summary_keys() -> set[str]:
        return set(REVIEW_INPUT_SUMMARY_SPECS)

    def summarize(
        self,
        *,
        problem_family: str | None,
        interpretation: str,
        analysis_brief: Mapping[str, Any],
        expected_summaries: Mapping[str, Mapping[str, Any]],
        required_summary_keys: set[str],
        enabled: bool = True,
    ) -> PostrunAcceptanceCheckBundle:
        if not enabled:
            return PostrunAcceptanceCheckBundle(
                checks=(
                    PostrunAcceptanceCheck(
                        name="review_input_summaries_actionability",
                        status="skipped",
                        required=False,
                        detail={
                            "reason": "not_problem_specific_agentic_summary",
                            "problem_family": problem_family,
                        },
                    ),
                )
            )

        details = []
        for key, (schema, count_field) in REVIEW_INPUT_SUMMARY_SPECS.items():
            required_for_interpretation = key in required_summary_keys
            summary = _mapping_or_empty(analysis_brief.get(key))
            expected = _mapping_or_empty(expected_summaries.get(key))
            details.append(
                _review_input_summary_detail(
                    key=key,
                    schema=schema,
                    count_field=count_field,
                    required_for_interpretation=required_for_interpretation,
                    summary=summary,
                    expected=expected,
                )
            )

        status = "ok" if all(not item["failures"] for item in details) else "failed"
        return PostrunAcceptanceCheckBundle(
            checks=(
                PostrunAcceptanceCheck(
                    name="review_input_summaries_actionability",
                    status=status,
                    detail={
                        "problem_family": problem_family,
                        "interpretation": interpretation,
                        "summaries": details,
                    },
                ),
            )
        )


def _review_input_summary_detail(
    *,
    key: str,
    schema: str,
    count_field: str,
    required_for_interpretation: bool,
    summary: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    count_value = _int_or_zero(summary.get(count_field))
    expected_count_value = _int_or_zero(expected.get(count_field))
    summary_present = (
        summary.get("available") is True
        or _int_or_zero(summary.get("report_count")) > 0
        or summary.get("schema_version") is not None
    )
    expected_present = (
        expected.get("available") is True
        or _int_or_zero(expected.get("report_count")) > 0
        or expected_count_value > 0
    )
    consistency_required = (
        required_for_interpretation or summary_present or expected_present
    )

    failures: list[str] = []
    if (required_for_interpretation or summary_present) and (
        summary.get("schema_version") != schema
    ):
        failures.append(f"{key}_schema_stale")
    if (required_for_interpretation or summary_present) and (
        summary.get("report_only") is not True
    ):
        failures.append(f"{key}_not_report_only")
    if (required_for_interpretation or summary_present) and (
        summary.get("quality_judgment") is not False
    ):
        failures.append(f"{key}_quality_judgment_not_false")
    if (required_for_interpretation or summary_present) and (
        summary.get("decision_features_excluded") is not True
    ):
        failures.append(f"{key}_decision_features_not_excluded")
    if (required_for_interpretation or summary_present) and (
        summary.get("current_run_evidence") is not True
    ):
        failures.append(f"{key}_not_current_run_evidence")
    if required_for_interpretation and summary.get("available") is not True:
        failures.append(f"{key}_unavailable")
    if required_for_interpretation and _int_or_zero(summary.get("report_count")) <= 0:
        failures.append(f"{key}_report_count_missing")
    if required_for_interpretation and count_value <= 0:
        failures.append(f"{key}_{count_field}_missing")
    if key == "runtime_feedback_summary" and required_for_interpretation:
        if summary.get("drain_status_complete") is not True:
            failures.append("runtime_feedback_summary_drain_status_incomplete")
        if summary.get("review_ready") is not True:
            failures.append("runtime_feedback_summary_not_review_ready")

    consistency_failures: list[str] = []
    if consistency_required:
        consistency_failures = _review_input_summary_consistency_failures(
            key=key,
            summary=summary,
            expected=expected,
            count_field=count_field,
        )
        failures.extend(consistency_failures)

    return {
        "summary": key,
        "required_for_interpretation": required_for_interpretation,
        "failures": failures,
        "consistency_failures": consistency_failures,
        "schema_version": summary.get("schema_version"),
        "expected_schema_version": schema,
        "report_only": summary.get("report_only"),
        "quality_judgment": summary.get("quality_judgment"),
        "decision_features_excluded": summary.get("decision_features_excluded"),
        "current_run_evidence": summary.get("current_run_evidence"),
        "expected_current_run_evidence": expected.get("current_run_evidence"),
        "available": summary.get("available"),
        "expected_available": expected.get("available"),
        "report_count": summary.get("report_count"),
        "expected_report_count": expected.get("report_count"),
        count_field: summary.get(count_field),
        f"expected_{count_field}": expected_count_value,
        "drain_status_complete": summary.get("drain_status_complete"),
        "expected_drain_status_complete": expected.get("drain_status_complete"),
        "review_ready": summary.get("review_ready"),
        "expected_review_ready": expected.get("review_ready"),
    }


def _review_input_summary_consistency_failures(
    *,
    key: str,
    summary: Mapping[str, Any],
    expected: Mapping[str, Any],
    count_field: str,
) -> list[str]:
    failures: list[str] = []
    for field in (
        "current_run_evidence",
        "available",
        "report_count",
        count_field,
    ):
        if summary.get(field) != expected.get(field):
            failures.append(f"{key}_{field}_mismatch")
    if key == "runtime_feedback_summary":
        for field in (
            "drain_status_complete",
            "review_ready",
            "budget_diagnostic_source_count",
        ):
            if summary.get(field) != expected.get(field):
                failures.append(f"{key}_{field}_mismatch")
    if _summary_without_paths(summary.get("aggregate")) != _summary_without_paths(
        expected.get("aggregate")
    ):
        failures.append(f"{key}_aggregate_mismatch")
    if _summary_without_paths(summary.get("entries")) != _summary_without_paths(
        expected.get("entries")
    ):
        failures.append(f"{key}_entries_mismatch")
    if key == "runtime_feedback_summary" and _summary_without_paths(
        summary.get("runtime_budget_diagnostics")
    ) != _summary_without_paths(expected.get("runtime_budget_diagnostics")):
        failures.append("runtime_feedback_summary_budget_diagnostics_mismatch")
    return failures


def _summary_without_paths(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                _path_tail_signature(item)
                if str(key) == "path"
                else _summary_without_paths(item)
            )
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_summary_without_paths(item) for item in value]
    return _json_comparison_value(value)


def _path_tail_signature(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return _json_comparison_value(value)
    normalized = value.replace("\\", "/")
    parts = [part for part in PurePosixPath(normalized).parts if part not in {"", "/"}]
    return {"path_tail": parts[-4:]}


def _json_comparison_value(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True))
    except (TypeError, ValueError):
        return str(value)


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "PostrunReviewInputAcceptancePort",
    "REVIEW_INPUT_SUMMARY_SPECS",
]
