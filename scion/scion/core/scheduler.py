from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Literal, Optional

from scion.core.branch_hygiene import (
    BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE,
    BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
    CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM,
    branch_has_actionable_diagnostic,
    branch_has_retained_checkpoint,
    branch_is_parked_lineage,
    branch_lifecycle_new_mechanism_ineligible,
    branch_lineage_status,
    branch_requires_repair_focus,
    branch_requires_same_mechanism_followup,
)
from scion.core.branch_lifecycle_policy import BRANCH_LIFECYCLE_PARK_LINEAGE
from scion.core.models import Branch, BranchState


@dataclass(frozen=True)
class SchedulerAction:
    action: Literal["run_existing", "create_new", "at_capacity"]
    branch: Optional[Branch] = None
    reason: str = ""
    slot: Literal[
        "explore_new",
        "exploit_weak_positive",
        "repair_diagnostic",
        "refine_active",
        "capacity_blocked",
    ] = "refine_active"


# High-priority tiers (index 0 = highest priority).
# BLOCKED_INFRA is intentionally excluded — those branches are not schedulable.
_HIGH_PRIORITY_TIERS: List[frozenset] = [
    frozenset({BranchState.READY_FROZEN}),
    frozenset({BranchState.READY_VALIDATE}),
    frozenset({BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE}),
    frozenset({
        BranchState.EXPLORE_EXPAND,
        BranchState.VALIDATING,
        BranchState.VALIDATING_EXPAND,
        BranchState.FROZEN_TESTING,
    }),
]
# Backward-compatible name for older white-box tests and downstream checks.
_PRIORITY_TIERS = _HIGH_PRIORITY_TIERS
_RESEARCH_STATES = frozenset({BranchState.EXPLORE})
_TERMINAL_STATES = frozenset({
    BranchState.PROMOTED,
    BranchState.ABANDONED,
    BranchState.PARKED_LINEAGE,
})

_DEFAULT_MAX_ACTIVE_BRANCHES = 3
_PLATEAU_REROUTE_REASON = "plateau_reroute_clean_fork"
ACTIVE_SLOT_HARD_CAP_RECONCILED = "active_slot_hard_cap_reconciled"
ACTIVE_SLOT_RECLAIMED_FOR_NEW_BRANCH = "active_slot_reclaimed_for_new_branch"
ACTIVE_SLOT_HARD_CAP_BLOCKED = "active_slot_hard_cap_blocked"


@dataclass(frozen=True)
class ActiveSlotReconciliation:
    mode: Literal["overflow", "new_branch_reclaim"]
    reason: str
    before_used: int
    after_used: int
    max_active_branches: int
    parked_branch_ids: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.parked_branch_ids)

    def as_audit_metadata(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "reason": self.reason,
            "before_used": self.before_used,
            "after_used": self.after_used,
            "max_active_branches": self.max_active_branches,
            "parked_branch_ids": list(self.parked_branch_ids),
        }


