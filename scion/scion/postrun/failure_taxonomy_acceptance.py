"""Generic failure taxonomy postrun acceptance checks."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any, Mapping


FAILURE_TAXONOMY_SCHEMA = "scion.postrun_failure_taxonomy_summary.v1"


def failure_taxonomy_actionability(
    *,
    problem_family: str | None,
    brief: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    summary = _mapping_or_empty(brief.get("failure_taxonomy_summary"))
    aggregate = _mapping_or_empty(summary.get("aggregate"))
    expected = _mapping_or_empty(expected)
    expected_aggregate = _mapping_or_empty(expected.get("aggregate"))
    proposal_quality = _mapping_or_empty(aggregate.get("proposal_quality"))
    entries = summary.get("entries")
    entry_count = len(entries) if isinstance(entries, list) else 0
    report_evidence_count = max(
        _int_or_zero(summary.get("failure_report_count")),
        entry_count,
    )
    run_validity_counts = _mapping_or_empty(
        aggregate.get("run_validity_status_counts")
    )
    failure_observation_counts = _mapping_or_empty(
        aggregate.get("failure_observation_counts")
    )
    proposal_attempts = _int_or_zero(
        proposal_quality.get("proposal_attempts_total")
    )
    report_evidence_available = (
        bool(run_validity_counts)
        or bool(failure_observation_counts)
        or proposal_attempts > 0
    )
    failures: list[str] = []
    if summary.get("schema_version") != FAILURE_TAXONOMY_SCHEMA:
        failures.append("failure_taxonomy_schema_stale")
    failures.extend(_boundary_marker_failures("failure_taxonomy", summary))
    if summary.get("raw_logs_excluded") is not True:
        failures.append("failure_taxonomy_raw_logs_excluded_not_true")
    if summary.get("current_run_evidence") is not True:
        failures.append("failure_taxonomy_not_current_run_evidence")
    if summary.get("available") is not True:
        failures.append("failure_taxonomy_unavailable")
    if _int_or_zero(summary.get("report_count")) <= 0:
        failures.append("failure_taxonomy_report_count_missing")
    if report_evidence_count <= 0:
        failures.append("failure_taxonomy_entry_missing")
    if not report_evidence_available:
        failures.append("failure_taxonomy_report_evidence_missing")
    consistency_failures = _failure_taxonomy_consistency_failures(
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
            "schema_version": summary.get("schema_version"),
            "expected_schema_version": FAILURE_TAXONOMY_SCHEMA,
            "current_run_evidence": summary.get("current_run_evidence"),
            "expected_current_run_evidence": expected.get("current_run_evidence"),
            "report_only": summary.get("report_only"),
            "quality_judgment": summary.get("quality_judgment"),
            "decision_features_excluded": summary.get("decision_features_excluded"),
            "raw_logs_excluded": summary.get("raw_logs_excluded"),
            "available": summary.get("available"),
            "expected_available": expected.get("available"),
            "report_count": summary.get("report_count"),
            "expected_report_count": expected.get("report_count"),
            "failure_report_count": summary.get("failure_report_count"),
            "expected_failure_report_count": expected.get("failure_report_count"),
            "entry_count": entry_count,
            "expected_entry_count": len(expected.get("entries") or []),
            "run_validity_status_counts": run_validity_counts,
            "expected_run_validity_status_counts": expected_aggregate.get(
                "run_validity_status_counts"
            ),
            "failure_observation_counts": failure_observation_counts,
            "expected_failure_observation_counts": expected_aggregate.get(
                "failure_observation_counts"
            ),
            "failure_count_maxima": aggregate.get("failure_count_maxima"),
            "expected_failure_count_maxima": expected_aggregate.get(
                "failure_count_maxima"
            ),
            "failure_source_counts": aggregate.get("failure_source_counts"),
            "expected_failure_source_counts": expected_aggregate.get(
                "failure_source_counts"
            ),
            "stopped_reason_counts": aggregate.get("stopped_reason_counts"),
            "expected_stopped_reason_counts": expected_aggregate.get(
                "stopped_reason_counts"
            ),
            "proposal_attempts_total": proposal_quality.get(
                "proposal_attempts_total"
            ),
            "expected_proposal_attempts_total": _mapping_or_empty(
                expected_aggregate.get("proposal_quality")
            ).get("proposal_attempts_total"),
            "proposal_quality_blocks": proposal_quality.get(
                "proposal_quality_blocks"
            ),
            "expected_proposal_quality_blocks": _mapping_or_empty(
                expected_aggregate.get("proposal_quality")
            ).get("proposal_quality_blocks"),
            "quality_blocks": proposal_quality.get("quality_blocks"),
            "expected_quality_blocks": _mapping_or_empty(
                expected_aggregate.get("proposal_quality")
            ).get("quality_blocks"),
            "quality_block_ledger_count": proposal_quality.get(
                "quality_block_ledger_count"
            ),
            "expected_quality_block_ledger_count": _mapping_or_empty(
                expected_aggregate.get("proposal_quality")
            ).get("quality_block_ledger_count"),
        },
    )


def _failure_taxonomy_consistency_failures(
    *,
    summary: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    for field in (
        "current_run_evidence",
        "available",
        "report_count",
        "failure_report_count",
    ):
        if summary.get(field) != expected.get(field):
            failures.append(f"failure_taxonomy_{field}_mismatch")

    aggregate = _mapping_or_empty(summary.get("aggregate"))
    expected_aggregate = _mapping_or_empty(expected.get("aggregate"))
    for field in (
        "failure_count_maxima",
        "failure_observation_counts",
        "failure_source_counts",
        "run_validity_status_counts",
        "stopped_reason_counts",
    ):
        if _int_mapping(aggregate.get(field)) != _int_mapping(
            expected_aggregate.get(field)
        ):
            failures.append(f"failure_taxonomy_{field}_mismatch")

    proposal = _mapping_or_empty(aggregate.get("proposal_quality"))
    expected_proposal = _mapping_or_empty(expected_aggregate.get("proposal_quality"))
    for field in (
        "proposal_attempts_total",
        "proposal_attempts_consumed",
        "proposal_quality_blocks",
        "quality_blocks",
        "quality_block_ledger_count",
        "reports_with_quality_blocks",
    ):
        if _int_or_zero(proposal.get(field)) != _int_or_zero(
            expected_proposal.get(field)
        ):
            failures.append(f"failure_taxonomy_{field}_mismatch")
    if _int_mapping(proposal.get("quality_block_reason_counts")) != _int_mapping(
        expected_proposal.get("quality_block_reason_counts")
    ):
        failures.append("failure_taxonomy_quality_block_reason_counts_mismatch")

    if _failure_taxonomy_entry_signature(summary.get("entries")) != (
        _failure_taxonomy_entry_signature(expected.get("entries"))
    ):
        failures.append("failure_taxonomy_entries_mismatch")
    if _failure_taxonomy_top_examples_signature(
        aggregate.get("top_examples")
    ) != _failure_taxonomy_top_examples_signature(expected_aggregate.get("top_examples")):
        failures.append("failure_taxonomy_top_examples_mismatch")
    return failures


def _failure_taxonomy_entry_signature(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    entries: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        entries.append(
            {
                "report": str(item.get("report") or ""),
                "path": _path_tail_signature(item.get("path")),
                "proposal_quality": _failure_taxonomy_proposal_signature(
                    item.get("proposal_quality")
                ),
                "failure_taxonomy": _json_comparison_value(
                    _mapping_or_empty(item.get("failure_taxonomy"))
                ),
                "failure_observations_total": _int_or_zero(
                    item.get("failure_observations_total")
                ),
                "top_failure_keys": _string_list(item.get("top_failure_keys")),
                "top_examples": _failure_taxonomy_top_examples_signature(
                    item.get("top_examples")
                ),
                "run_status": _failure_taxonomy_run_status_signature(
                    item.get("run_status")
                ),
            }
        )
    return sorted(entries, key=lambda entry: entry["report"])


def _failure_taxonomy_proposal_signature(value: Any) -> dict[str, Any]:
    proposal = _mapping_or_empty(value)
    return {
        "proposal_attempts_total": _int_or_zero(
            proposal.get("proposal_attempts_total")
        ),
        "proposal_attempts_consumed": _int_or_zero(
            proposal.get("proposal_attempts_consumed")
        ),
        "proposal_quality_blocks": _int_or_zero(
            proposal.get("proposal_quality_blocks")
        ),
        "quality_blocks": _int_or_zero(proposal.get("quality_blocks")),
        "quality_block_ledger_count": _int_or_zero(
            proposal.get("quality_block_ledger_count")
        ),
        "quality_block_reasons": _string_list(proposal.get("quality_block_reasons")),
        "semantics": str(proposal.get("semantics") or ""),
    }


def _failure_taxonomy_run_status_signature(value: Any) -> dict[str, Any]:
    status = _mapping_or_empty(value)
    return {
        "run_validity_status": str(status.get("run_validity_status") or ""),
        "stopped_reason": str(status.get("stopped_reason") or ""),
        "run_complete": status.get("run_complete"),
        "run_completeness_status": str(status.get("run_completeness_status") or ""),
        "wrapper_exit_status": _int_or_none(status.get("wrapper_exit_status")),
        "campaign_exit_status": _int_or_none(status.get("campaign_exit_status")),
    }


def _failure_taxonomy_top_examples_signature(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    examples: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        examples.append(
            {
                "report": str(item.get("report") or ""),
                "failure_key": str(item.get("failure_key") or ""),
                "example": str(item.get("example") or ""),
            }
        )
    return sorted(
        examples,
        key=lambda item: (item["report"], item["failure_key"], item["example"]),
    )

def _boundary_marker_failures(
    prefix: str,
    summary: Mapping[str, Any],
    *,
    require_quality: bool = True,
) -> list[str]:
    failures: list[str] = []
    if summary.get("report_only") is not True:
        failures.append(f"{prefix}_not_report_only")
    if require_quality and summary.get("quality_judgment") is not False:
        failures.append(f"{prefix}_quality_judgment_not_false")
    if summary.get("decision_features_excluded") is not True:
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
    return {str(key): _int_or_zero(count) for key, count in sorted(value.items())}


def _json_comparison_value(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def _path_tail_signature(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return _json_comparison_value(value)
    normalized = value.replace("\\", "/")
    parts = [part for part in PurePosixPath(normalized).parts if part not in {"", "/"}]
    return {"path_tail": parts[-4:]}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _numeric_or_value_equal(actual: Any, expected: Any) -> bool:
    if actual == expected:
        return True
    try:
        return abs(float(actual) - float(expected)) <= 1e-9
    except (TypeError, ValueError):
        return False


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    items: list[int] = []
    for item in value:
        parsed = _int_or_none(item)
        if parsed is not None:
            items.append(parsed)
    return items
