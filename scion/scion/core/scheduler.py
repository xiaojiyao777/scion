"""Deterministic branch-state scheduler.

The scheduler owns only legal state selection, FIFO ordering, and active-slot
admission.  Research conclusions remain owned by the formal Decision layer.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from scion.core.models import Branch, BranchState
from scion.core.scheduling.active_slots import (
    active_slot_branches as _active_slot_branches,
)
from scion.core.scheduling.active_slots import (
    active_slot_inventory as _active_slot_inventory,
)


@dataclass(frozen=True)
class SchedulerAction:
    action: Literal["run_existing", "create_new", "at_capacity"]
    branch: Branch | None = None
    reason: str = ""
    slot: Literal["existing", "explore_new", "capacity_blocked"] = "existing"


# V3 section 12.1: state priority is lexicographic.  Queued evaluation stages
# retain creation FIFO; active research branches rejoin their tier after each
# service so one old branch cannot starve its siblings.
_PRIORITY_TIERS: tuple[frozenset[BranchState], ...] = (
    frozenset({BranchState.READY_FROZEN}),
    frozenset({BranchState.READY_VALIDATE}),
    frozenset({BranchState.STALE, BranchState.STALE_WEIGHT_UPDATE}),
    frozenset(
        {
            BranchState.EXPLORE_EXPAND,
            BranchState.VALIDATING,
            BranchState.VALIDATING_EXPAND,
            BranchState.FROZEN_TESTING,
        }
    ),
)
_RESEARCH_STATES = frozenset({BranchState.EXPLORE})
_TERMINAL_STATES = frozenset(
    {BranchState.PROMOTED, BranchState.ABANDONED}
)
# V3 sections 11.1 and 12.2: keep depth within a direction while allowing up to
# three naturally divergent directions.  Slot admission remains evidence-blind.
_DEFAULT_MAX_ACTIVE_BRANCHES = 3


class Scheduler:
    def __init__(self, max_active_branches: int = _DEFAULT_MAX_ACTIVE_BRANCHES) -> None:
        self._max_active_branches = max(0, int(max_active_branches))

    @property
    def max_active_branches(self) -> int:
        return self._max_active_branches

    def select_next(self, branches: list[Branch]) -> SchedulerAction:
        """Select one legal action without interpreting research evidence."""

        active = [branch for branch in branches if branch.state not in _TERMINAL_STATES]
        schedulable = [
            branch for branch in active if branch.state != BranchState.BLOCKED_INFRA
        ]

        for tier_index, tier in enumerate(_PRIORITY_TIERS, start=1):
            candidates = [branch for branch in schedulable if branch.state in tier]
            if candidates:
                selected = _select_fifo(candidates)
                return SchedulerAction(
                    action="run_existing",
                    branch=selected,
                    reason=f"state_priority_{tier_index}:{selected.state.value}",
                    slot="existing",
                )

        used_slots = len(active_slot_branches(active))
        research = [branch for branch in schedulable if branch.state in _RESEARCH_STATES]

        # Fill free portfolio slots deterministically.  This is capacity
        # admission, not a judgment about any existing branch's evidence.
        if used_slots < self._max_active_branches:
            return SchedulerAction(
                action="create_new",
                reason="active_slot_available",
                slot="explore_new",
            )

        if research:
            selected = _select_least_recently_served(research)
            return SchedulerAction(
                action="run_existing",
                branch=selected,
                reason="state_priority_explore_least_recently_served",
                slot="existing",
            )

        return SchedulerAction(
            action="at_capacity",
            reason="active_branch_limit_reached",
            slot="capacity_blocked",
        )


def _select_fifo(candidates: list[Branch]) -> Branch:
    return min(candidates, key=lambda branch: (branch.created_at, branch.branch_id))


def _select_least_recently_served(candidates: list[Branch]) -> Branch:
    return min(
        candidates,
        key=lambda branch: (branch.updated_at, branch.created_at, branch.branch_id),
    )


def active_slot_branches(branches: Iterable[Branch]) -> list[Branch]:
    return _active_slot_branches(branches)


def active_slot_inventory(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> dict[str, Any]:
    return _active_slot_inventory(
        branches,
        max_active_branches=max_active_branches,
    )


__all__ = [
    "_PRIORITY_TIERS",
    "Scheduler",
    "SchedulerAction",
    "active_slot_branches",
    "active_slot_inventory",
]