class Scheduler:
    def __init__(self, max_active_branches: int = _DEFAULT_MAX_ACTIVE_BRANCHES) -> None:
        self._max_active_branches = max_active_branches

    @property
    def max_active_branches(self) -> int:
        return self._max_active_branches

    def select_next(self, branches: List[Branch]) -> SchedulerAction:
        """
        Select the next branch to process using lexicographic priority plus a
        small portfolio rule for low-priority research branches.

        P1: READY_FROZEN
        P2: READY_VALIDATE
        P3: STALE
        P4: EXPLORE_EXPAND / VALIDATING / VALIDATING_EXPAND / FROZEN_TESTING
        P5: pending_retry research branches
        P6: create new branch when only established research branches exist and
            active count is below max_active_branches
        P7: run research branch by oldest updated_at
        P8: at_capacity (when no actionable branch and active count >= max_active_branches)

        BLOCKED_INFRA branches are never scheduled.
        Within the same tier, pending_retry=True branches precede others; ties
        are broken by oldest updated_at as a last-run approximation.
        """
        active = [b for b in branches if b.state not in _TERMINAL_STATES]
        active_for_slots = active_slot_branches(active)
        # BLOCKED_INFRA branches are not schedulable, though they still count
        # toward the active-branch cap until recovery/abandon clears them.
        schedulable = [
            b
            for b in active
            if b.state != BranchState.BLOCKED_INFRA
            and not branch_is_parked_lineage(b)
            and not _retained_checkpoint_no_effect_current_head(b)
            and not _branch_lifecycle_budget_exhausted(b)
        ]

        for tier in _HIGH_PRIORITY_TIERS:
            candidates = [b for b in schedulable if b.state in tier]
            if candidates:
                selected = _select_fair(candidates)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot=_slot_for_branch(selected),
                )

        research = [b for b in schedulable if b.state in _RESEARCH_STATES]
        if research:
            pending_retry = [b for b in research if b.pending_retry]
            if pending_retry:
                selected = _select_fair(pending_retry)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot="repair_diagnostic",
                )
            eligible_research = [
                branch
                for branch in research
                if not branch_lifecycle_new_mechanism_ineligible(branch)
                and not branch_is_parked_lineage(branch)
                and not _branch_lifecycle_budget_exhausted(branch)
            ]
            if not eligible_research:
                if len(active_for_slots) < self._max_active_branches:
                    return SchedulerAction(
                        action="create_new",
                        branch=None,
                        reason=BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
                        slot="repair_diagnostic",
                    )
                return SchedulerAction(
                    action="at_capacity",
                    branch=None,
                    reason="active_branch_limit_reached",
                    slot="capacity_blocked",
                )
            preferred_research = [
                branch
                for branch in eligible_research
                if not _branch_plateau_reroute_preferred(branch)
            ]
            priority_candidates = [
                branch
                for branch in preferred_research
                if _branch_research_priority(branch) <= 40
            ]
            if priority_candidates:
                selected = _select_budgeted(priority_candidates)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot=_slot_for_branch(selected),
                )
            if not preferred_research:
                if len(active_for_slots) < self._max_active_branches:
                    return SchedulerAction(
                        action="create_new",
                        branch=None,
                        reason=_PLATEAU_REROUTE_REASON,
                        slot="explore_new",
                    )
                return SchedulerAction(
                    action="at_capacity",
                    branch=None,
                    reason="active_branch_limit_reached",
                    slot="capacity_blocked",
                )
            if all(
                branch_requires_same_mechanism_followup(branch)
                for branch in eligible_research
            ):
                if len(active_for_slots) < self._max_active_branches:
                    return SchedulerAction(
                        action="create_new",
                        branch=None,
                        reason=CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM,
                        slot="explore_new",
                    )
                return SchedulerAction(
                    action="at_capacity",
                    branch=None,
                    reason="active_branch_limit_reached",
                    slot="capacity_blocked",
                )
            clean_research = [
                branch
                for branch in preferred_research
                if not branch_requires_same_mechanism_followup(branch)
            ]
            clean_candidates = [
                branch
                for branch in clean_research
                if not _established_branch(branch)
            ]
            if clean_candidates:
                selected = _select_fair(clean_candidates)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=_reason_for_branch(selected),
                    slot=_slot_for_branch(selected),
                )
            if len(active_for_slots) < self._max_active_branches and any(
                _established_branch(branch) for branch in eligible_research
            ):
                return SchedulerAction(
                    action="create_new",
                    branch=None,
                    reason="established_branch_portfolio_expansion",
                    slot="explore_new",
                )
            selection_pool = clean_research or preferred_research or eligible_research
            selected = _select_budgeted(selection_pool)
            return SchedulerAction(
                action="run_existing",
                branch=selected,
                reason=_reason_for_branch(selected),
                slot=_slot_for_branch(selected),
            )

        # No actionable branch: only create new if below capacity (§4.6 / §11.5)
        if len(active_for_slots) >= self._max_active_branches:
            return SchedulerAction(
                action="at_capacity",
                branch=None,
                reason="active_branch_limit_reached",
                slot="capacity_blocked",
            )

        return SchedulerAction(
            action="create_new",
            branch=None,
            reason="new_exploration_slot_available",
            slot="explore_new",
        )


def _select_fair(candidates: List[Branch]) -> Branch:
    return sorted(
        candidates,
        key=lambda b: (0 if b.pending_retry else 1, b.updated_at, b.created_at),
    )[0]


def _select_budgeted(candidates: List[Branch]) -> Branch:
    return sorted(
        candidates,
        key=lambda b: (
            _branch_research_priority(b),
            0 if b.pending_retry else 1,
            b.updated_at,
            b.created_at,
        ),
    )[0]


def _established_branch(branch: Branch) -> bool:
    return bool(branch.direction)


def branch_counts_toward_active_slots(branch: Branch) -> bool:
    """Return whether ``branch`` consumes a reported active lineage slot.

    Proposal scheduling may prefer a clean fork over a weak or exhausted
    follow-up, but active-slot accounting is the live lineage inventory:
    non-terminal, non-parked branches consume slots until reconciliation parks
    or otherwise terminalizes them.
    """
    if branch.state in _TERMINAL_STATES:
        return False
    if branch_is_parked_lineage(branch):
        return False
    if _retained_checkpoint_no_effect_current_head(branch):
        return False
    return True


