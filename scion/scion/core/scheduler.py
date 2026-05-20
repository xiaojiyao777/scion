from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional

from scion.core.models import Branch, BranchState


@dataclass(frozen=True)
class SchedulerAction:
    action: Literal["run_existing", "create_new", "at_capacity"]
    branch: Optional[Branch] = None


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
        # BLOCKED_INFRA branches are not schedulable, though they still count
        # toward the active-branch cap until recovery/abandon clears them.
        schedulable = [b for b in active if b.state != BranchState.BLOCKED_INFRA]

        for tier in _HIGH_PRIORITY_TIERS:
            candidates = [b for b in schedulable if b.state in tier]
            if candidates:
                return SchedulerAction(
                    action="run_existing",
                    branch=_select_fair(candidates),
                )

        research = [b for b in schedulable if b.state in _RESEARCH_STATES]
        if research:
            pending_retry = [b for b in research if b.pending_retry]
            if pending_retry:
                return SchedulerAction(
                    action="run_existing",
                    branch=_select_fair(pending_retry),
                )
            if len(active) < self._max_active_branches and any(
                _established_branch(branch) for branch in research
            ):
                return SchedulerAction(action="create_new", branch=None)
            return SchedulerAction(
                action="run_existing",
                branch=_select_fair(research),
            )

        # No actionable branch: only create new if below capacity (§4.6 / §11.5)
        if len(active) >= self._max_active_branches:
            return SchedulerAction(action="at_capacity", branch=None)

        return SchedulerAction(action="create_new", branch=None)


def _select_fair(candidates: List[Branch]) -> Branch:
    return sorted(
        candidates,
        key=lambda b: (0 if b.pending_retry else 1, b.updated_at, b.created_at),
    )[0]


def _established_branch(branch: Branch) -> bool:
    return bool(branch.direction)
