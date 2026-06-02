"""Branch lifecycle side-effect helpers for decision finalization."""

from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Any, Iterable, Mapping, Optional

from scion.core.branch_hygiene import (
    BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE,
    BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
)
from scion.core.branch_lifecycle_policy import (
    BRANCH_LIFECYCLE_ARCHIVE_LINEAGE,
    BRANCH_LIFECYCLE_PARK_LINEAGE,
    BRANCH_LIFECYCLE_RETAIN_CHECKPOINT,
    BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT,
    generic_effect_status,
    generic_evidence_signature,
)
from scion.core.models import Branch, BranchState, ProtocolResult
from scion.core.screening_visibility import (
    mechanism_evidence_for_protocol,
    runtime_aggregate_exclusion_for_protocol,
)


def lifecycle_action(
    decision_reason_codes: Optional[tuple[str, ...]],
) -> str:
    reason_set = set(decision_reason_codes or ())
    if BRANCH_LIFECYCLE_ROLLBACK_TO_CHECKPOINT in reason_set:
        return "rollback_to_checkpoint"
    if BRANCH_LIFECYCLE_PARK_LINEAGE in reason_set:
        return "park_lineage"
    if BRANCH_LIFECYCLE_RETAIN_CHECKPOINT in reason_set:
        return "retain_checkpoint"
    if BRANCH_LIFECYCLE_ARCHIVE_LINEAGE in reason_set:
        return "archive_lineage"
    return "retain_head"


def update_branch_lifecycle_signal_state(
    branch: Branch,
    *,
    protocol_result: Optional[ProtocolResult],
    screening_feedback: object,
    telemetry_effect_zero: bool,
) -> None:
    if protocol_result is None or protocol_result.stats is None:
        return
    if getattr(protocol_result.stage, "value", protocol_result.stage) != "screening":
        return
    stats = protocol_result.stats
    pair_wins = max(0, int(getattr(screening_feedback, "pair_wins", 0) or 0))
    pair_losses = max(0, int(getattr(screening_feedback, "pair_losses", 0) or 0))
    effect_status = str(
        getattr(screening_feedback, "effect_status", "") or ""
    ).strip() or generic_effect_status(
        wins=max(0, int(getattr(stats, "wins", 0) or 0)),
        losses=max(0, int(getattr(stats, "losses", 0) or 0)),
        pair_wins=pair_wins,
        pair_losses=pair_losses,
        median_delta=getattr(stats, "median_delta", None),
        telemetry_effect_zero=telemetry_effect_zero,
        candidate_failed_pairs=max(
            0,
            int(getattr(stats, "candidate_failed_pairs", 0) or 0),
        ),
    )
    signature = generic_evidence_signature(
        wins=max(0, int(getattr(stats, "wins", 0) or 0)),
        losses=max(0, int(getattr(stats, "losses", 0) or 0)),
        ties=max(0, int(getattr(stats, "ties", 0) or 0)),
        median_delta=getattr(stats, "median_delta", None),
        ci_low=getattr(stats, "ci_low", None),
        ci_high=getattr(stats, "ci_high", None),
        runtime_ratio_median=getattr(stats, "runtime_ratio_median", None),
        runtime_delta_median_ms=getattr(stats, "runtime_delta_median_ms", None),
        runtime_regression_rate=getattr(stats, "runtime_regression_rate", None),
        runtime_pairs=max(0, int(getattr(stats, "runtime_pairs", 0) or 0)),
        effect_status=effect_status,
    )
    previous_signature = str(
        getattr(branch, "lifecycle_last_signal_signature", "") or ""
    )
    previous_repeat_count = max(
        0,
        int(getattr(branch, "lifecycle_signal_repeat_count", 0) or 0),
    )
    branch.lifecycle_last_signal_signature = signature
    branch.lifecycle_signal_repeat_count = (
        previous_repeat_count + 1
        if previous_signature and previous_signature == signature
        else 1
    )

    tier = str(getattr(screening_feedback, "tier", "") or "")
    if tier in {"marginal", "no_effect"}:
        branch.lifecycle_marginal_no_effect_streak = (
            max(
                0,
                int(
                    getattr(
                        branch,
                        "lifecycle_marginal_no_effect_streak",
                        0,
                    )
                    or 0
                ),
            )
            + 1
        )
    elif tier in {"weak_positive", "promotable"}:
        branch.lifecycle_marginal_no_effect_streak = 0

    if tier == "no_effect":
        prior_followups = max(
            0,
            int(
                getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0)
                or 0
            ),
        )
        prior_status = str(getattr(branch, "branch_code_status", "") or "")
        prior_tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
        if prior_followups == 0 and (
            prior_status == "active_no_effect" or prior_tier == "no_effect"
        ):
            prior_followups = 1
        branch.lifecycle_no_effect_diagnostic_followups = prior_followups + 1
    elif tier in {"weak_positive", "marginal", "promotable"}:
        branch.lifecycle_no_effect_diagnostic_followups = 0