def branch_active_slot_release_reason(branch: Branch | None) -> str:
    """Return why ``branch`` is excluded from active-slot accounting, if known."""
    if branch is None:
        return ""
    if branch.state in _TERMINAL_STATES:
        if branch_is_parked_lineage(branch):
            return "parked_lineage"
        return "terminal_state"
    if branch_is_parked_lineage(branch):
        return "parked_lineage"
    if _retained_checkpoint_no_effect_current_head(branch):
        return "retained_checkpoint_no_effect_current_head"
    return ""


def active_slot_branches(branches: Iterable[Branch]) -> list[Branch]:
    """Filter branches to the active-slot capacity pool."""
    return [
        branch
        for branch in branches
        if branch_counts_toward_active_slots(branch)
    ]


def active_slot_inventory(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> dict[str, Any]:
    """Build a status/summary inventory for active scheduling slots."""
    branch_list = list(branches)
    active = active_slot_branches(branch_list)
    parked = [
        branch
        for branch in branch_list
        if branch_is_parked_lineage(branch)
    ]
    limit = max(0, int(max_active_branches))
    used = len(active)
    return {
        "used": used,
        "max": limit,
        "available": max(0, limit - used),
        "branch_ids": [branch.branch_id for branch in active],
        "parked_lineages": len(parked),
        "parked_lineage_ids": [branch.branch_id for branch in parked],
    }


def reconcile_active_slot_overflow(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> ActiveSlotReconciliation:
    """Park deterministic low-value lineages until live active slots fit the cap."""
    branch_list = list(branches)
    limit = max(0, int(max_active_branches))
    return _reconcile_active_slots(
        branch_list,
        max_active_branches=limit,
        target_used=limit,
        mode="overflow",
        reason=ACTIVE_SLOT_HARD_CAP_RECONCILED,
        reclaim_filter=lambda _branch: True,
    )


def reclaim_active_slot_for_new_branch(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> ActiveSlotReconciliation:
    """Release one low-value active slot before admitting a clean fork."""
    branch_list = list(branches)
    limit = max(0, int(max_active_branches))
    active = active_slot_branches(branch_list)
    if limit <= 0 or len(active) < limit:
        return ActiveSlotReconciliation(
            mode="new_branch_reclaim",
            reason=ACTIVE_SLOT_RECLAIMED_FOR_NEW_BRANCH,
            before_used=len(active),
            after_used=len(active),
            max_active_branches=limit,
        )
    return _reconcile_active_slots(
        branch_list,
        max_active_branches=limit,
        target_used=limit - 1,
        mode="new_branch_reclaim",
        reason=ACTIVE_SLOT_RECLAIMED_FOR_NEW_BRANCH,
        reclaim_filter=_eligible_new_branch_slot_reclaim,
    )


def active_slot_capacity_block_metadata(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> dict[str, Any]:
    active = active_slot_branches(list(branches))
    limit = max(0, int(max_active_branches))
    return {
        "reason": ACTIVE_SLOT_HARD_CAP_BLOCKED,
        "used": len(active),
        "max_active_branches": limit,
        "branch_ids": [branch.branch_id for branch in active],
    }


def _reconcile_active_slots(
    branches: list[Branch],
    *,
    max_active_branches: int,
    target_used: int,
    mode: Literal["overflow", "new_branch_reclaim"],
    reason: str,
    reclaim_filter: Any,
) -> ActiveSlotReconciliation:
    active = active_slot_branches(branches)
    before_used = len(active)
    target = max(0, int(target_used))
    if before_used <= target:
        return ActiveSlotReconciliation(
            mode=mode,
            reason=reason,
            before_used=before_used,
            after_used=before_used,
            max_active_branches=max_active_branches,
        )

    candidates = sorted(
        [branch for branch in active if reclaim_filter(branch)],
        key=_active_slot_reclaim_sort_key,
    )
    parked: list[str] = []
    for branch in candidates:
        if len(active_slot_branches(branches)) <= target:
            break
        _park_active_slot_branch(
            branch,
            reason=reason,
            mode=mode,
            max_active_branches=max_active_branches,
            before_used=before_used,
        )
        parked.append(branch.branch_id)
    after_used = len(active_slot_branches(branches))
    return ActiveSlotReconciliation(
        mode=mode,
        reason=reason,
        before_used=before_used,
        after_used=after_used,
        max_active_branches=max_active_branches,
        parked_branch_ids=tuple(parked),
    )


def _eligible_new_branch_slot_reclaim(branch: Branch) -> bool:
    if branch.state not in _RESEARCH_STATES:
        return False
    return (
        _branch_lifecycle_budget_exhausted(branch)
        or branch_lifecycle_new_mechanism_ineligible(branch)
        or _no_effect_without_actionable_diagnostic(branch)
        or _branch_plateau_reroute_preferred(branch)
    )


def _active_slot_reclaim_sort_key(branch: Branch) -> tuple[Any, ...]:
    status = branch_lineage_status(branch)
    if _branch_lifecycle_budget_exhausted(branch):
        bucket = 0
    elif branch_lifecycle_new_mechanism_ineligible(branch):
        bucket = 1
    elif _no_effect_without_actionable_diagnostic(branch):
        bucket = 2
    elif _branch_plateau_reroute_preferred(branch):
        bucket = 3
    elif status == "active_no_effect":
        bucket = 4
    elif status == "active_marginal":
        bucket = 5
    elif branch.state == BranchState.BLOCKED_INFRA:
        bucket = 10
    elif branch.state in _RESEARCH_STATES:
        bucket = 20
    elif branch.state in {BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE}:
        bucket = 30
    else:
        bucket = 40
    if getattr(branch, "pending_retry", False):
        bucket += 25
    policy_blocks = max(
        0,
        int(getattr(branch, "branch_lifecycle_policy_blocks", 0) or 0),
    )
    return (
        bucket,
        1 if branch_has_retained_checkpoint(branch) else 0,
        -policy_blocks,
        getattr(branch, "updated_at", datetime.min),
        getattr(branch, "created_at", datetime.min),
        branch.branch_id,
    )


def _park_active_slot_branch(
    branch: Branch,
    *,
    reason: str,
    mode: str,
    max_active_branches: int,
    before_used: int,
) -> None:
    now = datetime.now()
    existing = dict(getattr(branch, "last_branch_lifecycle_policy_block", {}) or {})
    block_count = (
        int(
            existing.get("block_count")
            or getattr(branch, "branch_lifecycle_policy_blocks", 0)
            or 0
        )
        + 1
    )
    lifecycle_codes = list(existing.get("lifecycle_action_reason_codes") or ())
    if BRANCH_LIFECYCLE_PARK_LINEAGE not in lifecycle_codes:
        lifecycle_codes.append(BRANCH_LIFECYCLE_PARK_LINEAGE)
    existing.update(
        {
            "reason": reason,
            "detail": (
                f"{reason}: active_slots.used={before_used} "
                f"max_active_branches={max_active_branches}"
            ),
            "recorded_at": now.isoformat(),
            "block_count": block_count,
            "reroute_reason": BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
            "new_mechanism_ineligible_reason": (
                BRANCH_LIFECYCLE_NEW_MECHANISM_INELIGIBLE
            ),
            "lifecycle_action_reason_codes": lifecycle_codes,
            "active_slot_reconciliation": {
                "mode": mode,
                "before_used": before_used,
                "max_active_branches": max_active_branches,
            },
            "active_slot_status": "parked_lineage",
            "next_selection": "excluded_from_active_slot_pool",
        }
    )
    branch.state = BranchState.PARKED_LINEAGE
    branch.branch_code_status = "parked_lineage"
    branch.last_telemetry_outcome = reason
    branch.branch_lifecycle_policy_blocks = block_count
    branch.branch_lifecycle_new_mechanism_ineligible = True
    branch.branch_lifecycle_reroute_reason = (
        BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK
    )
    branch.last_branch_lifecycle_policy_block = existing
    branch.updated_at = now


def _branch_lifecycle_budget_exhausted(branch: Branch) -> bool:
    if branch.state not in _RESEARCH_STATES:
        return False
    return _rollback_budget_exhausted(branch) or _marginal_loop_exhausted(branch)


def _rollback_budget_exhausted(branch: Branch) -> bool:
    return (
        max(0, int(getattr(branch, "rollback_count", 0) or 0)) >= 2
        and (
            bool(getattr(branch, "best_quality_checkpoint_id", None))
            or bool(getattr(branch, "last_valid_checkpoint_id", None))
        )
    )


def _marginal_loop_exhausted(branch: Branch) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    if status not in {"active_marginal", "active_no_effect"} and tier not in {
        "marginal",
        "no_effect",
    }:
        return False
    repeated = max(
        0,
        int(getattr(branch, "lifecycle_signal_repeat_count", 0) or 0),
    )
    marginal_or_no_effect_streak = max(
        0,
        int(getattr(branch, "lifecycle_marginal_no_effect_streak", 0) or 0),
    )
    no_effect_followups = max(
        0,
        int(getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0) or 0),
    )
    return (
        marginal_or_no_effect_streak >= 2
        and repeated >= 2
        or no_effect_followups >= 2
    )


def _branch_plateau_reroute_preferred(branch: Branch) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    repeated = max(
        0,
        int(getattr(branch, "lifecycle_signal_repeat_count", 0) or 0),
    )
    marginal_or_no_effect_streak = max(
        0,
        int(getattr(branch, "lifecycle_marginal_no_effect_streak", 0) or 0),
    )
    no_effect_followups = max(
        0,
        int(getattr(branch, "lifecycle_no_effect_diagnostic_followups", 0) or 0),
    )
    if (
        status in {"active_marginal", "active_no_effect"}
        or tier in {"marginal", "no_effect"}
    ):
        return marginal_or_no_effect_streak >= 2 or no_effect_followups >= 1
    if status == "active_weak_positive" or tier == "weak_positive":
        return repeated >= 2
    return False


def _branch_research_priority(branch: Branch) -> int:
    status = branch_lineage_status(branch)
    if getattr(branch, "pending_retry", False):
        return 0
    if status in {"active_weak_positive", "restored_weak_positive"}:
        return 10
    if status == "restored_checkpoint":
        return 20
    if status == "active_marginal":
        return 30
    if branch_has_actionable_diagnostic(branch):
        return 40
    if not _established_branch(branch):
        return 50
    if _no_effect_without_actionable_diagnostic(branch):
        return 70
    if branch_has_retained_checkpoint(branch):
        return 80
    return 60


def _no_effect_without_actionable_diagnostic(branch: Branch) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    return (
        (status == "active_no_effect" or tier == "no_effect")
        and not branch_has_actionable_diagnostic(branch)
    )


def _retained_checkpoint_no_effect_current_head(branch: Branch) -> bool:
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    current_no_effect = status in {"active_no_effect", "active_neutral"} or tier in {
        "no_effect",
        "neutral",
    }
    if not current_no_effect or not branch_has_retained_checkpoint(branch):
        return False
    if getattr(branch, "pending_retry", False):
        return False
    if branch_requires_repair_focus(branch):
        return False
    if getattr(branch, "telemetry_repair_mechanism_ids", ()) or ():
        return False
    return True


def _slot_for_branch(
    branch: Branch,
) -> Literal[
    "explore_new",
    "exploit_weak_positive",
    "repair_diagnostic",
    "refine_active",
    "capacity_blocked",
]:
    if getattr(branch, "pending_retry", False):
        return "repair_diagnostic"
    lineage_status = branch_lineage_status(branch)
    if lineage_status in {"active_weak_positive", "restored_weak_positive"}:
        return "exploit_weak_positive"
    if lineage_status == "restored_checkpoint":
        return "refine_active"
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    diagnostic_tiers = {
        "inactive",
        "invalid",
        "no_effect",
        "quality_regression",
        "runtime_regression",
    }
    diagnostic_statuses = {
        "discarded",
        "regressed_followup",
        "telemetry_wiring_suspect",
        "telemetry_invalid",
        *(f"active_{item}" for item in diagnostic_tiers),
    }
    if status in diagnostic_statuses:
        return "repair_diagnostic"
    if tier in diagnostic_tiers:
        return "repair_diagnostic"
    return "refine_active"


def _reason_for_branch(branch: Branch) -> str:
    if getattr(branch, "pending_retry", False):
        return "pending_retry_diagnostic_followup"
    slot = _slot_for_branch(branch)
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    if slot == "exploit_weak_positive":
        if branch_lineage_status(branch) == "restored_weak_positive":
            return "restored_weak_positive_checkpoint_followup"
        return "weak_positive_signal_followup"
    if branch_lineage_status(branch) == "restored_checkpoint":
        return "restored_checkpoint_followup"
    if slot == "repair_diagnostic":
        if status in {"telemetry_wiring_suspect", "telemetry_invalid"}:
            return "telemetry_diagnostic_followup"
        if status == "active_runtime_regression" or tier == "runtime_regression":
            return "runtime_diagnostic_followup"
        if _no_effect_without_actionable_diagnostic(branch):
            return "no_effect_without_actionable_diagnostic_deprioritized"
        if status.startswith("active_") or tier:
            return "effect_diagnostic_followup"
        return "diagnostic_followup"
    return "active_branch_refinement"
