"""Direct active-slot accounting for scheduler admission."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from scion.core.models import Branch, BranchState

_NON_ACTIVE_STATES = frozenset(
    {
        BranchState.BLOCKED_INFRA,
        BranchState.PROMOTED,
        BranchState.ABANDONED,
    }
)


def active_slot_branches(branches: Iterable[Branch]) -> list[Branch]:
    return [branch for branch in branches if branch.state not in _NON_ACTIVE_STATES]


def active_slot_inventory(
    branches: Iterable[Branch],
    *,
    max_active_branches: int,
) -> dict[str, Any]:
    active = active_slot_branches(branches)
    limit = max(0, int(max_active_branches))
    return {
        "used": len(active),
        "max": limit,
        "available": max(0, limit - len(active)),
        "branch_ids": [branch.branch_id for branch in active],
    }


__all__ = [
    "active_slot_branches",
    "active_slot_inventory",
]