def update_branch_screening_evidence_summary(
    branch: Branch,
    *,
    protocol_result: Optional[ProtocolResult],
    screening_feedback: object | None,
    decision_reason_codes: Iterable[str] | None = None,
) -> None:
    """Persist compact generic screening evidence for branch cards."""
    if protocol_result is None or protocol_result.stats is None:
        return
    if getattr(protocol_result.stage, "value", protocol_result.stage) != "screening":
        return
    stats = protocol_result.stats
    mechanism_evidence = mechanism_evidence_for_protocol(protocol_result)
    runtime_aggregate_exclusion = runtime_aggregate_exclusion_for_protocol(
        protocol_result
    )
    reason_codes = tuple(
        dict.fromkeys(
            str(code).strip()
            for code in (
                tuple(decision_reason_codes or ())
                + tuple(getattr(protocol_result, "reason_codes", ()) or ())
            )
            if str(code).strip()
        )
    )
    summary = {
        "stage": "screening",
        "tier": str(getattr(screening_feedback, "tier", "") or "").strip()
        or "unknown",
        "wins": max(0, int(getattr(stats, "wins", 0) or 0)),
        "losses": max(0, int(getattr(stats, "losses", 0) or 0)),
        "ties": max(0, int(getattr(stats, "ties", 0) or 0)),
        "pair_wins": max(0, int(getattr(screening_feedback, "pair_wins", 0) or 0)),
        "pair_losses": max(
            0,
            int(getattr(screening_feedback, "pair_losses", 0) or 0),
        ),
        "pair_ties": max(0, int(getattr(screening_feedback, "pair_ties", 0) or 0)),
        "median_delta": getattr(stats, "median_delta", None),
        "ci_low": getattr(stats, "ci_low", None),
        "ci_high": getattr(stats, "ci_high", None),
        "runtime_ratio_median": getattr(stats, "runtime_ratio_median", None),
        "runtime_delta_median_ms": getattr(stats, "runtime_delta_median_ms", None),
        "runtime_regression_rate": getattr(stats, "runtime_regression_rate", None),
        "runtime_pairs": max(0, int(getattr(stats, "runtime_pairs", 0) or 0)),
        "runtime_evidence_confidence": str(
            getattr(screening_feedback, "runtime_confidence", None)
            or getattr(protocol_result, "runtime_confidence", "")
            or "unknown"
        ),
        "phase_activation_summary": {
            "stage": "screening",
            "activation_status": str(
                getattr(screening_feedback, "activation_status", "") or "unknown"
            ),
            "effect_status": str(
                getattr(screening_feedback, "effect_status", "") or "unknown"
            ),
            "activation_evidence_status": str(
                mechanism_evidence.get("activation_evidence_status") or "unknown"
            ),
            "objective_effect_status": str(
                mechanism_evidence.get("objective_effect_status") or "unknown"
            ),
            "opportunity_status": str(
                getattr(screening_feedback, "opportunity_status", "")
                or getattr(protocol_result, "opportunity_status", "")
                or "unknown"
            ),
            "telemetry_outcome": getattr(branch, "last_telemetry_outcome", None),
        },
        "case_level_winners": _compact_case_results(protocol_result, "win"),
        "case_level_losses": _compact_case_results(protocol_result, "loss"),
        "runtime_cache": {
            "champion_cache_hits": max(
                0,
                int(getattr(protocol_result, "champion_cache_hits", 0) or 0),
            ),
            "champion_cache_misses": max(
                0,
                int(getattr(protocol_result, "champion_cache_misses", 0) or 0),
            ),
            "champion_cached_runtime_pairs": max(
                0,
                int(
                    getattr(
                        protocol_result,
                        "champion_cached_runtime_pairs",
                        0,
                    )
                    or 0
                ),
            ),
        },
    }
    if reason_codes:
        summary["decision_reason_codes"] = list(reason_codes)
        summary["reason_codes"] = list(reason_codes)
        summary["why_not_promoted_reason_codes"] = list(reason_codes)
    if runtime_aggregate_exclusion:
        summary["runtime_aggregate_exclusion"] = runtime_aggregate_exclusion
    branch.branch_evidence_summary = summary
    block = dict(getattr(branch, "last_branch_lifecycle_policy_block", {}) or {})
    if reason_codes:
        block.setdefault("decision_reason_codes", list(reason_codes))
        block.setdefault("reason_codes", list(reason_codes))
        block.setdefault("why_not_promoted_reason_codes", list(reason_codes))
    block.setdefault("runtime_evidence_confidence", summary["runtime_evidence_confidence"])
    block.setdefault("phase_activation_summary", summary["phase_activation_summary"])
    if runtime_aggregate_exclusion:
        block.setdefault("runtime_aggregate_exclusion", runtime_aggregate_exclusion)
    block.setdefault("case_level_winners", summary["case_level_winners"])
    block.setdefault("case_level_losses", summary["case_level_losses"])
    branch.last_branch_lifecycle_policy_block = block


