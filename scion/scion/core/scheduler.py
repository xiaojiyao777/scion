from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional

from scion.core.branch_hygiene import (
    BRANCH_LIFECYCLE_REROUTE_AFTER_POLICY_BLOCK,
    CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM,
    branch_has_actionable_diagnostic,
    branch_has_retained_checkpoint,
    branch_is_parked_lineage,
    branch_lifecycle_new_mechanism_ineligible,
    branch_lineage_status,
    branch_requires_same_mechanism_followup,
)
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
_TERMINAL_STATES = frozenset({BranchState.PROMOTED, BranchState.ABANDONED})

_DEFAULT_MAX_ACTIVE_BRANCHES = 3


class Scheduler:
    def __init__(self, max_active_branches: int = _DEFAULT_MAX_ACTIVE_BRANCHES) -> None:
        self._max_active_branches = max_active_branches

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
        active_for_proposal_capacity = [
            b
            for b in active
            if _counts_toward_proposal_capacity(b)
        ]
        # BLOCKED_INFRA branches are not schedulable, though they still count
        # toward the active-branch cap until recovery/abandon clears them.
        schedulable = [
            b
            for b in active
            if b.state != BranchState.BLOCKED_INFRA
            and not branch_is_parked_lineage(b)
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
                if len(active_for_proposal_capacity) < self._max_active_branches:
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
            priority_candidates = [
                branch
                for branch in eligible_research
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
            if (
                len(active_for_proposal_capacity) < self._max_active_branches
                and all(
                    branch_requires_same_mechanism_followup(branch)
                    for branch in eligible_research
                )
            ):
                return SchedulerAction(
                    action="create_new",
                    branch=None,
                    reason=CLEAN_FORK_REQUIRED_FOR_NEW_MECHANISM,
                    slot="explore_new",
                )
            clean_research = [
                branch
                for branch in eligible_research
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
            if len(active_for_proposal_capacity) < self._max_active_branches and any(
                _established_branch(branch) for branch in eligible_research
            ):
                return SchedulerAction(
                    action="create_new",
                    branch=None,
                    reason="established_branch_portfolio_expansion",
                    slot="explore_new",
                )
            selection_pool = clean_research or eligible_research
            selected = _select_budgeted(selection_pool)
            return SchedulerAction(
                action="run_existing",
                branch=selected,
                reason=_reason_for_branch(selected),
                slot=_slot_for_branch(selected),
            )

        # No actionable branch: only create new if below capacity (§4.6 / §11.5)
        if len(active_for_proposal_capacity) >= self._max_active_branches:
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


def _counts_toward_proposal_capacity(branch: Branch) -> bool:
    if branch_is_parked_lineage(branch):
        return False
    if branch.state in _RESEARCH_STATES and _branch_lifecycle_budget_exhausted(
        branch
    ):
        return False
    if branch.state in _RESEARCH_STATES and (
        branch_lifecycle_new_mechanism_ineligible(branch)
        or _no_effect_without_actionable_diagnostic(branch)
    ):
        return False
    return True


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
