"""Deterministic branch-state scheduler.

The scheduler owns only legal state selection, FIFO ordering, and active-slot
admission.  Research conclusions remain owned by the formal Decision layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Literal, Mapping, Optional

from scion.core.execution_outcome import branch_has_execution_hold
from scion.core.models import Branch, BranchState
from scion.core.scheduling.active_slots import (
    active_slot_branches as _active_slot_branches,
    active_slot_capacity_block_metadata as _active_slot_capacity_block_metadata,
    active_slot_inventory as _active_slot_inventory,
    branch_active_slot_release_reason as _branch_active_slot_release_reason,
    branch_counts_toward_active_slots as _branch_counts_toward_active_slots,
    branch_scheduling_status as _branch_scheduling_status,
)


@dataclass(frozen=True)
class SchedulerAction:
    action: Literal["run_existing", "create_new", "at_capacity"]
    branch: Optional[Branch] = None
    reason: str = ""
    slot: Literal["existing", "explore_new", "capacity_blocked"] = "existing"
    audit_metadata: Mapping[str, Any] = field(default_factory=dict)


# V3 section 12.1: state priority is lexicographic and ties are FIFO.
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
    {BranchState.PROMOTED, BranchState.ABANDONED, BranchState.PARKED_LINEAGE}
)
# v0.4 direct runtime defaults to one branch so an EXPLORE continuation can
# consume that branch's preceding screening evidence on the next invocation.
# Broader portfolios remain an explicit scheduler configuration for ablation.
_DEFAULT_MAX_ACTIVE_BRANCHES = 1


class Scheduler:
    def __init__(self, max_active_branches: int = _DEFAULT_MAX_ACTIVE_BRANCHES) -> None:
        self._max_active_branches = max(0, int(max_active_branches))

    @property
    def max_active_branches(self) -> int:
        return self._max_active_branches

    def select_next(self, branches: List[Branch]) -> SchedulerAction:
        """Select one legal action without interpreting research evidence."""

        active = [branch for branch in branches if branch.state not in _TERMINAL_STATES]
        schedulable = [
            branch
            for branch in active
            if branch.state != BranchState.BLOCKED_INFRA
            and not branch_has_execution_hold(branch)
            and branch_scheduling_status(branch).schedulable
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
            selected = _select_fifo(research)
            return SchedulerAction(
                action="run_existing",
                branch=selected,
                reason="state_priority_explore_fifo",
                slot="existing",
            )

        return SchedulerAction(
            action="at_capacity",
            reason="active_branch_limit_reached",
            slot="capacity_blocked",
            audit_metadata=active_slot_capacity_block_metadata(
                active,
                max_active_branches=self._max_active_branches,
            ),
        )


def _select_fifo(candidates: List[Branch]) -> Branch:
    return min(candidates, key=lambda branch: (branch.created_at, branch.branch_id))


def branch_counts_toward_active_slots(branch: Branch) -> bool:
    return _branch_counts_toward_active_slots(branch)


def branch_active_slot_release_reason(branch: Branch | None) -> str:
    return _branch_active_slot_release_reason(branch)


def branch_scheduling_status(branch: Branch | None):
    return _branch_scheduling_status(branch)


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


def active_slot_capacity_block_metadata(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> dict[str, Any]:
    return _active_slot_capacity_block_metadata(
        branches,
        max_active_branches=max_active_branches,
    )


__all__ = [
    "Scheduler",
    "SchedulerAction",
    "_PRIORITY_TIERS",
    "active_slot_branches",
    "active_slot_capacity_block_metadata",
    "active_slot_inventory",
    "branch_active_slot_release_reason",
    "branch_counts_toward_active_slots",
    "branch_scheduling_status",
]