def _compact_case_results(
    protocol_result: ProtocolResult,
    dominant_result: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    case_feedback = list(getattr(protocol_result, "case_feedback", ()) or ())
    items: list[dict[str, Any]] = []
    for feedback in case_feedback:
        result = str(getattr(feedback, "dominant_result", "") or "")
        if result != dominant_result:
            continue
        items.append(_case_feedback_item(feedback, protocol_result))
        if len(items) >= limit:
            return items
    if items:
        return items
    return _compact_pair_results(protocol_result, dominant_result, limit=limit)


def _case_feedback_item(
    feedback: object,
    protocol_result: ProtocolResult,
) -> dict[str, Any]:
    deltas = getattr(feedback, "median_deltas", {}) or {}
    return {
        "case_id": str(getattr(feedback, "case_id", "") or ""),
        "result": str(getattr(feedback, "dominant_result", "") or ""),
        "delta": _selected_case_delta(deltas, protocol_result),
        "effect_counters": {
            "wins": max(0, int(getattr(feedback, "wins", 0) or 0)),
            "losses": max(0, int(getattr(feedback, "losses", 0) or 0)),
            "ties": max(0, int(getattr(feedback, "ties", 0) or 0)),
            "pairs": max(0, int(getattr(feedback, "n_pairs", 0) or 0)),
        },
    }


def _compact_pair_results(
    protocol_result: ProtocolResult,
    dominant_result: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[object]] = {}
    for item in getattr(protocol_result, "pair_feedback", ()) or ():
        case_id = str(getattr(item, "case_id", "") or "")
        if case_id:
            grouped.setdefault(case_id, []).append(item)
    results: list[dict[str, Any]] = []
    for case_id, rows in sorted(grouped.items()):
        wins = sum(1 for row in rows if getattr(row, "comparison", None) == "win")
        losses = sum(1 for row in rows if getattr(row, "comparison", None) == "loss")
        ties = len(rows) - wins - losses
        result = "win" if wins > losses else "loss" if losses > wins else "tie"
        if result != dominant_result:
            continue
        deltas = [
            float(getattr(row, "delta"))
            for row in rows
            if isinstance(getattr(row, "delta", None), (int, float))
        ]
        results.append(
            {
                "case_id": case_id,
                "result": result,
                "delta": median(deltas) if deltas else None,
                "effect_counters": {
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "pairs": len(rows),
                },
            }
        )
        if len(results) >= limit:
            return results
    return results


def _selected_case_delta(
    deltas: Mapping[str, Any],
    protocol_result: ProtocolResult,
) -> float | None:
    if not isinstance(deltas, Mapping) or not deltas:
        return None
    normalized = {str(key): value for key, value in deltas.items()}
    metric = str(getattr(protocol_result.stats, "statistical_metric", "") or "")
    keys = [metric] if metric else []
    keys.extend(sorted(key for key in normalized if key not in keys))
    for key in keys:
        try:
            return float(normalized[key])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def park_lineage(
    branch: Branch,
    *,
    reason_codes: tuple[str, ...],
    checkpoint_retained: bool,
) -> None:
    branch.state = BranchState.PARKED_LINEAGE
    branch.branch_code_status = "parked_lineage"
    branch.last_telemetry_outcome = (
        "checkpoint_retained"
        if checkpoint_retained
        else "parked_lineage"
    )
    branch.branch_lifecycle_new_mechanism_ineligible = True
    branch.branch_lifecycle_reroute_reason = (
        BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK
    )
    branch.updated_at = datetime.now()
    merge_branch_lifecycle_block(
        branch,
        action="park_lineage",
        reason_codes=reason_codes,
    )


def merge_branch_lifecycle_block(
    branch: Branch,
    *,
    action: str,
    reason_codes: tuple[str, ...],
) -> None:
    existing = dict(getattr(branch, "last_branch_lifecycle_policy_block", {}) or {})
    block_count = int(
        existing.get("block_count")
        or getattr(branch, "branch_lifecycle_policy_blocks", 0)
        or 0
    ) + 1
    lifecycle_reason_codes = tuple(
        dict.fromkeys(
            [
                *tuple(existing.get("lifecycle_action_reason_codes") or ()),
                *tuple(reason_codes or ()),
            ]
        )
    )
    existing.update(
        {
            "reason": action,
            "block_count": block_count,
            "reroute_reason": BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
            "new_mechanism_ineligible_reason": (
                BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE
            ),
            "lifecycle_action_reason_codes": list(lifecycle_reason_codes),
            "rollback_count": int(getattr(branch, "rollback_count", 0) or 0),
            "lifecycle_marginal_no_effect_streak": int(
                getattr(branch, "lifecycle_marginal_no_effect_streak", 0) or 0
            ),
            "lifecycle_no_effect_diagnostic_followups": int(
                getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0)
                or 0
            ),
            "lifecycle_signal_repeat_count": int(
                getattr(branch, "lifecycle_signal_repeat_count", 0) or 0
            ),
            "lifecycle_last_signal_signature": getattr(
                branch,
                "lifecycle_last_signal_signature",
                None,
            ),
            "best_quality_checkpoint_id": getattr(
                branch,
                "best_quality_checkpoint_id",
                None,
            ),
            "last_valid_checkpoint_id": getattr(
                branch,
                "last_valid_checkpoint_id",
                None,
            ),
        }
    )
    branch.branch_lifecycle_policy_blocks = block_count
    branch.last_branch_lifecycle_policy_block = existing


__all__ = [
    "lifecycle_action",
    "merge_branch_lifecycle_block",
    "park_lineage",
    "update_branch_screening_evidence_summary",
    "update_branch_lifecycle_signal_state",
]
