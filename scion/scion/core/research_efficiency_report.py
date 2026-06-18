"""Build postrun research-efficiency/accounting reports.

This module is report-only. It reads completed campaign artifacts and optional
wrapper logs, but it never mutates campaign, scheduler, protocol, promotion, or
Decision state.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from scion.core.evidence_recording.common import reduced_measurement_readiness_payload

SCHEMA_VERSION = "scion.research_efficiency_report.v1"
DEFAULT_REPORT_FILENAME = "research_efficiency_report.v1.json"
FORMAL_CANDIDATE_INDEX_REF = "artifacts/formal_candidates/index.jsonl"

_BOUNDARY_GUARDRAILS: dict[str, bool] = {
    "report_only": True,
    "decision_features_excluded": True,
    "comparison_is_decision_input": False,
    "campaign_state_mutated": False,
    "scheduler_state_mutated": False,
    "promotion_state_mutated": False,
    "protocol_gate_mutated": False,
    "campaign_execution_mutated": False,
}

_TAXONOMY_KEYS = (
    "verification_heavy",
    "code_generation",
    "agentic_proposal:code_generation_failed",
    "old_string_not_found",
    "stale_source",
    "tool_timeout",
    "abandon_fast_verification_heavy",
)
_ABANDON_FAST_RE = re.compile(
    r"abandon_fast after \d+ consecutive ['\"]verification_heavy['\"] failures",
    re.IGNORECASE,
)


def build_research_efficiency_report(
    campaign_dir: str | Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return a stable report-only research-efficiency/accounting JSON object."""

    input_path = Path(campaign_dir).expanduser().resolve()
    campaign_path, run_root = _resolve_campaign_path(input_path)
    summary = _read_json_object(campaign_path / "campaign_summary.json")
    status = _read_json_object(campaign_path / "status.json")
    wrapper_status = _read_json_object(campaign_path / "run_status.json")

    formal_index = campaign_path / FORMAL_CANDIDATE_INDEX_REF
    formal_index_counts = _count_formal_index_rows(formal_index)
    formal_artifact_count = _first_int(
        summary.get("formal_candidate_artifact_count"),
        status.get("formal_candidate_artifact_count"),
        _nested_int(summary, "formal_candidate_count_reconciliation", "formal_candidates_index_count"),
        _nested_int(status, "formal_candidate_count_reconciliation", "formal_candidates_index_count"),
        formal_index_counts["row_count"],
    )

    run_log_path = _find_run_log(input_path, campaign_path, run_root)
    steps = _list_value(summary.get("steps"))
    step_taxonomy = _classify_step_failures(steps)
    run_log_taxonomy = _classify_run_log(run_log_path)
    taxonomy = _merge_taxonomy(step_taxonomy, run_log_taxonomy)

    run_validity = _mapping_value(summary.get("run_validity")) or _mapping_value(
        status.get("run_validity")
    )
    stopped_reason = _first_str(
        summary.get("stopped_reason"),
        summary.get("last_stop_reason"),
        status.get("stopped_reason"),
        status.get("last_stop_reason"),
        wrapper_status.get("last_stop_reason"),
        wrapper_status.get("exit_reason"),
    )

    protocol_metric_stage_counts = _mapping_value(
        summary.get("protocol_metric_stage_counts")
    ) or _mapping_value(status.get("protocol_metric_stage_counts"))
    protocol_stage_counts = _mapping_value(summary.get("protocol_stage_counts")) or (
        _mapping_value(status.get("protocol_stage_counts"))
    )
    measurement_readiness = reduced_measurement_readiness_payload(
        summary.get("measurement_readiness")
    ) or reduced_measurement_readiness_payload(status.get("measurement_readiness"))
    cross_branch_observability = _mapping_value(
        summary.get("cross_branch_research_observability")
    ) or _mapping_value(status.get("cross_branch_research_observability"))
    research_shape_diagnostics = _mapping_value(
        cross_branch_observability.get("research_shape_diagnostics")
    )

    report = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "research_efficiency_report",
        "generated_at": generated_at or _utc_now_iso(),
        "campaign_dir": str(campaign_path),
        "input_dir": str(input_path),
        **_BOUNDARY_GUARDRAILS,
        "source_files": {
            "campaign_summary": _source_ref(campaign_path / "campaign_summary.json"),
            "status": _source_ref(campaign_path / "status.json"),
            "run_status": _source_ref(campaign_path / "run_status.json"),
            "formal_candidate_index": _source_ref(formal_index),
            "run_log": _source_ref(run_log_path),
        },
        "effective_budget": {
            "counter": _first_str(
                summary.get("max_rounds_budget_counter"),
                status.get("max_rounds_budget_counter"),
                "effective_rounds_completed",
            ),
            "requested_rounds": _first_int(
                summary.get("requested_rounds"), status.get("requested_rounds")
            ),
            "effective_rounds_completed": _first_int(
                summary.get("effective_rounds_completed"),
                status.get("effective_rounds_completed"),
                _nested_int(run_validity, "effective_rounds_completed"),
            ),
            "completed_requested_rounds": _first_bool(
                summary.get("completed_requested_rounds"),
                status.get("completed_requested_rounds"),
                wrapper_status.get("completed_requested_rounds"),
                _nested_value(run_validity, "completed_requested_rounds"),
            ),
            "stopped_reason": stopped_reason,
            "semantics": _first_str(
                summary.get("effective_rounds_completed_semantics"),
                status.get("effective_rounds_completed_semantics"),
                "budget counter; not equivalent to protocol rows, formal candidate artifacts, or failure count",
            ),
        },
        "attempts": {
            "proposal_attempts_total": _first_int(
                summary.get("proposal_attempts_total"),
                status.get("proposal_attempts_total"),
                summary.get("proposal_attempts"),
                status.get("proposal_attempts"),
            ),
            "proposal_attempts_consumed": _first_int(
                summary.get("proposal_attempts_consumed"),
                status.get("proposal_attempts_consumed"),
            ),
            "verification_consumed_candidates": _first_int(
                summary.get("verification_consumed_candidates"),
                status.get("verification_consumed_candidates"),
            ),
            "verification_failure_consumed_candidates": _first_int(
                summary.get("verification_failure_consumed_candidates"),
                status.get("verification_failure_consumed_candidates"),
            ),
        },
        "protocol_rows": {
            "effective_protocol_rounds": _first_int(
                summary.get("effective_protocol_rounds"),
                status.get("effective_protocol_rounds"),
            ),
            "protocol_metric_results": _first_int(
                summary.get("protocol_metric_results"),
                status.get("protocol_metric_results"),
            ),
            "protocol_evaluated_candidates": _first_int(
                summary.get("protocol_evaluated_candidates"),
                status.get("protocol_evaluated_candidates"),
            ),
            "stage_counts": dict(protocol_metric_stage_counts or protocol_stage_counts),
            "semantics": _first_str(
                summary.get("protocol_metric_results_semantics"),
                status.get("protocol_metric_results_semantics"),
                "completed protocol metric rows; excludes verification-only and proposal quality-block failures",
            ),
        },
        "formal_candidates": {
            "formal_screened_candidates": _first_int(
                summary.get("formal_screened_candidates"),
                status.get("formal_screened_candidates"),
            ),
            "protocol_evaluated_candidates": _first_int(
                summary.get("protocol_evaluated_candidates"),
                status.get("protocol_evaluated_candidates"),
            ),
            "semantics": _first_str(
                summary.get("formal_screened_candidates_semantics"),
                status.get("formal_screened_candidates_semantics"),
                "legacy formal screened counter; not equivalent to artifact row count",
            ),
        },
        "formal_candidate_artifacts": {
            "row_count": formal_artifact_count,
            "index_status": (
                "available"
                if formal_index_counts["exists"]
                else _first_str(
                    _nested_value(
                        summary,
                        "formal_candidate_count_reconciliation",
                        "formal_candidates_index_status",
                    ),
                    _nested_value(
                        status,
                        "formal_candidate_count_reconciliation",
                        "formal_candidates_index_status",
                    ),
                    "missing",
                )
            ),
            "index_ref": FORMAL_CANDIDATE_INDEX_REF if formal_index.exists() else "",
            "unreadable_rows": formal_index_counts["unreadable_rows"],
            "semantics": _first_str(
                summary.get("formal_candidate_artifact_count_semantics"),
                status.get("formal_candidate_artifact_count_semantics"),
                "formal_candidates/index.jsonl rows; replayable artifact rows are not experiment counts",
            ),
        },
        "stage_rows": {
            "screening": _first_int(
                summary.get("screening_protocol_results"),
                status.get("screening_protocol_results"),
                _mapping_int(protocol_metric_stage_counts, "screening"),
                _mapping_int(protocol_stage_counts, "screening"),
            ),
            "validation": _first_int(
                summary.get("validation_protocol_results"),
                status.get("validation_protocol_results"),
                _mapping_int(protocol_metric_stage_counts, "validation"),
                _mapping_int(protocol_stage_counts, "validation"),
            ),
            "frozen": _first_int(
                summary.get("frozen_protocol_results"),
                status.get("frozen_protocol_results"),
                _mapping_int(protocol_metric_stage_counts, "frozen"),
                _mapping_int(protocol_stage_counts, "frozen"),
            ),
            "fresh_runtime_replay": _first_int(
                summary.get("fresh_runtime_replay_protocol_results"),
                status.get("fresh_runtime_replay_protocol_results"),
            ),
        },
        "measurement_readiness": measurement_readiness or {},
        "research_shape": _compact_research_shape_diagnostics(
            research_shape_diagnostics
        ),
        "cross_branch_observability": _compact_cross_branch_observability(
            cross_branch_observability
        ),
        "fresh_runtime_replay_drain": {
            "attempts": _first_int(
                summary.get("fresh_runtime_replay_drain_attempts"),
                status.get("fresh_runtime_replay_drain_attempts"),
                _nested_int(summary, "fresh_runtime_replay_drain", "attempts"),
                _nested_int(status, "fresh_runtime_replay_drain", "attempts"),
            ),
            "executed": _first_int(
                summary.get("fresh_runtime_replay_drain_executed"),
                status.get("fresh_runtime_replay_drain_executed"),
                _nested_int(summary, "fresh_runtime_replay_drain", "executed"),
                _nested_int(status, "fresh_runtime_replay_drain", "executed"),
            ),
            "skipped": _first_int(
                summary.get("fresh_runtime_replay_drain_skipped"),
                status.get("fresh_runtime_replay_drain_skipped"),
                _nested_int(summary, "fresh_runtime_replay_drain", "skipped"),
                _nested_int(status, "fresh_runtime_replay_drain", "skipped"),
            ),
            "blocked": _first_int(
                summary.get("fresh_runtime_replay_drain_blocked_count"),
                status.get("fresh_runtime_replay_drain_blocked_count"),
                _nested_int(summary, "fresh_runtime_replay_drain", "blocked_count"),
                _nested_int(status, "fresh_runtime_replay_drain", "blocked_count"),
            ),
            "protocol_results": _first_int(
                summary.get("fresh_runtime_replay_protocol_results"),
                status.get("fresh_runtime_replay_protocol_results"),
            ),
            "stopped_reason": _first_str(
                summary.get("fresh_runtime_replay_drain_stopped_reason"),
                status.get("fresh_runtime_replay_drain_stopped_reason"),
                _nested_value(summary, "fresh_runtime_replay_drain", "stopped_reason"),
                _nested_value(status, "fresh_runtime_replay_drain", "stopped_reason"),
            ),
            "counts_toward_max_rounds": _first_bool(
                _nested_value(
                    summary,
                    "fresh_runtime_replay_drain",
                    "counts_toward_max_rounds",
                ),
                _nested_value(
                    status,
                    "fresh_runtime_replay_drain",
                    "counts_toward_max_rounds",
                ),
                False,
            ),
        },
        "stage_transition_drain": {
            "attempts": _first_int(
                summary.get("stage_transition_drain_attempts"),
                status.get("stage_transition_drain_attempts"),
                _nested_int(summary, "stage_transition_drain", "attempts"),
                _nested_int(status, "stage_transition_drain", "attempts"),
            ),
            "executed": _first_int(
                summary.get("stage_transition_drain_executed"),
                status.get("stage_transition_drain_executed"),
                _nested_int(summary, "stage_transition_drain", "executed"),
                _nested_int(status, "stage_transition_drain", "executed"),
            ),
            "skipped": _first_int(
                summary.get("stage_transition_drain_skipped"),
                status.get("stage_transition_drain_skipped"),
                _nested_int(summary, "stage_transition_drain", "skipped"),
                _nested_int(status, "stage_transition_drain", "skipped"),
            ),
            "limit": _first_int(
                summary.get("stage_transition_drain_limit"),
                status.get("stage_transition_drain_limit"),
                _nested_int(summary, "stage_transition_drain", "limit"),
                _nested_int(status, "stage_transition_drain", "limit"),
            ),
            "status": _first_str(
                summary.get("stage_transition_drain_status"),
                status.get("stage_transition_drain_status"),
                _nested_value(summary, "stage_transition_drain", "status"),
                _nested_value(status, "stage_transition_drain", "status"),
            ),
            "stopped_reason": _first_str(
                summary.get("stage_transition_drain_stopped_reason"),
                status.get("stage_transition_drain_stopped_reason"),
                _nested_value(summary, "stage_transition_drain", "stopped_reason"),
                _nested_value(status, "stage_transition_drain", "stopped_reason"),
            ),
            "counts_toward_max_rounds": _first_bool(
                _nested_value(
                    summary,
                    "stage_transition_drain",
                    "counts_toward_max_rounds",
                ),
                _nested_value(
                    status,
                    "stage_transition_drain",
                    "counts_toward_max_rounds",
                ),
                False,
            ),
            "generates_new_hypothesis": _first_bool(
                _nested_value(
                    summary,
                    "stage_transition_drain",
                    "generates_new_hypothesis",
                ),
                _nested_value(
                    status,
                    "stage_transition_drain",
                    "generates_new_hypothesis",
                ),
                False,
            ),
        },
        "proposal_quality": {
            "proposal_attempts_total": _first_int(
                summary.get("proposal_attempts_total"),
                status.get("proposal_attempts_total"),
                summary.get("proposal_attempts"),
                status.get("proposal_attempts"),
            ),
            "proposal_attempts_consumed": _first_int(
                summary.get("proposal_attempts_consumed"),
                status.get("proposal_attempts_consumed"),
            ),
            "proposal_quality_blocks": _first_int(
                summary.get("proposal_quality_blocks"),
                status.get("proposal_quality_blocks"),
                summary.get("quality_blocks"),
                status.get("quality_blocks"),
            ),
            "quality_blocks": _first_int(
                summary.get("quality_blocks"),
                status.get("quality_blocks"),
            ),
            "quality_block_ledger_count": _first_int(
                summary.get("quality_block_ledger_count"),
                status.get("quality_block_ledger_count"),
            ),
            "quality_block_reasons": _quality_block_reasons(summary, status),
            "semantics": _first_str(
                summary.get("proposal_quality_blocks_semantics"),
                status.get("proposal_quality_blocks_semantics"),
                "proposal/schema quality blocks before verification or protocol metrics",
            ),
        },
        "failures": {
            "verification_heavy": taxonomy["verification_heavy"],
            "code_generation": taxonomy["code_generation"],
            "tool_timeout": taxonomy["tool_timeout"],
            "non_fatal_agentic_code": taxonomy[
                "agentic_proposal:code_generation_failed"
            ],
        },
        "failure_taxonomy": taxonomy,
        "run_status": {
            "run_validity": run_validity,
            "run_validity_status": _first_str(
                summary.get("run_validity_status"),
                status.get("run_validity_status"),
                wrapper_status.get("run_validity_status"),
                _nested_value(run_validity, "status"),
            ),
            "stopped_reason": stopped_reason,
            "run_complete": _first_bool(
                summary.get("run_complete"),
                status.get("run_complete"),
                wrapper_status.get("run_complete"),
            ),
            "run_completeness_status": _first_str(
                summary.get("run_completeness_status"),
                status.get("run_completeness_status"),
                wrapper_status.get("run_completeness_status"),
            ),
            "wrapper_exit_status": _first_int(wrapper_status.get("wrapper_exit_status")),
            "campaign_exit_status": _first_str(wrapper_status.get("campaign_exit_status")),
        },
        "reconciliation": {
            "formal_candidate_count_reconciliation": _mapping_value(
                summary.get("formal_candidate_count_reconciliation")
            )
            or _mapping_value(status.get("formal_candidate_count_reconciliation")),
            "candidate_count_reconciliation": _mapping_value(
                summary.get("candidate_count_reconciliation")
            )
            or _mapping_value(status.get("candidate_count_reconciliation")),
            "accounting_reconciliation": _mapping_value(
                summary.get("accounting_reconciliation")
            )
            or _mapping_value(status.get("accounting_reconciliation")),
        },
    }
    return report


