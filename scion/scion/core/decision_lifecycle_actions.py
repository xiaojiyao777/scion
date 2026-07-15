"""Direct branch evidence and lifecycle side effects for decision finalization.

Protocol results are recorded without deriving a second screening tier or
follow-up policy. Formal decisions remain owned by the protocol gate and its
reason codes.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from scion.core.models import Branch, ProtocolResult


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

    previous_summary = dict(getattr(branch, "branch_evidence_summary", {}) or {})
    durable_keys = (
        "canonical_screening_history",
        "verified_branch_created_files",
        "verified_branch_touched_files",
    )
    durable_values = {
        key: previous_summary[key]
        for key in durable_keys
        if key in previous_summary
    }
    stats = protocol_result.stats
    reason_codes = tuple(
        dict.fromkeys(
            str(code).strip()
            for code in (
                tuple(decision_reason_codes or ())
                + tuple(protocol_result.reason_codes or ())
            )
            if str(code).strip()
        )
    )
    pair_wins, pair_losses, pair_ties = _pair_counts(protocol_result)
    summary: dict[str, Any] = {
        "stage": "screening",
        "gate_outcome": protocol_result.gate_outcome,
        "evidence_retention_status": "retained",
        "wins": max(0, int(getattr(stats, "wins", 0) or 0)),
        "losses": max(0, int(getattr(stats, "losses", 0) or 0)),
        "ties": max(0, int(getattr(stats, "ties", 0) or 0)),
        "pair_wins": pair_wins,
        "pair_losses": pair_losses,
        "pair_ties": pair_ties,
        "median_delta": getattr(stats, "median_delta", None),
        "ci_low": getattr(stats, "ci_low", None),
        "ci_high": getattr(stats, "ci_high", None),
        "statistical_status": getattr(stats, "statistical_status", None),
        "statistical_metric": getattr(stats, "statistical_metric", None),
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
        "opportunity_status": str(
            getattr(protocol_result, "opportunity_status", "") or "unknown"
        ),
        "opportunity_diagnostics": list(
            getattr(protocol_result, "opportunity_diagnostics", ()) or ()
        ),
        "mechanism_evidence": dict(
            getattr(protocol_result, "mechanism_evidence", {}) or {}
        ),
        "case_feedback": [_case_payload(item) for item in protocol_result.case_feedback],
        "pair_feedback": [_pair_payload(item) for item in protocol_result.pair_feedback],
        "runtime_cache": {
            "champion_cache_hits": max(
                0, int(getattr(protocol_result, "champion_cache_hits", 0) or 0)
            ),
            "champion_cache_misses": max(
                0, int(getattr(protocol_result, "champion_cache_misses", 0) or 0)
            ),
            "champion_cached_runtime_pairs": max(
                0,
                int(
                    getattr(protocol_result, "champion_cached_runtime_pairs", 0)
                    or 0
                ),
            ),
        },
    }
    phase_telemetry = getattr(protocol_result, "candidate_phase_telemetry_summary", None)
    if isinstance(phase_telemetry, Mapping) and phase_telemetry:
        summary["phase_telemetry_summary"] = dict(phase_telemetry)
    if reason_codes:
        summary["decision_reason_codes"] = list(reason_codes)
        summary["reason_codes"] = list(reason_codes)
    summary.update(durable_values)
    branch.branch_evidence_summary = summary


def _pair_counts(protocol_result: ProtocolResult) -> tuple[int, int, int]:
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
        "dominant_result": str(getattr(item, "dominant_result", "") or ""),
        "decisive_metric": str(getattr(item, "decisive_metric", "") or ""),
        "median_deltas": dict(getattr(item, "median_deltas", {}) or {}),
        "seed_consistency": getattr(item, "seed_consistency", None),
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
    "update_branch_screening_evidence_summary",
]
