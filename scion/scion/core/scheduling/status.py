"""Pure branch-state scheduling status."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scion.core.execution_outcome import branch_has_execution_hold
from scion.core.models import Branch, BranchState


_TERMINAL_STATES = frozenset(
    {BranchState.PROMOTED, BranchState.ABANDONED, BranchState.PARKED_LINEAGE}
)
_LEGAL_SCHEDULABLE_STATES = frozenset(
    {
        BranchState.EXPLORE,
        BranchState.EXPLORE_EXPAND,
        BranchState.READY_VALIDATE,
        BranchState.VALIDATING,
        BranchState.VALIDATING_EXPAND,
        BranchState.READY_FROZEN,
        BranchState.FROZEN_TESTING,
        BranchState.STALE,
        BranchState.STALE_WEIGHT_UPDATE,
    }
)


@dataclass(frozen=True)
class BranchSchedulingStatus:
    branch_id: str
    branch_state: str
    lane: str
    schedulable: bool
    consumes_active_slot: bool
    release_reason: str
    next_action_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "branch_state": self.branch_state,
            "lane": self.lane,
            "schedulable": self.schedulable,
            "consumes_active_slot": self.consumes_active_slot,
            "release_reason": self.release_reason,
            "next_action_reason": self.next_action_reason,
        }


def branch_scheduling_status(branch: Branch | None) -> BranchSchedulingStatus:
    if branch is None:
        return BranchSchedulingStatus(
            branch_id="",
            branch_state="missing",
            lane="not_schedulable",
            schedulable=False,
            consumes_active_slot=False,
            release_reason="branch_missing",
            next_action_reason="",
        )

    state = branch.state
    state_value = state.value
    if state in _TERMINAL_STATES:
        return BranchSchedulingStatus(
            branch_id=branch.branch_id,
            branch_state=state_value,
            lane="terminal",
            schedulable=False,
            consumes_active_slot=False,
            release_reason=state_value,
            next_action_reason="",
        )
    if state == BranchState.BLOCKED_INFRA:
        return BranchSchedulingStatus(
            branch_id=branch.branch_id,
            branch_state=state_value,
            lane="blocked_infra",
            schedulable=False,
            consumes_active_slot=True,
            release_reason="",
            next_action_reason="operator_resume_required",
        )
    if branch_has_execution_hold(branch):
        return BranchSchedulingStatus(
            branch_id=branch.branch_id,
            branch_state=state_value,
            lane="execution_hold",
            schedulable=False,
            consumes_active_slot=True,
            release_reason="",
            next_action_reason="operator_resume_required",
        )
    schedulable = state in _LEGAL_SCHEDULABLE_STATES
    return BranchSchedulingStatus(
        branch_id=branch.branch_id,
        branch_state=state_value,
        lane=state_value if schedulable else "not_schedulable",
        schedulable=schedulable,
        consumes_active_slot=True,
        release_reason="" if schedulable else "unsupported_state",
        next_action_reason=state_value if schedulable else "",
    )


__all__ = ["BranchSchedulingStatus", "branch_scheduling_status"]