def write_research_efficiency_report(
    campaign_dir: str | Path,
    *,
    output_path: str | Path | None = None,
) -> Path:
    """Build and write a research-efficiency report JSON artifact."""

    campaign_path, _ = _resolve_campaign_path(Path(campaign_dir).expanduser().resolve())
    destination = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else campaign_path / DEFAULT_REPORT_FILENAME
    )
    report = build_research_efficiency_report(campaign_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_stable_json(report), encoding="utf-8")
    return destination


def _resolve_campaign_path(input_path: Path) -> tuple[Path, Path]:
    if input_path.is_dir() and _looks_like_campaign_dir(input_path):
        return input_path, input_path.parent
    nested_campaign = input_path / "campaign"
    if nested_campaign.is_dir() and _looks_like_campaign_dir(nested_campaign):
        return nested_campaign, input_path
    return input_path, input_path.parent


def _looks_like_campaign_dir(path: Path) -> bool:
    return any(
        (path / name).exists()
        for name in ("campaign_summary.json", "status.json", "scion.db", "artifacts")
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def _count_formal_index_rows(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "row_count": None, "unreadable_rows": 0}
    row_count = 0
    unreadable_rows = 0
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    json.loads(stripped)
                except json.JSONDecodeError:
                    unreadable_rows += 1
                row_count += 1
    except OSError:
        return {"exists": True, "row_count": None, "unreadable_rows": 0}
    return {
        "exists": True,
        "row_count": row_count,
        "unreadable_rows": unreadable_rows,
    }


def _find_run_log(input_path: Path, campaign_path: Path, run_root: Path) -> Path | None:
    candidates = [
        input_path / "run.log",
        campaign_path / "run.log",
        campaign_path.parent / "run.log",
        run_root / "run.log",
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate
    return None


def _classify_step_failures(steps: list[Any]) -> dict[str, dict[str, Any]]:
    buckets = _empty_taxonomy()
    for index, raw_step in enumerate(steps):
        if not isinstance(raw_step, Mapping):
            continue
        stage = str(raw_step.get("failure_stage") or "")
        text_parts = [
            stage,
            str(raw_step.get("failure_detail") or ""),
            str(raw_step.get("verification_detail") or ""),
        ]
        text = "\n".join(text_parts)
        source = {"kind": "campaign_step", "index": index}
        if stage == "verification" and _looks_heavy_verification(text):
            _add_observation(buckets, "verification_heavy", "campaign_steps", text, source)
        if stage == "code_generation" or "code_generation_failed" in text:
            _add_observation(buckets, "code_generation", "campaign_steps", text, source)
        if "agentic_proposal:code_generation_failed" in text:
            _add_observation(
                buckets,
                "agentic_proposal:code_generation_failed",
                "campaign_steps",
                text,
                source,
            )
        if "old_string_not_found" in text:
            _add_observation(buckets, "old_string_not_found", "campaign_steps", text, source)
        if "stale_source" in text:
            _add_observation(buckets, "stale_source", "campaign_steps", text, source)
        if "Tool call timeout" in text:
            _add_observation(buckets, "tool_timeout", "campaign_steps", text, source)
        if _ABANDON_FAST_RE.search(text):
            _add_observation(
                buckets,
                "abandon_fast_verification_heavy",
                "campaign_steps",
                text,
                source,
            )
    return buckets


def _classify_run_log(path: Path | None) -> dict[str, dict[str, Any]]:
    buckets = _empty_taxonomy()
    if path is None:
        return buckets
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line_number, line in enumerate(fh, start=1):
                text = line.strip()
                if not text:
                    continue
                source = {
                    "kind": "run_log",
                    "line": line_number,
                    "path": str(path),
                }
                if "verification_heavy" in text:
                    _add_observation(buckets, "verification_heavy", "run_log", text, source)
                if "agentic_proposal:code_generation_failed" in text:
                    _add_observation(
                        buckets,
                        "agentic_proposal:code_generation_failed",
                        "run_log",
                        text,
                        source,
                    )
                    _add_observation(buckets, "code_generation", "run_log", text, source)
                elif "code_generation" in text:
                    _add_observation(buckets, "code_generation", "run_log", text, source)
                if "old_string_not_found" in text:
                    _add_observation(buckets, "old_string_not_found", "run_log", text, source)
                if "stale_source" in text:
                    _add_observation(buckets, "stale_source", "run_log", text, source)
                if "Tool call timeout" in text:
                    _add_observation(buckets, "tool_timeout", "run_log", text, source)
                if _ABANDON_FAST_RE.search(text):
                    _add_observation(
                        buckets,
                        "abandon_fast_verification_heavy",
                        "run_log",
                        text,
                        source,
                    )
    except OSError:
        return buckets
    return buckets


def _empty_taxonomy() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "count": 0,
            "observations": 0,
            "source_counts": {},
            "examples": [],
            "sources": [],
        }
        for key in _TAXONOMY_KEYS
    }


