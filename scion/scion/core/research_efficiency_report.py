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

import yaml

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
    measurement_readiness_source = "summary_status" if measurement_readiness else ""
    if not measurement_readiness:
        measurement_readiness = _artifact_measurement_readiness(
            campaign_path=campaign_path,
            run_root=run_root,
        )
        measurement_readiness_source = "artifact_fallback" if measurement_readiness else ""
    cross_branch_observability = _mapping_value(
        summary.get("cross_branch_research_observability")
    ) or _mapping_value(status.get("cross_branch_research_observability"))
    research_shape_diagnostics = _mapping_value(
        cross_branch_observability.get("research_shape_diagnostics")
    )
    branch_family_map = _mapping_value(
        research_shape_diagnostics.get("branch_mechanism_family_map")
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
        "measurement_readiness_source": measurement_readiness_source,
        "protocol_effects_vs_mde": _protocol_effects_vs_mde(
            steps,
            measurement_readiness or {},
            branch_family_map,
        ),
        "research_shape": _compact_research_shape_diagnostics(
            research_shape_diagnostics
        ),
        "cross_branch_observability": _compact_cross_branch_observability(
            cross_branch_observability
        ),
        "research_continuity": _research_continuity_metrics(
            cross_branch_observability,
            research_shape_diagnostics,
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
        "branch_mechanism_family_map": _mapping_value(
            diagnostics.get("branch_mechanism_family_map")
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
        "branch_lesson_usage_present_not_semantic_count": _first_int(
            observability.get("branch_lesson_usage_present_not_semantic_count")
        ),
        "branch_lesson_usage_metadata_only_count": _first_int(
            observability.get("branch_lesson_usage_metadata_only_count")
        ),
        "branch_lesson_usage_metadata_only_block_count": _first_int(
            observability.get("branch_lesson_usage_metadata_only_block_count")
        ),
        "branch_lesson_usage_linkage_unrecognized_count": _first_int(
            observability.get("branch_lesson_usage_linkage_unrecognized_count")
        ),
        "branch_lesson_usage_linkage_unrecognized_block_count": _first_int(
            observability.get("branch_lesson_usage_linkage_unrecognized_block_count")
        ),
        "branch_lesson_usage_semantic_mismatch_count": _first_int(
            observability.get("branch_lesson_usage_semantic_mismatch_count")
        ),
        "branch_lesson_usage_semantic_mismatch_block_count": _first_int(
            observability.get("branch_lesson_usage_semantic_mismatch_block_count")
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


def _research_continuity_metrics(
    observability: Mapping[str, Any],
    research_shape_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(observability, Mapping) or not observability:
        return {}
    shape = _mapping_value(research_shape_diagnostics)
    selected_same_branch = _int_or_zero(
        observability.get("same_branch_refinement_allowance_count")
    )
    not_selected_same_branch = _int_or_zero(
        observability.get("same_branch_refinement_not_selected_count")
    )
    same_branch_opportunities = selected_same_branch + not_selected_same_branch

    lesson_requirements = _int_or_zero(
        observability.get("branch_lesson_usage_requirement_count")
    )
    lessons_present = _int_or_zero(
        observability.get("branch_lesson_usage_present_count")
    )
    lessons_satisfied = _int_or_zero(
        observability.get("branch_lesson_usage_satisfied_count")
    )
    present_not_semantic = _int_or_zero(
        observability.get("branch_lesson_usage_present_not_semantic_count")
    )
    missing_blocks = _int_or_zero(
        observability.get("branch_lesson_usage_missing_block_count")
    )
    metadata_only = _int_or_zero(
        observability.get("branch_lesson_usage_metadata_only_count")
    )
    metadata_only_blocks = _int_or_zero(
        observability.get("branch_lesson_usage_metadata_only_block_count")
    )
    linkage_unrecognized = _int_or_zero(
        observability.get("branch_lesson_usage_linkage_unrecognized_count")
    )
    linkage_unrecognized_blocks = _int_or_zero(
        observability.get("branch_lesson_usage_linkage_unrecognized_block_count")
    )
    semantic_mismatch = _int_or_zero(
        observability.get("branch_lesson_usage_semantic_mismatch_count")
    )
    semantic_mismatch_blocks = _int_or_zero(
        observability.get("branch_lesson_usage_semantic_mismatch_block_count")
    )
    weak_positive_accepts = _int_or_zero(
        observability.get("weak_positive_transfer_count")
    )
    weak_positive_rejects = _int_or_zero(
        observability.get("weak_positive_transfer_reject_count")
    )
    weak_positive_opportunities = weak_positive_accepts + weak_positive_rejects
    active_shape = _mapping_value(shape.get("active_research_shape_signal"))
    mechanism_breadth = _mapping_value(shape.get("mechanism_family_breadth"))

    return {
        "schema_version": "scion.research_continuity_metrics.v1",
        "report_only": True,
        "decision_features_excluded": True,
        "decision_input_policy": "excluded_from_decision_features",
        "metric_semantics": (
            "postrun summary/status observability; not Decision input and not "
            "a promotion criterion"
        ),
        "same_mechanism_followup": {
            "selected_same_branch_refinement_count": selected_same_branch,
            "not_selected_same_branch_refinement_count": not_selected_same_branch,
            "observed_opportunity_count": same_branch_opportunities,
            "selection_rate": _safe_ratio(
                selected_same_branch,
                same_branch_opportunities,
            ),
            "interpretation": _same_branch_followup_interpretation(
                selected_same_branch,
                not_selected_same_branch,
            ),
        },
        "branch_lesson_usage": {
            "requirement_count": lesson_requirements,
            "present_count": lessons_present,
            "satisfied_count": lessons_satisfied,
            "missing_block_count": missing_blocks,
            "present_not_semantic_count": present_not_semantic,
            "metadata_only_count": metadata_only,
            "metadata_only_block_count": metadata_only_blocks,
            "linkage_unrecognized_count": linkage_unrecognized,
            "linkage_unrecognized_block_count": linkage_unrecognized_blocks,
            "semantic_mismatch_count": semantic_mismatch,
            "semantic_mismatch_block_count": semantic_mismatch_blocks,
            "semantic_failure_counts": _nonzero_counts(
                {
                    "missing": missing_blocks,
                    "metadata_only": metadata_only,
                    "linkage_unrecognized": linkage_unrecognized,
                    "semantic_mismatch": semantic_mismatch,
                }
            ),
            "semantic_block_counts": _nonzero_counts(
                {
                    "missing": missing_blocks,
                    "metadata_only": metadata_only_blocks,
                    "linkage_unrecognized": linkage_unrecognized_blocks,
                    "semantic_mismatch": semantic_mismatch_blocks,
                }
            ),
            "satisfaction_rate": _safe_ratio(
                lessons_satisfied,
                lesson_requirements,
            ),
            "present_rate": _safe_ratio(lessons_present, lesson_requirements),
            "semantic_gap_count": max(0, lessons_present - lessons_satisfied),
            "semantic_gap_rate": _safe_ratio(
                max(0, lessons_present - lessons_satisfied),
                max(lessons_present, lesson_requirements),
            ),
        },
        "weak_positive_transfer": {
            "accepted_count": weak_positive_accepts,
            "rejected_count": weak_positive_rejects,
            "observed_opportunity_count": weak_positive_opportunities,
            "acceptance_rate": _safe_ratio(
                weak_positive_accepts,
                weak_positive_opportunities,
            ),
        },
        "lesson_action_counts": {
            "borrowed": _int_or_zero(observability.get("borrowed_lesson_count")),
            "avoided": _int_or_zero(observability.get("avoided_lesson_count")),
            "contrasted": _int_or_zero(observability.get("contrasted_lesson_count")),
            "preserved_same_branch": _int_or_zero(
                observability.get("preserved_same_branch_lesson_count")
            ),
            "clean_fork_contrast_satisfied": _int_or_zero(
                observability.get("clean_fork_contrast_satisfied_count")
            ),
        },
        "research_shape_summary": {
            "max_branch_depth": _first_int(shape.get("max_branch_depth")),
            "mean_branch_depth": _first_float(shape.get("mean_branch_depth")),
            "branch_depth_distribution": _mapping_value(
                shape.get("branch_depth_distribution")
            ),
            "active_shape": _first_str(active_shape.get("shape")),
            "active_branch_count": _first_int(active_shape.get("active_branch_count")),
            "active_mechanism_family_count": _first_int(
                active_shape.get("active_mechanism_family_count")
            ),
            "mechanism_family_count": _first_int(
                mechanism_breadth.get("family_count")
            ),
        },
    }


def _same_branch_followup_interpretation(
    selected_count: int,
    not_selected_count: int,
) -> str:
    total = selected_count + not_selected_count
    if total <= 0:
        return "no_same_mechanism_followup_opportunities_observed"
    if selected_count > 0 and not_selected_count == 0:
        return "all_observed_same_mechanism_followups_selected"
    if selected_count > 0:
        return "some_same_mechanism_followups_selected"
    return "same_mechanism_followup_opportunities_not_selected"


def _nonzero_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return {
        str(key): _int_or_zero(value)
        for key, value in sorted(counts.items())
        if _int_or_zero(value) > 0
    }


def _protocol_effects_vs_mde(
    steps: list[Any],
    measurement_readiness: Mapping[str, Any],
    branch_family_map: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    mde = _first_float(measurement_readiness.get("mde_at_power_80"))
    family_map = _mapping_value(branch_family_map)
    rows: list[dict[str, Any]] = []
    for item in steps:
        if not isinstance(item, Mapping):
            continue
        protocol = item.get("protocol_result")
        if not isinstance(protocol, Mapping):
            continue
        row = _protocol_effect_row(item, protocol, mde, family_map)
        if row:
            rows.append(row)

    stage_buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        stage_buckets.setdefault(str(row.get("stage") or "unknown"), []).append(row)

    return {
        "schema_version": "scion.research_efficiency_effect_vs_mde.v1",
        "report_only": True,
        "decision_features_excluded": True,
        "decision_input_policy": "excluded_from_decision_features",
        "measurement_readiness_status": _first_str(
            measurement_readiness.get("status")
        ),
        "measurement_readiness_reason_code": _first_str(
            measurement_readiness.get("reason_code")
        ),
        "mde_at_power_80": mde,
        "mde_source": (
            "measurement_readiness.mde_at_power_80"
            if mde is not None and mde > 0
            else "unavailable"
        ),
        "interpretation": _effect_vs_mde_interpretation(rows, mde),
        **_effect_row_counts(rows, mde),
        "by_stage": {
            stage: _effect_row_counts(stage_rows, mde)
            for stage, stage_rows in sorted(stage_buckets.items())
        },
        "mechanism_family_effect_summary": _mechanism_family_effect_summary(
            rows,
            mde,
        ),
        "top_rows_by_effect_to_mde": _top_effect_rows(rows),
    }


def _protocol_effect_row(
    step: Mapping[str, Any],
    protocol: Mapping[str, Any],
    mde: float | None,
    branch_family_map: Mapping[str, Any],
) -> dict[str, Any] | None:
    median_delta = _first_float(protocol.get("median_delta"))
    ci_low = _first_float(protocol.get("ci_low"))
    ci_high = _first_float(protocol.get("ci_high"))
    win_rate = _first_float(protocol.get("win_rate"), protocol.get("case_win_rate"))
    branch_id = _first_str(step.get("branch_id"))
    mechanism_family = _mechanism_family_for_branch(branch_id, branch_family_map)
    effect_to_mde_ratio = (
        round(median_delta / mde, 6)
        if median_delta is not None and mde is not None and mde > 0
        else None
    )
    return {
        "round": _first_int(step.get("round")),
        "branch_id": branch_id,
        "mechanism_family": mechanism_family,
        "stage": _first_str(protocol.get("stage"), "unknown"),
        "decision": _first_str(step.get("decision")),
        "gate_outcome": _first_str(protocol.get("gate_outcome")),
        "median_delta": median_delta,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "win_rate": win_rate,
        "effect_to_mde_ratio": effect_to_mde_ratio,
        "positive_effect_at_or_above_mde": bool(
            median_delta is not None
            and mde is not None
            and mde > 0
            and median_delta >= mde
        ),
        "ci_high_below_mde": bool(
            ci_high is not None and mde is not None and mde > 0 and ci_high < mde
        ),
        "reason_codes": _list_of_str(protocol.get("effective_reason_codes"))
        or _list_of_str(protocol.get("reason_codes")),
    }


def _mechanism_family_for_branch(
    branch_id: str,
    branch_family_map: Mapping[str, Any],
) -> str:
    if not branch_id:
        return ""
    entry = branch_family_map.get(branch_id)
    if isinstance(entry, Mapping):
        return _first_str(entry.get("primary_family"))
    if isinstance(entry, str):
        return _first_str(entry)
    return ""


def _mechanism_family_effect_summary(
    rows: list[Mapping[str, Any]],
    mde: float | None,
) -> dict[str, Any]:
    buckets: dict[str, list[Mapping[str, Any]]] = {}
    mapped = 0
    unmapped = 0
    for row in rows:
        family = _first_str(row.get("mechanism_family"))
        if family:
            mapped += 1
            buckets.setdefault(family, []).append(row)
        else:
            unmapped += 1

    by_family = {
        family: _effect_row_counts(family_rows, mde)
        for family, family_rows in sorted(buckets.items())
    }
    return {
        "schema_version": "scion.mechanism_family_effect_summary.v1",
        "report_only": True,
        "decision_features_excluded": True,
        "decision_input_policy": "excluded_from_decision_features",
        "mapping_status": "available" if mapped else "unavailable",
        "mapped_row_count": mapped,
        "unmapped_row_count": unmapped,
        "mechanism_family_count": len(by_family),
        "by_family": by_family,
    }


def _effect_row_counts(
    rows: list[Mapping[str, Any]],
    mde: float | None,
) -> dict[str, Any]:
    rows_with_median = [
        row for row in rows if _first_float(row.get("median_delta")) is not None
    ]
    positive_rows = [
        row for row in rows_with_median if _first_float(row.get("median_delta")) > 0
    ]
    nonpositive_rows = [
        row for row in rows_with_median if _first_float(row.get("median_delta")) <= 0
    ]
    rows_at_or_above_mde = [
        row for row in rows_with_median if row.get("positive_effect_at_or_above_mde")
    ]
    rows_with_ci_high_below_mde = [
        row for row in rows_with_median if row.get("ci_high_below_mde")
    ]
    ratios = [
        ratio
        for row in rows_with_median
        for ratio in [_first_float(row.get("effect_to_mde_ratio"))]
        if ratio is not None
    ]
    median_values = [
        value
        for row in rows_with_median
        for value in [_first_float(row.get("median_delta"))]
        if value is not None
    ]
    return {
        "protocol_row_count": len(rows),
        "rows_with_median_delta": len(rows_with_median),
        "positive_rows": len(positive_rows),
        "nonpositive_rows": len(nonpositive_rows),
        "rows_at_or_above_mde": len(rows_at_or_above_mde),
        "rows_below_mde": (
            len(rows_with_median) - len(rows_at_or_above_mde)
            if mde is not None and mde > 0
            else None
        ),
        "rows_with_ci_high_below_mde": len(rows_with_ci_high_below_mde),
        "max_median_delta": max(median_values) if median_values else None,
        "max_effect_to_mde_ratio": max(ratios) if ratios else None,
    }


def _effect_vs_mde_interpretation(
    rows: list[Mapping[str, Any]],
    mde: float | None,
) -> str:
    if not rows:
        return "no_protocol_rows"
    if mde is None or mde <= 0:
        return "mde_unavailable"
    if any(row.get("positive_effect_at_or_above_mde") for row in rows):
        return "has_positive_protocol_effect_at_or_above_mde"
    ci_rows = [row for row in rows if row.get("ci_high") is not None]
    if ci_rows and all(row.get("ci_high_below_mde") for row in ci_rows):
        return "all_available_ci_high_below_mde"
    return "protocol_effects_below_mde_or_inconclusive"


def _top_effect_rows(
    rows: list[Mapping[str, Any]],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    sortable = [
        row
        for row in rows
        if _first_float(row.get("effect_to_mde_ratio")) is not None
    ]
    sortable.sort(
        key=lambda row: _first_float(row.get("effect_to_mde_ratio")) or float("-inf"),
        reverse=True,
    )
    return [
        {
            key: row.get(key)
            for key in (
                "round",
                "branch_id",
                "mechanism_family",
                "stage",
                "decision",
                "gate_outcome",
                "median_delta",
                "ci_low",
                "ci_high",
                "win_rate",
                "effect_to_mde_ratio",
                "positive_effect_at_or_above_mde",
                "ci_high_below_mde",
                "reason_codes",
            )
        }
        for row in sortable[:limit]
    ]


def _artifact_measurement_readiness(
    *,
    campaign_path: Path,
    run_root: Path,
) -> dict[str, Any] | None:
    for problem_path in _candidate_problem_v1_paths(campaign_path, run_root):
        problem = _read_yaml_object(problem_path)
        measurement = _mapping_value(problem.get("measurement"))
        if not measurement:
            continue
        artifact_path = _find_calibration_artifact(
            problem_path=problem_path,
            measurement=measurement,
            campaign_path=campaign_path,
            run_root=run_root,
        )
        if artifact_path is None:
            continue
        artifact = _read_json_object(artifact_path)
        if not _calibration_compatible(problem, measurement, artifact):
            continue
        return _readiness_from_calibration_artifact(measurement, artifact)
    return None


def _candidate_problem_v1_paths(campaign_path: Path, run_root: Path) -> list[Path]:
    candidates: list[Path] = []
    roots = [
        campaign_path,
        run_root,
        run_root.parent,
        run_root.parent.parent,
    ]
    for root in roots:
        candidates.append(root / "problem-v1.yaml")
        candidates.append(root / "config" / "problem-v1.yaml")
    for pattern in (
        "champions/*/problem-v1.yaml",
        "workspaces/*/problem-v1.yaml",
        "weight_opt_*/problem-v1.yaml",
    ):
        candidates.extend(campaign_path.glob(pattern))
    return _existing_unique_paths(candidates)


def _find_calibration_artifact(
    *,
    problem_path: Path,
    measurement: Mapping[str, Any],
    campaign_path: Path,
    run_root: Path,
) -> Path | None:
    ref = _first_str(measurement.get("calibration_ref"))
    if not ref:
        return None
    ref_path = Path(ref)
    candidates: list[Path] = []
    if ref_path.is_absolute():
        candidates.append(ref_path)
    else:
        candidates.extend(
            [
                problem_path.parent / ref_path,
                campaign_path / ref_path,
                run_root / ref_path,
                run_root.parent / ref_path,
                run_root.parent.parent / ref_path,
            ]
        )
        for pattern in (
            f"champions/*/{ref}",
            f"workspaces/*/{ref}",
            f"weight_opt_*/{ref}",
        ):
            candidates.extend(campaign_path.glob(pattern))
    for candidate in _existing_unique_paths(candidates):
        if candidate.is_file():
            return candidate
    return None


def _calibration_compatible(
    problem: Mapping[str, Any],
    measurement: Mapping[str, Any],
    artifact: Mapping[str, Any],
) -> bool:
    if artifact.get("schema") != "scion.aa_noise_floor.v1":
        return False
    if artifact.get("decision_features_excluded") is not True:
        return False
    problem_id = _first_str(problem.get("id"), problem.get("name"))
    artifact_problem_id = _first_str(artifact.get("problem_id"))
    if problem_id and artifact_problem_id and problem_id != artifact_problem_id:
        return False
    effect_scale = _mapping_value(measurement.get("effect_scale"))
    metric = _first_str(effect_scale.get("metric"))
    unit = _first_str(effect_scale.get("unit"))
    if metric and _first_str(artifact.get("measurement_metric")) != metric:
        return False
    if unit and _first_str(artifact.get("measurement_unit")) != unit:
        return False
    return True


def _readiness_from_calibration_artifact(
    measurement: Mapping[str, Any],
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    max_age_days = _nonnegative_int(measurement.get("calibration_max_age_days"))
    calibrated_at = _parse_datetime(artifact.get("calibrated_at"))
    age_days = (
        max(0, (datetime.now(timezone.utc).date() - calibrated_at.date()).days)
        if calibrated_at is not None
        else None
    )
    power = _mapping_value(artifact.get("protocol_power"))
    mde = _first_float(power.get("mde_at_power_80"))
    effect_scale = _mapping_value(measurement.get("effect_scale"))
    practical_delta = _first_float(effect_scale.get("practical_delta_screen"))
    effect_to_mde = (
        practical_delta / mde
        if practical_delta is not None and mde is not None and mde > 0
        else None
    )
    status = "ready"
    reason_code = "ok"
    if calibrated_at is None or mde is None:
        status = "degraded"
        reason_code = "calibration_incomplete"
    elif age_days is not None and age_days > max_age_days:
        status = "degraded"
        reason_code = "calibration_stale"
    return {
        "status": status,
        "reason_code": reason_code,
        "calibration_age_days": age_days,
        "calibration_max_age_days": max_age_days,
        "n_pairs": _nonnegative_int(artifact.get("n_pairs")),
        "mde_at_power_80": mde,
        "noise_band_p90_abs": _noise_band_p90_abs(artifact.get("per_case")),
        "effect_to_mde_ratio": effect_to_mde,
        "signal_to_noise_tier": _signal_to_noise_tier(effect_to_mde),
        "decision_features_excluded": True,
    }


def _read_yaml_object(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return dict(loaded) if isinstance(loaded, Mapping) else {}


def _parse_datetime(value: Any) -> datetime | None:
    text = _first_str(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _noise_band_p90_abs(value: Any) -> float | None:
    if not isinstance(value, list):
        return None
    values = [
        parsed
        for row in value
        if isinstance(row, Mapping)
        for parsed in [_first_float(row.get("delta_p90_abs"))]
        if parsed is not None
    ]
    return max(values) if values else None


def _signal_to_noise_tier(ratio: float | None) -> str:
    if ratio is None:
        return "unknown"
    if ratio >= 1.0:
        return "ready"
    if ratio >= 1.0 / 3.0:
        return "marginal"
    return "low_power"


def _existing_unique_paths(candidates: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        result.append(resolved)
    return result


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


def _int_or_zero(value: Any) -> int:
    parsed = _first_int(value)
    return parsed if parsed is not None else 0


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _first_float(*values: Any) -> float | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _nonnegative_int(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


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


def _list_of_str(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


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
