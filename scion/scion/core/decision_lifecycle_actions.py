"""Branch lifecycle side-effect helpers for decision finalization."""

from __future__ import annotations

from typing import Optional

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
from scion.core.models import Branch, ProtocolResult


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


def park_lineage(
    branch: Branch,
    *,
    reason_codes: tuple[str, ...],
    checkpoint_retained: bool,
) -> None:
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
    "update_branch_lifecycle_signal_state",
]
