"""Pure active-slot accounting.

Slot accounting never mutates branch state.  Only a formal Decision applied by
the BranchController may promote, abandon, or otherwise transition a branch.
"""
from __future__ import annotations

from typing import Any, Iterable

from scion.core.models import Branch
from scion.core.scheduling.status import BranchSchedulingStatus, branch_scheduling_status


ACTIVE_SLOT_HARD_CAP_BLOCKED = "active_slot_hard_cap_blocked"


def branch_counts_toward_active_slots(branch: Branch) -> bool:
    return branch_scheduling_status(branch).consumes_active_slot


def branch_active_slot_release_reason(branch: Branch | None) -> str:
    return branch_scheduling_status(branch).release_reason


def active_slot_branches(branches: Iterable[Branch]) -> list[Branch]:
    return [branch for branch in branches if branch_counts_toward_active_slots(branch)]


def active_slot_inventory(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> dict[str, Any]:
    branch_list = list(branches)
    statuses = [branch_scheduling_status(branch) for branch in branch_list]
    active = [
        branch
        for branch, status in zip(branch_list, statuses)
        if status.consumes_active_slot
    ]
    released = [
        (branch, status)
        for branch, status in zip(branch_list, statuses)
        if not status.consumes_active_slot
    ]
    limit = max(0, int(max_active_branches))
    return {
        "used": len(active),
        "max": limit,
        "available": max(0, limit - len(active)),
        "branch_ids": [branch.branch_id for branch in active],
        "released_active_slots": len(released),
        "released_active_slot_ids": [branch.branch_id for branch, _ in released],
        "released_active_slot_reasons": {
            branch.branch_id: status.release_reason for branch, status in released
        },
        "branch_scheduling_statuses": [status.as_dict() for status in statuses],
    }


def active_slot_capacity_block_metadata(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> dict[str, Any]:
    inventory = active_slot_inventory(
        branches,
        max_active_branches=max_active_branches,
    )
    return {
        "reason": ACTIVE_SLOT_HARD_CAP_BLOCKED,
        "used": inventory["used"],
        "max_active_branches": inventory["max"],
        "branch_ids": list(inventory["branch_ids"]),
        "branch_scheduling_statuses": list(
            inventory["branch_scheduling_statuses"]
        ),
    }


__all__ = [
    "ACTIVE_SLOT_HARD_CAP_BLOCKED",
    "BranchSchedulingStatus",
    "active_slot_branches",
    "active_slot_capacity_block_metadata",
    "active_slot_inventory",
    "branch_active_slot_release_reason",
    "branch_counts_toward_active_slots",
    "branch_scheduling_status",
]
