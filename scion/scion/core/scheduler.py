from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional

from scion.core.models import Branch, BranchState


@dataclass(frozen=True)
class SchedulerAction:
    action: Literal["run_existing", "create_new"]
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


class Scheduler:
    def select_next(self, branches: List[Branch]) -> SchedulerAction:
        """
        Select the next branch to process using lexicographic hard priority.

        P1: READY_FROZEN
        P2: READY_VALIDATE
        P3: STALE
        P4: EXPLORE / EXPLORE_EXPAND / VALIDATING / VALIDATING_EXPAND /
            FROZEN_TESTING / BLOCKED_INFRA
        P5: create new branch (when none of the above exist)

        Within the same tier, FIFO by branch.created_at.
        """
        for tier in _PRIORITY_TIERS:
            candidates = [b for b in branches if b.state in tier]
            if candidates:
                candidates.sort(key=lambda b: b.created_at)
                return SchedulerAction(action="run_existing", branch=candidates[0])

        return SchedulerAction(action="create_new", branch=None)
