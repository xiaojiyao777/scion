"""Direct branch evidence and lifecycle side effects for decision finalization.

Protocol results are recorded without deriving a second screening tier or
follow-up policy. Formal decisions remain owned by the protocol gate and its
reason codes.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from scion.core.models import Branch, ProtocolResult
from scion.core.public_refs import public_artifact_ref, public_case_ref
from scion.core.screening_visibility import (
    runtime_aggregate_exclusion_for_protocol,
    runtime_evidence_policy_for_protocol,
)

_DURABLE_SCREENING_KEYS = (
    "canonical_screening_history",
    "protocol_evidence_by_stage",
    "verified_branch_created_files",
    "verified_branch_touched_files",
    "candidate_evaluation",
)

# These fields form one current-protocol projection.  Clear them together
# before writing a later stage so screening facts cannot survive beside
# validation reason codes (or vice versa).
_CURRENT_PROTOCOL_KEYS = frozenset(
    {
        "case_feedback",
        "case_aggregation",
        "case_ids",
        "candidate_failed_pairs",
        "champion_failed_pairs",
        "ci_high",
        "ci_low",
        "decision_reason_codes",
        "evidence_retention_status",
        "failed_pairs",
        "gate_outcome",
        "losses",
        "mechanism_evidence",
        "median_delta",
        "metric_stats",
        "n_cases",
        "objective_semantics",
        "opportunity_diagnostics",
        "opportunity_status",
        "pair_feedback",
        "pair_losses",
        "pair_ties",
        "pair_wins",
        "phase_telemetry_summary",
        "protocol_reason_codes",
        "protocol_stage",
        "raw_metrics_ref",
        "raw_metrics_ref_scope",
        "reason_codes",
        "runtime_aggregate_exclusion",
        "runtime_cache",
        "runtime_delta_median_ms",
        "runtime_evidence_confidence",
        "runtime_evidence_status",
        "runtime_evidence_policy",
        "runtime_model",
        "runtime_pairs",
        "runtime_ratio_median",
        "runtime_regression_rate",
        "seed_set",
        "selected_surface",
        "stage",
        "statistical_metric",
        "statistical_status",
        "ties",
        "attempted_pairs",
        "total_pairs",
        "valid_pairs",
        "why_not_promoted_reason_codes",
        "win_rate",
        "wins",
    }
)


def update_branch_screening_evidence_summary(
    branch: Branch,
    *,
    protocol_result: Optional[ProtocolResult],
    decision_reason_codes: Iterable[str] | None = None,
) -> None:
    """Persist lossless screening facts without advisory classification."""

    if protocol_result is None or protocol_result.stats is None:
        return
    if getattr(protocol_result.stage, "value", protocol_result.stage) != "screening":
        return

    update_branch_protocol_evidence_summary(
        branch,
        protocol_result=protocol_result,
        decision_reason_codes=decision_reason_codes,
    )


def update_branch_protocol_evidence_summary(
    branch: Branch,
    *,
    protocol_result: Optional[ProtocolResult],
    decision_reason_codes: Iterable[str] | None = None,
) -> None:
    """Atomically project latest and per-stage protocol read models.

    Append-only experiment history remains owned by the lineage registry and
    raw metric artifacts; branch cards retain only the latest record per stage
    to avoid duplicating full research history into proposal context.
    """

    if protocol_result is None or protocol_result.stats is None:
        return

    previous_summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    stage = _stage_value(protocol_result)
    if stage == "screening":
        summary: dict[str, Any] = {
            key: previous_summary[key]
            for key in _DURABLE_SCREENING_KEYS
            if key in previous_summary
        }
    else:
        summary = previous_summary

    for key in _CURRENT_PROTOCOL_KEYS:
        summary.pop(key, None)

    projection = _protocol_evidence_projection(
        protocol_result,
        decision_reason_codes=decision_reason_codes,
    )
    summary.update(_current_protocol_fields(projection))
    summary["evidence_retention_status"] = "retained"
    summary["case_feedback"] = [
        _case_payload(item) for item in protocol_result.case_feedback
    ]
    summary["pair_feedback"] = [
        _pair_payload(item) for item in protocol_result.pair_feedback
    ]
    summary["mechanism_evidence"] = dict(
        getattr(protocol_result, "mechanism_evidence", {}) or {}
    )
    phase_telemetry = getattr(
        protocol_result, "candidate_phase_telemetry_summary", None
    )
    if isinstance(phase_telemetry, Mapping) and phase_telemetry:
        summary["phase_telemetry_summary"] = dict(phase_telemetry)

    runtime_aggregate_exclusion = runtime_aggregate_exclusion_for_protocol(
        protocol_result
    )
    if runtime_aggregate_exclusion:
        summary["runtime_aggregate_exclusion"] = runtime_aggregate_exclusion

    by_stage = {
        str(key): dict(value)
        for key, value in (summary.get("protocol_evidence_by_stage") or {}).items()
        if isinstance(value, Mapping)
    }
    by_stage[projection["stage"]] = dict(projection)
    summary["protocol_evidence_by_stage"] = by_stage
    summary["latest_protocol_evidence"] = dict(projection)
    branch.branch_evidence_summary = summary


def _protocol_evidence_projection(
    protocol_result: ProtocolResult,
    *,
    decision_reason_codes: Iterable[str] | None,
) -> dict[str, Any]:
    stats = protocol_result.stats
    pair_wins, pair_losses, pair_ties = _pair_counts(protocol_result)
    protocol_reason_codes = _reason_codes(protocol_result.reason_codes)
    decision_codes = _reason_codes(decision_reason_codes)
    effective_reason_codes = tuple(
        dict.fromkeys((*decision_codes, *protocol_reason_codes))
    )
    raw_metrics_ref = public_artifact_ref(
        protocol_result.raw_metrics_ref,
        kind="metrics",
    )
    case_ids = [
        ref
        for ref in (public_case_ref(case_id) for case_id in protocol_result.case_ids)
        if ref is not None
    ]
    runtime_model = getattr(protocol_result, "runtime_model", None)
    runtime_policy = (
        runtime_evidence_policy_for_protocol(protocol_result) if runtime_model else {}
    )
    return {
        "schema_version": "scion.branch_protocol_evidence.v1",
        "stage": _stage_value(protocol_result),
        "gate_outcome": protocol_result.gate_outcome,
        "raw_metrics_ref": raw_metrics_ref,
        "raw_metrics_ref_scope": "public_artifact_ref",
        "case_ids": case_ids,
        "seed_set": list(protocol_result.seed_set),
        "objective_semantics": str(protocol_result.objective_semantics or "unknown"),
        "case_aggregation": {
            "method": str(
                getattr(protocol_result, "case_aggregation_method", "")
                or "seed_vote_majority"
            ),
            "effect_metric": str(
                getattr(protocol_result, "case_effect_metric", "") or ""
            ),
            "equivalence_band": float(
                getattr(protocol_result, "case_equivalence_band", 0.0) or 0.0
            ),
        },
        "selected_surface": protocol_result.selected_surface,
        "n_cases": max(0, int(getattr(stats, "n_cases", 0) or 0)),
        "wins": max(0, int(getattr(stats, "wins", 0) or 0)),
        "losses": max(0, int(getattr(stats, "losses", 0) or 0)),
        "ties": max(0, int(getattr(stats, "ties", 0) or 0)),
        "win_rate": getattr(stats, "win_rate", None),
        "pair_wins": pair_wins,
        "pair_losses": pair_losses,
        "pair_ties": pair_ties,
        "median_delta": getattr(stats, "median_delta", None),
        "ci_low": getattr(stats, "ci_low", None),
        "ci_high": getattr(stats, "ci_high", None),
        "statistical_status": getattr(stats, "statistical_status", None),
        "statistical_metric": getattr(stats, "statistical_metric", None),
        "metric_stats": [
            {
                "metric_name": item.metric_name,
                "median_delta": item.median_delta,
                "ci_low": item.ci_low,
                "ci_high": item.ci_high,
                "n_cases": item.n_cases,
            }
            for item in (getattr(stats, "metric_stats", ()) or ())
        ],
        "runtime_ratio_median": getattr(stats, "runtime_ratio_median", None),
        "runtime_delta_median_ms": getattr(stats, "runtime_delta_median_ms", None),
        "runtime_regression_rate": getattr(stats, "runtime_regression_rate", None),
        "runtime_pairs": max(0, int(getattr(stats, "runtime_pairs", 0) or 0)),
        "runtime_evidence_confidence": str(
            getattr(protocol_result, "runtime_confidence", "") or "unknown"
        ),
        "runtime_evidence_status": str(
            getattr(protocol_result, "runtime_evidence_status", "")
            or getattr(stats, "runtime_evidence_status", "")
            or "unknown"
        ),
        **(
            {
                "runtime_model": runtime_model,
                "runtime_evidence_policy": runtime_policy,
            }
            if runtime_model
            else {}
        ),
        "runtime_cache": {
            "champion_cache_hits": max(
                0, int(getattr(protocol_result, "champion_cache_hits", 0) or 0)
            ),
            "champion_cache_misses": max(
                0, int(getattr(protocol_result, "champion_cache_misses", 0) or 0)
            ),
            "champion_cached_runtime_pairs": max(
                0,
                int(getattr(protocol_result, "champion_cached_runtime_pairs", 0) or 0),
            ),
        },
        "total_pairs": max(0, int(getattr(stats, "total_pairs", 0) or 0)),
        "attempted_pairs": max(0, int(getattr(stats, "attempted_pairs", 0) or 0)),
        "valid_pairs": max(0, int(getattr(stats, "valid_pairs", 0) or 0)),
        "failed_pairs": max(0, int(getattr(stats, "failed_pairs", 0) or 0)),
        "candidate_failed_pairs": max(
            0, int(getattr(stats, "candidate_failed_pairs", 0) or 0)
        ),
        "champion_failed_pairs": max(
            0, int(getattr(stats, "champion_failed_pairs", 0) or 0)
        ),
        "opportunity_status": str(
            getattr(protocol_result, "opportunity_status", "") or "unknown"
        ),
        "opportunity_diagnostics": list(
            getattr(protocol_result, "opportunity_diagnostics", ()) or ()
        ),
        "protocol_reason_codes": list(protocol_reason_codes),
        "decision_reason_codes": list(decision_codes),
        "reason_codes": list(effective_reason_codes),
    }


def _current_protocol_fields(projection: Mapping[str, Any]) -> dict[str, Any]:
    fields = {
        key: value for key, value in projection.items() if key != "schema_version"
    }
    fields["protocol_stage"] = projection["stage"]
    effective_reason_codes = list(projection.get("reason_codes") or ())
    fields["decision_reason_codes"] = effective_reason_codes
    return fields


def _stage_value(protocol_result: ProtocolResult) -> str:
    stage = getattr(protocol_result, "stage", "")
    return str(getattr(stage, "value", stage) or "")


def _reason_codes(values: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(str(code).strip() for code in (values or ()) if str(code).strip())
    )


def _pair_counts(protocol_result: ProtocolResult) -> tuple[int, int, int]:
    stats = protocol_result.stats
    stats_counts = (
        max(0, int(getattr(stats, "pair_wins", 0) or 0)),
        max(0, int(getattr(stats, "pair_losses", 0) or 0)),
        max(0, int(getattr(stats, "pair_ties", 0) or 0)),
    )
    if sum(stats_counts) > 0 or int(getattr(stats, "total_pairs", 0) or 0) > 0:
        return stats_counts
    wins = losses = ties = 0
    for item in protocol_result.pair_feedback or ():
        comparison = str(getattr(item, "comparison", "") or "")
        if comparison == "win":
            wins += 1
        elif comparison == "loss":
            losses += 1
        else:
            ties += 1
    return wins, losses, ties


def _case_payload(item: Any) -> dict[str, Any]:
    return {
        "case_id": str(getattr(item, "case_id", "") or ""),
        "n_pairs": max(0, int(getattr(item, "n_pairs", 0) or 0)),
        "wins": max(0, int(getattr(item, "wins", 0) or 0)),
        "losses": max(0, int(getattr(item, "losses", 0) or 0)),
        "ties": max(0, int(getattr(item, "ties", 0) or 0)),
        "win_rate": getattr(item, "win_rate", None),
        "dominant_result": str(getattr(item, "dominant_result", "") or ""),
        "decisive_metric": str(getattr(item, "decisive_metric", "") or ""),
        "median_deltas": dict(getattr(item, "median_deltas", {}) or {}),
        "seed_consistency": getattr(item, "seed_consistency", None),
        "seed_pattern": str(getattr(item, "seed_pattern", "") or "uniform"),
        "case_features": dict(getattr(item, "case_features", {}) or {}),
    }


def _pair_payload(item: Any) -> dict[str, Any]:
    return {
        "case_id": str(getattr(item, "case_id", "") or ""),
        "seed": getattr(item, "seed", None),
        "comparison": str(getattr(item, "comparison", "") or ""),
        "delta": getattr(item, "delta", None),
        "case_features": dict(getattr(item, "case_features", {}) or {}),
    }


__all__ = [
    "update_branch_protocol_evidence_summary",
    "update_branch_screening_evidence_summary",
]
