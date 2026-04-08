from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional

from scion.core.models import Branch, BranchState


@dataclass(frozen=True)
class SchedulerAction:
    action: Literal["run_existing", "create_new", "at_capacity"]
    branch: Optional[Branch] = None


# Priority tiers (index 0 = highest priority)
_PRIORITY_TIERS: List[frozenset] = [
    frozenset({BranchState.READY_FROZEN}),
    frozenset({BranchState.READY_VALIDATE}),
    frozenset({BranchState.STALE}),
    frozenset({
        BranchState.EXPLORE,
        BranchState.EXPLORE_EXPAND,
        BranchState.VALIDATING,
        BranchState.VALIDATING_EXPAND,
        BranchState.FROZEN_TESTING,
        BranchState.BLOCKED_INFRA,
    }),
]

_DEFAULT_MAX_ACTIVE_BRANCHES = 3


class Scheduler:
    def __init__(self, max_active_branches: int = _DEFAULT_MAX_ACTIVE_BRANCHES) -> None:
        self._max_active_branches = max_active_branches

    def select_next(self, branches: List[Branch]) -> SchedulerAction:
        """
        Select the next branch to process using lexicographic hard priority.

        P1: READY_FROZEN
        P2: READY_VALIDATE
        P3: STALE
        P4: EXPLORE / EXPLORE_EXPAND / VALIDATING / VALIDATING_EXPAND /
            FROZEN_TESTING / BLOCKED_INFRA
        P5: create new branch (when none of the above exist AND under max_active_branches)
        P6: at_capacity (when no actionable branch and active count >= max_active_branches)

        Within the same tier, FIFO by branch.created_at.
        """
        for tier in _PRIORITY_TIERS:
            candidates = [b for b in branches if b.state in tier]
            if candidates:
                candidates.sort(key=lambda b: b.created_at)
                return SchedulerAction(action="run_existing", branch=candidates[0])

        # No actionable branch: only create new if below capacity (§4.6 / §11.5)
        if len(branches) >= self._max_active_branches:
            return SchedulerAction(action="at_capacity", branch=None)

        return SchedulerAction(action="create_new", branch=None)