def _add_observation(
    buckets: dict[str, dict[str, Any]],
    key: str,
    source_name: str,
    text: str,
    source: Mapping[str, Any],
) -> None:
    bucket = buckets[key]
    counts = Counter(bucket["source_counts"])
    counts[source_name] += 1
    bucket["source_counts"] = dict(sorted(counts.items()))
    bucket["observations"] = int(bucket["observations"]) + 1
    bucket["count"] = max(counts.values()) if counts else 0
    if len(bucket["examples"]) < 5:
        bucket["examples"].append(_shorten(text))
    if len(bucket["sources"]) < 10:
        bucket["sources"].append(dict(source))


def _merge_taxonomy(
    left: dict[str, dict[str, Any]],
    right: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged = _empty_taxonomy()
    for key in _TAXONOMY_KEYS:
        counts = Counter()
        counts.update(left[key].get("source_counts") or {})
        counts.update(right[key].get("source_counts") or {})
        examples = [
            *_list_value(left[key].get("examples")),
            *_list_value(right[key].get("examples")),
        ][:5]
        sources = [
            *_list_value(left[key].get("sources")),
            *_list_value(right[key].get("sources")),
        ][:10]
        merged[key] = {
            "count": max(counts.values()) if counts else 0,
            "observations": sum(counts.values()),
            "source_counts": dict(sorted(counts.items())),
            "examples": examples,
            "sources": sources,
        }
    return merged


def _looks_heavy_verification(text: str) -> bool:
    lowered = text.lower()
    return "severity=heavy" in lowered or "(heavy)" in lowered or "verification_heavy" in lowered


def _quality_block_reasons(summary: Mapping[str, Any], status: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    seen: set[str] = set()
    for source in (summary, status):
        for entry in _list_value(source.get("quality_block_ledger")):
            if not isinstance(entry, Mapping):
                continue
            reason = _first_str(
                entry.get("failure_reason"),
                entry.get("failure_detail"),
                entry.get("source_result_reason"),
            )
            if reason and reason not in seen:
                seen.add(reason)
                reasons.append(reason)
            if len(reasons) >= 10:
                return reasons
    return reasons


def _compact_research_shape_diagnostics(
    diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(diagnostics, Mapping) or not diagnostics:
        return {}
    return {
        "schema_version": _first_str(diagnostics.get("schema_version")),
        "policy": _first_str(diagnostics.get("policy")),
        "decision_features_excluded": _first_bool(
            diagnostics.get("decision_features_excluded"),
            True,
        ),
        "decision_input_policy": _first_str(
            diagnostics.get("decision_input_policy")
        ),
        "source": _mapping_value(diagnostics.get("source")),
        "branch_depth_distribution": _mapping_value(
            diagnostics.get("branch_depth_distribution")
        ),
        "branch_depth_by_branch": _mapping_value(
            diagnostics.get("branch_depth_by_branch")
        ),
        "max_branch_depth": _first_int(diagnostics.get("max_branch_depth")),
        "mean_branch_depth": _first_float(diagnostics.get("mean_branch_depth")),
        "active_research_shape_signal": _mapping_value(
            diagnostics.get("active_research_shape_signal")
        ),
        "mechanism_family_breadth": _mapping_value(
            diagnostics.get("mechanism_family_breadth")
        ),
    }


def _compact_cross_branch_observability(
    observability: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(observability, Mapping) or not observability:
        return {}
    return {
        "schema_version": _first_str(observability.get("schema_version")),
        "policy": _first_str(observability.get("policy")),
        "decision_input_policy": _first_str(
            observability.get("decision_input_policy")
        ),
        "source_counts": _mapping_value(observability.get("source_counts")),
        "observable_step_count": _first_int(
            observability.get("observable_step_count")
        ),
        "near_duplicate_count": _first_int(observability.get("near_duplicate_count")),
        "saturated_signature_count": _first_int(
            observability.get("saturated_signature_count")
        ),
        "material_difference_requirement_count": _first_int(
            observability.get("material_difference_requirement_count")
        ),
        "branch_lesson_record_count": _first_int(
            observability.get("branch_lesson_record_count")
        ),
        "branch_lesson_usage_requirement_count": _first_int(
            observability.get("branch_lesson_usage_requirement_count")
        ),
        "branch_lesson_usage_present_count": _first_int(
            observability.get("branch_lesson_usage_present_count")
        ),
        "branch_lesson_usage_satisfied_count": _first_int(
            observability.get("branch_lesson_usage_satisfied_count")
        ),
        "branch_lesson_usage_missing_block_count": _first_int(
            observability.get("branch_lesson_usage_missing_block_count")
        ),
        "borrowed_lesson_count": _first_int(
            observability.get("borrowed_lesson_count")
        ),
        "avoided_lesson_count": _first_int(observability.get("avoided_lesson_count")),
        "contrasted_lesson_count": _first_int(
            observability.get("contrasted_lesson_count")
        ),
        "preserved_same_branch_lesson_count": _first_int(
            observability.get("preserved_same_branch_lesson_count")
        ),
        "clean_fork_contrast_satisfied_count": _first_int(
            observability.get("clean_fork_contrast_satisfied_count")
        ),
        "weak_positive_transfer_count": _first_int(
            observability.get("weak_positive_transfer_count")
        ),
        "weak_positive_transfer_reject_count": _first_int(
            observability.get("weak_positive_transfer_reject_count")
        ),
        "same_branch_refinement_allowance_count": _first_int(
            observability.get("same_branch_refinement_allowance_count")
        ),
        "same_branch_refinement_not_selected_count": _first_int(
            observability.get("same_branch_refinement_not_selected_count")
        ),
        "reason_code_counts": _mapping_value(observability.get("reason_code_counts")),
    }


def _source_ref(path: Path | None) -> str:
    if path is None:
        return ""
    return str(path) if path.exists() else ""


def _first_int(*values: Any) -> int | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_bool(*values: Any) -> bool | None:
    for value in values:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1"}:
                return True
            if normalized in {"false", "no", "0"}:
                return False
    return None


def _first_float(*values: Any) -> float | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_str(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _mapping_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_value(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _mapping_int(mapping: Mapping[str, Any] | None, key: str) -> int | None:
    if not isinstance(mapping, Mapping):
        return None
    return _first_int(mapping.get(key))


def _nested_value(mapping: Mapping[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _nested_int(mapping: Mapping[str, Any], *keys: str) -> int | None:
    return _first_int(_nested_value(mapping, *keys))


def _shorten(text: str, *, limit: int = 260) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


__all__ = [
    "DEFAULT_REPORT_FILENAME",
    "SCHEMA_VERSION",
    "build_research_efficiency_report",
    "write_research_efficiency_report",
]
