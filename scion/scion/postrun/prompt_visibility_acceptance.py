"""Generic prompt/source visibility acceptance checks."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any, Mapping

from scion.postrun.acceptance_checks import (
    PostrunAcceptanceCheck,
    PostrunAcceptanceCheckBundle,
)
from scion.postrun.opportunity_visibility import (
    PROBLEM_OPPORTUNITY_VISIBILITY_SCHEMA,
    problem_opportunity_visibility_signature,
)


PROMPT_CONTEXT_VISIBILITY_SCHEMA = (
    "scion.postrun_prompt_context_visibility_summary.v1"
)
PROMPT_SOURCE_VISIBILITY_SCHEMA = "scion.postrun_prompt_source_visibility_summary.v1"
PROMPT_SIGNAL_DENSITY_SCHEMA = "scion.postrun_prompt_signal_density.v1"


class PostrunPromptVisibilityAcceptancePort:
    """Validate prompt visibility envelopes without problem-specific semantics."""

    def summarize(
        self,
        *,
        problem_family: str | None,
        summary: Mapping[str, Any],
        expected: Mapping[str, Any],
        active_subject_failure_prefix: str | None = None,
        enabled: bool = True,
    ) -> PostrunAcceptanceCheckBundle:
        if not enabled:
            return PostrunAcceptanceCheckBundle(
                checks=(
                    PostrunAcceptanceCheck(
                        name="prompt_source_visibility_actionability",
                        status="skipped",
                        required=False,
                        detail={
                            "reason": "not_problem_specific_agentic_summary",
                            "problem_family": problem_family,
                        },
                    ),
                )
            )

        status, detail = _prompt_source_visibility_actionability(
            problem_family=problem_family,
            summary=summary,
            expected=expected,
            active_subject_failure_prefix=active_subject_failure_prefix,
        )
        return PostrunAcceptanceCheckBundle(
            checks=(
                PostrunAcceptanceCheck(
                    name="prompt_source_visibility_actionability",
                    status=status,
                    detail=detail,
                ),
            )
        )


def _prompt_source_visibility_actionability(
    *,
    problem_family: str | None,
    summary: Mapping[str, Any],
    expected: Mapping[str, Any],
    active_subject_failure_prefix: str | None,
) -> tuple[str, dict[str, Any]]:
    summary = _mapping_or_empty(summary)
    expected = _mapping_or_empty(expected)
    aggregate = _mapping_or_empty(summary.get("aggregate"))
    source_visibility = _mapping_or_empty(aggregate.get("source_visibility"))
    opportunity_visibility = _mapping_or_empty(
        aggregate.get("problem_opportunity_visibility")
    )
    call_kind_counts = _mapping_or_empty(aggregate.get("call_kind_counts"))
    hypothesis_density = _mapping_or_empty(
        aggregate.get("hypothesis_generation_signal_density")
    )
    expected_aggregate = _mapping_or_empty(expected.get("aggregate"))
    expected_source_visibility = _mapping_or_empty(
        expected_aggregate.get("source_visibility")
    )
    expected_density = _mapping_or_empty(expected_aggregate.get("signal_density"))
    expected_hypothesis_density = _mapping_or_empty(
        expected_aggregate.get("hypothesis_generation_signal_density")
    )

    failures: list[str] = []
    if summary.get("schema_version") != PROMPT_CONTEXT_VISIBILITY_SCHEMA:
        failures.append("prompt_context_visibility_schema_stale")
    failures.extend(
        _boundary_marker_failures("prompt_context_visibility", summary)
    )
    for excluded_field in (
        "raw_prompt_excluded",
        "raw_response_excluded",
        "patch_body_excluded",
    ):
        if summary.get(excluded_field) is not True:
            failures.append(f"prompt_context_visibility_{excluded_field}_not_true")
    if source_visibility.get("schema_version") != PROMPT_SOURCE_VISIBILITY_SCHEMA:
        failures.append("prompt_source_visibility_schema_stale")
    failures.extend(
        _boundary_marker_failures(
            "prompt_source_visibility",
            source_visibility,
            require_quality=False,
        )
    )
    if opportunity_visibility and opportunity_visibility.get("schema_version") != (
        PROBLEM_OPPORTUNITY_VISIBILITY_SCHEMA
    ):
        failures.append("problem_opportunity_visibility_schema_stale")
    failures.extend(
        _boundary_marker_failures(
            "problem_opportunity_visibility",
            opportunity_visibility,
            require_quality=False,
        )
    )
    if summary.get("current_run_evidence") is not True:
        failures.append("prompt_context_not_current_run_evidence")
    if summary.get("available") is not True:
        failures.append("prompt_context_visibility_summary_unavailable")
    if _int_or_zero(aggregate.get("trace_count")) <= 0:
        failures.append("prompt_context_trace_accounting_missing")
    if _int_or_zero(source_visibility.get("trace_count")) <= 0:
        failures.append("prompt_source_visibility_trace_accounting_missing")

    target_intent_required = _target_intent_source_visibility_required(
        source_visibility,
        call_kind_counts,
    )
    _append_target_source_failures(
        failures,
        source_visibility=source_visibility,
        target_intent_source_visibility_required=target_intent_required,
    )
    code_trace_count = _append_code_source_failures(failures, source_visibility)
    if active_subject_failure_prefix and code_trace_count > 0:
        _append_active_subject_failures(
            failures,
            source_visibility=source_visibility,
            failure_prefix=active_subject_failure_prefix,
        )

    consistency_failures = _prompt_context_visibility_consistency_failures(
        summary=summary,
        expected=expected,
    )
    failures.extend(consistency_failures)
    return (
        "ok" if not failures else "failed",
        {
            "problem_family": problem_family,
            "failures": failures,
            "consistency_failures": consistency_failures,
            "current_run_evidence": summary.get("current_run_evidence"),
            "expected_current_run_evidence": expected.get("current_run_evidence"),
            "schema_version": summary.get("schema_version"),
            "expected_schema_version": PROMPT_CONTEXT_VISIBILITY_SCHEMA,
            "report_only": summary.get("report_only"),
            "quality_judgment": summary.get("quality_judgment"),
            "decision_features_excluded": summary.get("decision_features_excluded"),
            "raw_prompt_excluded": summary.get("raw_prompt_excluded"),
            "raw_response_excluded": summary.get("raw_response_excluded"),
            "patch_body_excluded": summary.get("patch_body_excluded"),
            "available": summary.get("available"),
            "expected_available": expected.get("available"),
            "manifest_report_count": summary.get("manifest_report_count"),
            "target_intent_trace_count": _int_or_zero(
                call_kind_counts.get("hypothesis_target_intent")
            ),
            "target_intent_source_visibility_required": target_intent_required,
            "expected_manifest_report_count": expected.get("manifest_report_count"),
            "context_report_count": summary.get("context_report_count"),
            "expected_context_report_count": expected.get("context_report_count"),
            "trace_count": aggregate.get("trace_count"),
            "expected_trace_count": expected_aggregate.get("trace_count"),
            "visibility_digest_count": aggregate.get("visibility_digest_count"),
            "expected_visibility_digest_count": expected_aggregate.get(
                "visibility_digest_count"
            ),
            "block_family_trace_count": aggregate.get("block_family_trace_count"),
            "expected_block_family_trace_count": expected_aggregate.get(
                "block_family_trace_count"
            ),
            "hypothesis_generation_trace_count": aggregate.get(
                "hypothesis_generation_trace_count"
            ),
            "expected_hypothesis_generation_trace_count": expected_aggregate.get(
                "hypothesis_generation_trace_count"
            ),
            "hypothesis_generation_block_family_trace_count": aggregate.get(
                "hypothesis_generation_block_family_trace_count"
            ),
            "expected_hypothesis_generation_block_family_trace_count": (
                expected_aggregate.get("hypothesis_generation_block_family_trace_count")
            ),
            "call_kind_counts": aggregate.get("call_kind_counts"),
            "expected_call_kind_counts": expected_aggregate.get("call_kind_counts"),
            "source_visibility_schema_version": source_visibility.get(
                "schema_version"
            ),
            "source_visibility_report_only": source_visibility.get("report_only"),
            "source_visibility_decision_features_excluded": source_visibility.get(
                "decision_features_excluded"
            ),
            "source_visibility_trace_count": source_visibility.get("trace_count"),
            "expected_source_visibility_trace_count": (
                expected_source_visibility.get("trace_count")
            ),
            "code_trace_count": source_visibility.get("code_trace_count"),
            "expected_code_trace_count": expected_source_visibility.get(
                "code_trace_count"
            ),
            "code_protected_source_visible_count": source_visibility.get(
                "code_protected_source_visible_count"
            ),
            "expected_code_protected_source_visible_count": (
                expected_source_visibility.get("code_protected_source_visible_count")
            ),
            "code_protected_source_missing_count": source_visibility.get(
                "code_protected_source_missing_count"
            ),
            "expected_code_protected_source_missing_count": (
                expected_source_visibility.get("code_protected_source_missing_count")
            ),
            "code_missing_required_source_trace_count": source_visibility.get(
                "code_missing_required_source_trace_count"
            ),
            "expected_code_missing_required_source_trace_count": (
                expected_source_visibility.get(
                    "code_missing_required_source_trace_count"
                )
            ),
            "code_missing_required_source_path_counts": source_visibility.get(
                "code_missing_required_source_path_counts"
            ),
            "expected_code_missing_required_source_path_counts": (
                expected_source_visibility.get(
                    "code_missing_required_source_path_counts"
                )
            ),
            "active_subject_code_constraints_trace_count": source_visibility.get(
                "active_subject_code_constraints_trace_count"
            ),
            "expected_active_subject_code_constraints_trace_count": (
                expected_source_visibility.get(
                    "active_subject_code_constraints_trace_count"
                )
            ),
            "active_subject_code_constraints_required_count": source_visibility.get(
                "active_subject_code_constraints_required_count"
            ),
            "expected_active_subject_code_constraints_required_count": (
                expected_source_visibility.get(
                    "active_subject_code_constraints_required_count"
                )
            ),
            "active_subject_code_constraints_full_visible_count": (
                source_visibility.get(
                    "active_subject_code_constraints_full_visible_count"
                )
            ),
            "expected_active_subject_code_constraints_full_visible_count": (
                expected_source_visibility.get(
                    "active_subject_code_constraints_full_visible_count"
                )
            ),
            "active_subject_code_constraints_not_full_visible_count": (
                source_visibility.get(
                    "active_subject_code_constraints_not_full_visible_count"
                )
            ),
            "expected_active_subject_code_constraints_not_full_visible_count": (
                expected_source_visibility.get(
                    "active_subject_code_constraints_not_full_visible_count"
                )
            ),
            "active_subject_code_constraints_status_counts": source_visibility.get(
                "active_subject_code_constraints_status_counts"
            ),
            "expected_active_subject_code_constraints_status_counts": (
                expected_source_visibility.get(
                    "active_subject_code_constraints_status_counts"
                )
            ),
            "hypothesis_target_source_trace_count": source_visibility.get(
                "hypothesis_target_source_trace_count"
            ),
            "expected_hypothesis_target_source_trace_count": (
                expected_source_visibility.get("hypothesis_target_source_trace_count")
            ),
            "hypothesis_target_source_required_count": source_visibility.get(
                "hypothesis_target_source_required_count"
            ),
            "expected_hypothesis_target_source_required_count": (
                expected_source_visibility.get(
                    "hypothesis_target_source_required_count"
                )
            ),
            "hypothesis_target_source_visible_count": source_visibility.get(
                "hypothesis_target_source_visible_count"
            ),
            "expected_hypothesis_target_source_visible_count": (
                expected_source_visibility.get(
                    "hypothesis_target_source_visible_count"
                )
            ),
            "hypothesis_target_source_not_visible_count": source_visibility.get(
                "hypothesis_target_source_not_visible_count"
            ),
            "expected_hypothesis_target_source_not_visible_count": (
                expected_source_visibility.get(
                    "hypothesis_target_source_not_visible_count"
                )
            ),
            "signal_density_total_token_estimate": _mapping_or_empty(
                aggregate.get("signal_density")
            ).get("total_token_estimate"),
            "expected_signal_density_total_token_estimate": (
                expected_density.get("total_token_estimate")
            ),
            "signal_density_interpretation": _mapping_or_empty(
                aggregate.get("signal_density")
            ).get("interpretation"),
            "expected_signal_density_interpretation": expected_density.get(
                "interpretation"
            ),
            "hypothesis_generation_signal_density_total_token_estimate": (
                hypothesis_density.get("total_token_estimate")
            ),
            "expected_hypothesis_generation_signal_density_total_token_estimate": (
                expected_hypothesis_density.get("total_token_estimate")
            ),
            "hypothesis_generation_signal_density_interpretation": (
                hypothesis_density.get("interpretation")
            ),
            "expected_hypothesis_generation_signal_density_interpretation": (
                expected_hypothesis_density.get("interpretation")
            ),
        },
    )


def _target_intent_source_visibility_required(
    source_visibility: Mapping[str, Any],
    call_kind_counts: Mapping[str, Any],
) -> bool:
    return (
        _int_or_zero(call_kind_counts.get("hypothesis_target_intent")) > 0
        or _int_or_zero(
            source_visibility.get("hypothesis_target_source_required_count")
        )
        > 0
    )


def _append_target_source_failures(
    failures: list[str],
    *,
    source_visibility: Mapping[str, Any],
    target_intent_source_visibility_required: bool,
) -> None:
    required_count = _int_or_zero(
        source_visibility.get("hypothesis_target_source_required_count")
    )
    visible_count = _int_or_zero(
        source_visibility.get("hypothesis_target_source_visible_count")
    )
    if (
        target_intent_source_visibility_required
        and _int_or_zero(
            source_visibility.get("hypothesis_target_source_trace_count")
        )
        <= 0
    ):
        failures.append("hypothesis_target_source_visibility_trace_missing")
    elif target_intent_source_visibility_required and visible_count <= 0:
        failures.append("hypothesis_target_source_visibility_not_visible")
    if required_count > 0 and visible_count < required_count:
        failures.append("hypothesis_target_required_source_not_fully_visible")


def _append_code_source_failures(
    failures: list[str],
    source_visibility: Mapping[str, Any],
) -> int:
    code_trace_count = _int_or_zero(source_visibility.get("code_trace_count"))
    if code_trace_count <= 0:
        return code_trace_count
    protected_visible_count = _int_or_zero(
        source_visibility.get("code_protected_source_visible_count")
    )
    missing_required_count = _int_or_zero(
        source_visibility.get("code_missing_required_source_trace_count")
    )
    if protected_visible_count < code_trace_count:
        failures.append("code_protected_source_visibility_not_full")
    if missing_required_count > 0:
        failures.append("code_missing_required_source_visibility")
    return code_trace_count


def _append_active_subject_failures(
    failures: list[str],
    *,
    source_visibility: Mapping[str, Any],
    failure_prefix: str,
) -> None:
    trace_count = _int_or_zero(
        source_visibility.get("active_subject_code_constraints_trace_count")
    )
    required_count = _int_or_zero(
        source_visibility.get("active_subject_code_constraints_required_count")
    )
    full_visible_count = _int_or_zero(
        source_visibility.get("active_subject_code_constraints_full_visible_count")
    )
    if trace_count <= 0:
        failures.append(f"{failure_prefix}_active_subject_code_constraints_trace_missing")
    if required_count <= 0:
        failures.append(f"{failure_prefix}_active_subject_code_constraints_not_required")
    if (required_count <= 0 and full_visible_count <= 0) or (
        required_count > 0 and full_visible_count < required_count
    ):
        failures.append(
            f"{failure_prefix}_active_subject_code_constraints_not_full_visible"
        )


def _prompt_context_visibility_consistency_failures(
    *,
    summary: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    for field in (
        "current_run_evidence",
        "available",
        "manifest_report_count",
        "context_report_count",
    ):
        if summary.get(field) != expected.get(field):
            failures.append(f"prompt_context_visibility_{field}_mismatch")

    aggregate = _mapping_or_empty(summary.get("aggregate"))
    expected_aggregate = _mapping_or_empty(expected.get("aggregate"))
    for field in (
        "prompt_manifest_ref_count",
        "prompt_manifest_loaded_count",
        "trace_count",
        "visibility_digest_count",
        "block_family_trace_count",
        "hypothesis_generation_trace_count",
        "hypothesis_generation_block_family_trace_count",
        "omitted_section_trace_count",
        "truncated_section_trace_count",
    ):
        if _int_or_zero(aggregate.get(field)) != _int_or_zero(
            expected_aggregate.get(field)
        ):
            failures.append(f"prompt_context_visibility_{field}_mismatch")

    for field in (
        "call_kind_counts",
        "omitted_section_counts",
        "truncated_section_counts",
    ):
        if _int_mapping(aggregate.get(field)) != _int_mapping(
            expected_aggregate.get(field)
        ):
            failures.append(f"prompt_context_visibility_{field}_mismatch")

    if _block_family_totals_signature(
        aggregate.get("block_family_totals")
    ) != _block_family_totals_signature(expected_aggregate.get("block_family_totals")):
        failures.append("prompt_context_visibility_block_family_totals_mismatch")
    if _block_family_totals_signature(
        aggregate.get("hypothesis_generation_block_family_totals")
    ) != _block_family_totals_signature(
        expected_aggregate.get("hypothesis_generation_block_family_totals")
    ):
        failures.append(
            "prompt_context_visibility_hypothesis_generation_block_family_totals_mismatch"
        )

    failures.extend(
        _prompt_source_visibility_consistency_failures(
            _mapping_or_empty(aggregate.get("source_visibility")),
            _mapping_or_empty(expected_aggregate.get("source_visibility")),
        )
    )
    failures.extend(
        _prompt_signal_density_consistency_failures(
            _mapping_or_empty(aggregate.get("signal_density")),
            _mapping_or_empty(expected_aggregate.get("signal_density")),
        )
    )
    failures.extend(
        _prompt_signal_density_consistency_failures(
            _mapping_or_empty(aggregate.get("hypothesis_generation_signal_density")),
            _mapping_or_empty(
                expected_aggregate.get("hypothesis_generation_signal_density")
            ),
            prefix="prompt_hypothesis_generation_signal_density",
        )
    )
    if problem_opportunity_visibility_signature(
        aggregate.get("problem_opportunity_visibility")
    ) != problem_opportunity_visibility_signature(
        expected_aggregate.get("problem_opportunity_visibility")
    ):
        failures.append("prompt_context_visibility_problem_opportunity_mismatch")
    if _prompt_context_entries_signature(summary.get("entries")) != (
        _prompt_context_entries_signature(expected.get("entries"))
    ):
        failures.append("prompt_context_visibility_entries_mismatch")
    return failures


def prompt_context_visibility_consistency_failures(
    *,
    summary: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    """Return stable mismatch keys for prompt visibility summary drift."""

    return _prompt_context_visibility_consistency_failures(
        summary=summary,
        expected=expected,
    )


def _prompt_source_visibility_consistency_failures(
    source_visibility: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    for field in (
        "trace_count",
        "code_trace_count",
        "code_target_source_visible_count",
        "code_target_source_missing_count",
        "code_protected_source_visible_count",
        "code_protected_source_missing_count",
        "code_required_integration_source_visible_count",
        "code_algorithm_file_read_source_visible_count",
        "code_missing_required_source_trace_count",
        "hypothesis_target_source_trace_count",
        "hypothesis_target_source_required_count",
        "hypothesis_target_source_visible_count",
        "hypothesis_target_source_not_visible_count",
        "active_subject_code_constraints_trace_count",
        "active_subject_code_constraints_required_count",
        "active_subject_code_constraints_full_visible_count",
        "active_subject_code_constraints_partial_visible_count",
        "active_subject_code_constraints_not_full_visible_count",
        "active_subject_code_constraints_not_required_count",
        "active_subject_code_constraints_constraint_count_total",
        "active_subject_code_constraints_forbidden_pattern_count_total",
    ):
        if _int_or_zero(source_visibility.get(field)) != _int_or_zero(
            expected.get(field)
        ):
            failures.append(f"prompt_source_visibility_{field}_mismatch")
    for field in (
        "code_missing_required_source_path_counts",
        "code_target_source_status_counts",
        "code_target_visibility_status_counts",
        "hypothesis_target_visibility_status_counts",
        "active_subject_code_constraints_status_counts",
        "active_subject_code_constraints_missing_reason_counts",
    ):
        if _int_mapping(source_visibility.get(field)) != _int_mapping(
            expected.get(field)
        ):
            failures.append(f"prompt_source_visibility_{field}_mismatch")
    return failures


def _prompt_signal_density_consistency_failures(
    density: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    prefix: str = "prompt_signal_density",
) -> list[str]:
    failures: list[str] = []
    for field in (
        "total_token_estimate",
        "research_signal_tokens",
        "source_code_tokens",
        "cross_branch_tokens",
        "governance_tokens",
    ):
        if _int_or_zero(density.get(field)) != _int_or_zero(expected.get(field)):
            failures.append(f"{prefix}_{field}_mismatch")
    for field in (
        "research_signal_share",
        "source_code_share",
        "cross_branch_share",
        "governance_share",
        "research_plus_source_to_governance_ratio",
    ):
        if not _numeric_or_value_equal(density.get(field), expected.get(field)):
            failures.append(f"{prefix}_{field}_mismatch")
    if density.get("interpretation") != expected.get("interpretation"):
        failures.append(f"{prefix}_interpretation_mismatch")
    return failures


def _prompt_context_entries_signature(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    entries: list[dict[str, Any]] = []
    for raw in value:
        entry = _mapping_or_empty(raw)
        if not entry:
            continue
        entries.append(
            {
                "report": str(entry.get("report") or ""),
                "path": _path_tail_signature(entry.get("path")),
                "prompt_manifest_ref_count": _int_or_zero(
                    entry.get("prompt_manifest_ref_count")
                ),
                "prompt_manifest_loaded_count": _int_or_zero(
                    entry.get("prompt_manifest_loaded_count")
                ),
                "trace_count": _int_or_zero(entry.get("trace_count")),
                "visibility_digest_count": _int_or_zero(
                    entry.get("visibility_digest_count")
                ),
                "block_family_trace_count": _int_or_zero(
                    entry.get("block_family_trace_count")
                ),
                "hypothesis_generation_trace_count": _int_or_zero(
                    entry.get("hypothesis_generation_trace_count")
                ),
                "hypothesis_generation_block_family_trace_count": _int_or_zero(
                    entry.get("hypothesis_generation_block_family_trace_count")
                ),
                "omitted_section_trace_count": _int_or_zero(
                    entry.get("omitted_section_trace_count")
                ),
                "truncated_section_trace_count": _int_or_zero(
                    entry.get("truncated_section_trace_count")
                ),
                "call_kind_counts": _int_mapping(entry.get("call_kind_counts")),
                "block_family_totals": _block_family_totals_signature(
                    entry.get("block_family_totals")
                ),
                "hypothesis_generation_block_family_totals": (
                    _block_family_totals_signature(
                        entry.get("hypothesis_generation_block_family_totals")
                    )
                ),
                "omitted_section_counts": _int_mapping(
                    entry.get("omitted_section_counts")
                ),
                "truncated_section_counts": _int_mapping(
                    entry.get("truncated_section_counts")
                ),
                "source_visibility": _prompt_source_visibility_signature(
                    entry.get("source_visibility")
                ),
                "problem_opportunity_visibility": (
                    problem_opportunity_visibility_signature(
                        entry.get("problem_opportunity_visibility")
                    )
                ),
            }
        )
    return sorted(entries, key=lambda item: item["report"])


def _prompt_source_visibility_signature(value: Any) -> dict[str, Any]:
    source_visibility = _mapping_or_empty(value)
    return {
        "trace_count": _int_or_zero(source_visibility.get("trace_count")),
        "code_trace_count": _int_or_zero(source_visibility.get("code_trace_count")),
        "code_target_source_visible_count": _int_or_zero(
            source_visibility.get("code_target_source_visible_count")
        ),
        "code_target_source_missing_count": _int_or_zero(
            source_visibility.get("code_target_source_missing_count")
        ),
        "code_protected_source_visible_count": _int_or_zero(
            source_visibility.get("code_protected_source_visible_count")
        ),
        "code_protected_source_missing_count": _int_or_zero(
            source_visibility.get("code_protected_source_missing_count")
        ),
        "code_required_integration_source_visible_count": _int_or_zero(
            source_visibility.get("code_required_integration_source_visible_count")
        ),
        "code_algorithm_file_read_source_visible_count": _int_or_zero(
            source_visibility.get("code_algorithm_file_read_source_visible_count")
        ),
        "code_missing_required_source_trace_count": _int_or_zero(
            source_visibility.get("code_missing_required_source_trace_count")
        ),
        "code_missing_required_source_path_counts": _int_mapping(
            source_visibility.get("code_missing_required_source_path_counts")
        ),
        "code_target_source_status_counts": _int_mapping(
            source_visibility.get("code_target_source_status_counts")
        ),
        "code_target_visibility_status_counts": _int_mapping(
            source_visibility.get("code_target_visibility_status_counts")
        ),
        "hypothesis_target_source_trace_count": _int_or_zero(
            source_visibility.get("hypothesis_target_source_trace_count")
        ),
        "hypothesis_target_source_required_count": _int_or_zero(
            source_visibility.get("hypothesis_target_source_required_count")
        ),
        "hypothesis_target_source_visible_count": _int_or_zero(
            source_visibility.get("hypothesis_target_source_visible_count")
        ),
        "hypothesis_target_source_not_visible_count": _int_or_zero(
            source_visibility.get("hypothesis_target_source_not_visible_count")
        ),
        "hypothesis_target_visibility_status_counts": _int_mapping(
            source_visibility.get("hypothesis_target_visibility_status_counts")
        ),
        "active_subject_code_constraints_trace_count": _int_or_zero(
            source_visibility.get("active_subject_code_constraints_trace_count")
        ),
        "active_subject_code_constraints_required_count": _int_or_zero(
            source_visibility.get("active_subject_code_constraints_required_count")
        ),
        "active_subject_code_constraints_full_visible_count": _int_or_zero(
            source_visibility.get("active_subject_code_constraints_full_visible_count")
        ),
        "active_subject_code_constraints_partial_visible_count": _int_or_zero(
            source_visibility.get(
                "active_subject_code_constraints_partial_visible_count"
            )
        ),
        "active_subject_code_constraints_not_full_visible_count": _int_or_zero(
            source_visibility.get(
                "active_subject_code_constraints_not_full_visible_count"
            )
        ),
        "active_subject_code_constraints_not_required_count": _int_or_zero(
            source_visibility.get("active_subject_code_constraints_not_required_count")
        ),
        "active_subject_code_constraints_constraint_count_total": _int_or_zero(
            source_visibility.get(
                "active_subject_code_constraints_constraint_count_total"
            )
        ),
        "active_subject_code_constraints_forbidden_pattern_count_total": _int_or_zero(
            source_visibility.get(
                "active_subject_code_constraints_forbidden_pattern_count_total"
            )
        ),
        "active_subject_code_constraints_status_counts": _int_mapping(
            source_visibility.get("active_subject_code_constraints_status_counts")
        ),
        "active_subject_code_constraints_missing_reason_counts": _int_mapping(
            source_visibility.get(
                "active_subject_code_constraints_missing_reason_counts"
            )
        ),
    }


def _block_family_totals_signature(value: Any) -> dict[str, dict[str, int]]:
    if not isinstance(value, Mapping):
        return {}
    families: dict[str, dict[str, int]] = {}
    for family, raw in value.items():
        item = _mapping_or_empty(raw)
        if not item:
            continue
        families[str(family)] = {
            "trace_count": _int_or_zero(item.get("trace_count")),
            "char_count": _int_or_zero(item.get("char_count")),
            "token_estimate": _int_or_zero(item.get("token_estimate")),
        }
    return families


def _boundary_marker_failures(
    prefix: str,
    payload: Mapping[str, Any],
    *,
    require_quality: bool = True,
) -> list[str]:
    failures: list[str] = []
    if payload.get("report_only") is not True:
        failures.append(f"{prefix}_not_report_only")
    if require_quality and payload.get("quality_judgment") is not False:
        failures.append(f"{prefix}_quality_judgment_not_false")
    if payload.get("decision_features_excluded") is not True:
        failures.append(f"{prefix}_decision_features_not_excluded")
    return failures


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _int_or_zero(count) for key, count in value.items()}


def _numeric_or_value_equal(actual: Any, expected: Any) -> bool:
    try:
        return float(actual) == float(expected)
    except (TypeError, ValueError):
        return actual == expected


def _json_comparison_value(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True))
    except (TypeError, ValueError):
        return str(value)


def _path_tail_signature(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return _json_comparison_value(value)
    normalized = value.replace("\\", "/")
    parts = [part for part in PurePosixPath(normalized).parts if part not in {"", "/"}]
    return {"path_tail": parts[-4:]}


__all__ = [
    "PROMPT_CONTEXT_VISIBILITY_SCHEMA",
    "PROMPT_SIGNAL_DENSITY_SCHEMA",
    "PROMPT_SOURCE_VISIBILITY_SCHEMA",
    "PostrunPromptVisibilityAcceptancePort",
    "prompt_context_visibility_consistency_failures",
]
