"""Deterministic branch scheduling status model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from scion.core.branch_hygiene import (
    MECHANISM_CONTRACT_BRANCH_LOCAL_FOLLOWUP_REASON,
    branch_code_status,
    branch_fresh_runtime_replay_blocked,
    branch_has_actionable_diagnostic,
    branch_is_parked_lineage,
    branch_lineage_status,
    branch_mechanism_contract_followup_required,
    branch_requires_repair_focus,
    branch_requires_same_mechanism_followup,
)
from scion.core.models import Branch, BranchState


PROMOTION_BOUNDARY = "not_a_promotion_or_validation_decision"
FRESH_RUNTIME_REPLAY_BLOCKED_REASON = (
    "fresh_runtime_replay_blocked_missing_identity"
)
INACTIVE_CURRENT_EVIDENCE_RELEASE_REASON = (
    "inactive_current_evidence_slot_release"
)
INVALID_CURRENT_EVIDENCE_RELEASE_REASON = (
    "invalid_current_evidence_slot_release"
)
QUALITY_REGRESSION_SLOT_RELEASE_REASON = (
    "quality_regression_without_actionable_diagnostic_slot_release"
)

_TERMINAL_STATES = frozenset({
    BranchState.PROMOTED,
    BranchState.ABANDONED,
    BranchState.PARKED_LINEAGE,
})
_PROMOTION_STATES = frozenset({
    BranchState.READY_FROZEN,
    BranchState.FROZEN_TESTING,
})
_VALIDATION_STATES = frozenset({
    BranchState.READY_VALIDATE,
    BranchState.VALIDATING,
    BranchState.VALIDATING_EXPAND,
})
_STALE_STATES = frozenset({
    BranchState.STALE,
    BranchState.STALE_WEIGHT_UPDATE,
})
_LOW_SIGNAL_TIERS = frozenset({
    "marginal",
    "neutral",
    "no_effect",
    "unclear",
    "weak_signal",
})
_NON_ACTIONABLE_TIERS = frozenset({
    "inactive",
    "invalid",
    "not_evaluated",
    "not_triggered",
})
_HARD_NEGATIVE_TIERS = frozenset({
    "quality_regression",
    "hard_negative",
    "negative",
})


@dataclass(frozen=True)
class BranchEligibility:
    """Reusable scheduling eligibility flags derived from branch state."""

    lane: str
    schedulable: bool
    consumes_active_slot: bool
    release_reason: str
    next_action_reason: str


@dataclass(frozen=True)
class BranchSchedulingStatus:
    """One source of truth for scheduler and active-slot branch semantics."""

    branch_id: str
    branch_state: str
    evidence_tier: str
    lineage_status: str
    lane: str
    schedulable: bool
    consumes_active_slot: bool
    release_reason: str
    next_action_reason: str
    promotion_boundary: str = PROMOTION_BOUNDARY
    decision_features_excluded: bool = True

    @property
    def eligibility(self) -> BranchEligibility:
        return BranchEligibility(
            lane=self.lane,
            schedulable=self.schedulable,
            consumes_active_slot=self.consumes_active_slot,
            release_reason=self.release_reason,
            next_action_reason=self.next_action_reason,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "branch_state": self.branch_state,
            "evidence_tier": self.evidence_tier,
            "lineage_status": self.lineage_status,
            "lane": self.lane,
            "schedulable": self.schedulable,
            "consumes_active_slot": self.consumes_active_slot,
            "release_reason": self.release_reason,
            "next_action_reason": self.next_action_reason,
            "promotion_boundary": self.promotion_boundary,
            "decision_features_excluded": self.decision_features_excluded,
        }


def branch_scheduling_status(
    branch: Branch | None,
    *,
    scheduler_owned_release_reason: str = "",
    has_decision_origin_park_marker: bool = False,
) -> BranchSchedulingStatus:
    """Return generic scheduling status for a branch.

    Current evidence tier takes precedence over copied/restored lineage labels.
    A stale weak-positive status alone is not enough to consume scarce active
    capacity unless the current head still has an actionable lane.
    """
    if branch is None:
        return BranchSchedulingStatus(
            branch_id="",
            branch_state="missing",
            evidence_tier="",
            lineage_status="missing",
            lane="not_schedulable",
            schedulable=False,
            consumes_active_slot=False,
            release_reason="branch_missing",
            next_action_reason="inspect_branch_state",
        )

    branch_state = _branch_state_value(branch)
    explicit_tier = _explicit_current_evidence_tier(branch)
    evidence_tier = explicit_tier or _tier_from_status(branch_code_status(branch))
    raw_lineage_status = branch_lineage_status(branch)
    lineage_status = _current_lineage_status(
        raw_lineage_status,
        evidence_tier=evidence_tier,
        explicit_current_tier=bool(explicit_tier),
    )
    status = branch_code_status(branch)

    release_reason = _release_reason(
        branch,
        status=status,
        evidence_tier=evidence_tier,
        explicit_current_tier=bool(explicit_tier),
        scheduler_owned_release_reason=scheduler_owned_release_reason,
        has_decision_origin_park_marker=has_decision_origin_park_marker,
    )
    if release_reason:
        return BranchSchedulingStatus(
            branch_id=branch.branch_id,
            branch_state=branch_state,
            evidence_tier=evidence_tier,
            lineage_status=lineage_status,
            lane="not_schedulable",
            schedulable=False,
            consumes_active_slot=False,
            release_reason=release_reason,
            next_action_reason=_next_action_for_release(release_reason),
        )

    if getattr(branch, "state", None) == BranchState.BLOCKED_INFRA:
        return BranchSchedulingStatus(
            branch_id=branch.branch_id,
            branch_state=branch_state,
            evidence_tier=evidence_tier,
            lineage_status=lineage_status,
            lane="not_schedulable",
            schedulable=False,
            consumes_active_slot=True,
            release_reason="",
            next_action_reason="infra_recovery_required",
        )

    lane, next_action_reason = _schedulable_lane(
        branch,
        status=status,
        evidence_tier=evidence_tier,
        lineage_status=lineage_status,
        explicit_current_tier=bool(explicit_tier),
    )
    schedulable = lane != "not_schedulable"
    return BranchSchedulingStatus(
        branch_id=branch.branch_id,
        branch_state=branch_state,
        evidence_tier=evidence_tier,
        lineage_status=lineage_status,
        lane=lane,
        schedulable=schedulable,
        consumes_active_slot=schedulable,
        release_reason="",
        next_action_reason=next_action_reason,
    )


def _release_reason(
    branch: Branch,
    *,
    status: str,
    evidence_tier: str,
    explicit_current_tier: bool,
    scheduler_owned_release_reason: str,
    has_decision_origin_park_marker: bool,
) -> str:
    state = getattr(branch, "state", None)
    if state in _TERMINAL_STATES:
        if branch_is_parked_lineage(branch):
            return "parked_lineage"
        return "terminal_state"
    if branch_is_parked_lineage(branch):
        return "parked_lineage"
    if branch_fresh_runtime_replay_blocked(branch):
        return FRESH_RUNTIME_REPLAY_BLOCKED_REASON
    if (
        evidence_tier in _HARD_NEGATIVE_TIERS
        and not _has_actionable_recovery(branch)
    ):
        return QUALITY_REGRESSION_SLOT_RELEASE_REASON
    if explicit_current_tier and evidence_tier in _NON_ACTIONABLE_TIERS:
        if _has_actionable_recovery(branch):
            return ""
        if evidence_tier == "invalid":
            return INVALID_CURRENT_EVIDENCE_RELEASE_REASON
        return INACTIVE_CURRENT_EVIDENCE_RELEASE_REASON
    if scheduler_owned_release_reason:
        return scheduler_owned_release_reason
    return ""


def _schedulable_lane(
    branch: Branch,
    *,
    status: str,
    evidence_tier: str,
    lineage_status: str,
    explicit_current_tier: bool,
) -> tuple[str, str]:
    state = getattr(branch, "state", None)
    if state in _PROMOTION_STATES:
        return "promotion_stage", "promotion_stage_ready"
    if state in _VALIDATION_STATES:
        return "validation_stage", "validation_stage_ready"
    if state in _STALE_STATES:
        return "stale_reconcile", "stale_reconcile_required"
    if getattr(branch, "pending_retry", False):
        return "diagnostic_followup", "pending_retry_diagnostic_followup"
    if branch_requires_repair_focus(branch) or (
        getattr(branch, "telemetry_repair_mechanism_ids", ()) or ()
    ):
        return "diagnostic_followup", "telemetry_diagnostic_followup"
    if branch_mechanism_contract_followup_required(branch):
        return "diagnostic_followup", MECHANISM_CONTRACT_BRANCH_LOCAL_FOLLOWUP_REASON
    if explicit_current_tier and evidence_tier in _NON_ACTIONABLE_TIERS:
        if _has_actionable_recovery(branch):
            return "diagnostic_followup", "current_evidence_diagnostic_followup"
        return "not_schedulable", "current_evidence_not_actionable"
    if lineage_status == "diagnostic_repair":
        return "diagnostic_followup", "effect_diagnostic_followup"
    if lineage_status in {"active_weak_positive", "restored_weak_positive"}:
        return "weak_positive_followup", "weak_positive_signal_followup"
    if lineage_status == "restored_checkpoint":
        return "low_signal_followup", "restored_checkpoint_followup"
    if evidence_tier in _LOW_SIGNAL_TIERS:
        if branch_requires_same_mechanism_followup(branch):
            return "diagnostic_followup", "low_signal_same_mechanism_followup"
        return "low_signal_followup", "low_signal_followup"
    if evidence_tier == "runtime_regression":
        return "diagnostic_followup", "runtime_diagnostic_followup"
    if status.startswith("active_") or branch_requires_same_mechanism_followup(branch):
        return "diagnostic_followup", "active_branch_followup"
    if state == BranchState.EXPLORE:
        return "clean_exploration", "active_branch_refinement"
    if state == BranchState.EXPLORE_EXPAND:
        return "low_signal_followup", "screening_expand_followup"
    return "not_schedulable", "no_scheduling_lane"


def _current_lineage_status(
    raw_lineage_status: str,
    *,
    evidence_tier: str,
    explicit_current_tier: bool,
) -> str:
    if raw_lineage_status not in {"active_weak_positive", "restored_weak_positive"}:
        return raw_lineage_status
    if not explicit_current_tier or evidence_tier == "weak_positive":
        return raw_lineage_status
    if evidence_tier in _HARD_NEGATIVE_TIERS:
        return "diagnostic_repair"
    if evidence_tier in _NON_ACTIONABLE_TIERS:
        return f"{evidence_tier}_current_head"
    if evidence_tier in _LOW_SIGNAL_TIERS or evidence_tier == "runtime_regression":
        return f"active_{evidence_tier}"
    return raw_lineage_status


def _has_actionable_recovery(branch: Branch) -> bool:
    return bool(
        getattr(branch, "pending_retry", False)
        or branch_requires_repair_focus(branch)
        or (getattr(branch, "telemetry_repair_mechanism_ids", ()) or ())
        or branch_has_actionable_diagnostic(branch)
    )


def _next_action_for_release(release_reason: str) -> str:
    if release_reason == "parked_lineage":
        return "clean_fork"
    if release_reason == "terminal_state":
        return "do_not_schedule"
    if release_reason == FRESH_RUNTIME_REPLAY_BLOCKED_REASON:
        return "clean_fork_or_restore_replay_identity"
    if release_reason in {
        INACTIVE_CURRENT_EVIDENCE_RELEASE_REASON,
        INVALID_CURRENT_EVIDENCE_RELEASE_REASON,
        QUALITY_REGRESSION_SLOT_RELEASE_REASON,
    }:
        return "clean_exploration_or_diagnostic"
    return "clean_exploration"


def _explicit_current_evidence_tier(branch: Branch) -> str:
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    if isinstance(summary, Mapping):
        tier = str(summary.get("tier") or "").strip()
        if tier:
            return tier
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "").strip()
    if tier:
        return tier
    return ""


def _tier_from_status(status: str) -> str:
    if status.startswith("active_"):
        return status.removeprefix("active_")
    if status in {"quality_regression", "active_quality_regression"}:
        return "quality_regression"
    return ""


def _branch_state_value(branch: Branch) -> str:
    state = getattr(branch, "state", None)
    return str(getattr(state, "value", state) or "")


__all__ = [
    "BranchEligibility",
    "BranchSchedulingStatus",
    "FRESH_RUNTIME_REPLAY_BLOCKED_REASON",
    "INACTIVE_CURRENT_EVIDENCE_RELEASE_REASON",
    "INVALID_CURRENT_EVIDENCE_RELEASE_REASON",
    "PROMOTION_BOUNDARY",
    "QUALITY_REGRESSION_SLOT_RELEASE_REASON",
    "branch_scheduling_status",
]
