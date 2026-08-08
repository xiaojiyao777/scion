"""State, FIFO, and active-slot tests for the V3 scheduler."""
from __future__ import annotations

from datetime import datetime, timedelta

from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    install_branch_execution_hold,
)
from scion.core.models import Branch, BranchState
from scion.core.scheduler import (
    Scheduler,
    active_slot_inventory,
    branch_scheduling_status,
)


def _branch(state: BranchState, name: str, offset: int = 0) -> Branch:
    timestamp = datetime(2026, 1, 1) + timedelta(seconds=offset)
    return Branch(
        branch_id=name,
        state=state,
        base_champion_id=0,
        base_champion_hash="champion",
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_empty_portfolio_creates_branch_when_slot_available() -> None:
    action = Scheduler(max_active_branches=3).select_next([])
    assert action.action == "create_new"
    assert action.slot == "explore_new"
    assert action.reason == "active_slot_available"


def test_default_v3_portfolio_admits_three_natural_directions() -> None:
    scheduler = Scheduler()
    branch = _branch(BranchState.EXPLORE, "scientific-direction")

    assert scheduler.max_active_branches == 3
    assert scheduler.select_next([]).action == "create_new"

    action = scheduler.select_next([branch])

    assert action.action == "create_new"
    assert action.branch is None
    assert action.reason == "active_slot_available"


def test_state_priority_is_frozen_validate_stale_then_running() -> None:
    branches = [
        _branch(BranchState.FROZEN_TESTING, "running", 0),
        _branch(BranchState.STALE, "stale", 1),
        _branch(BranchState.READY_VALIDATE, "validate", 2),
        _branch(BranchState.READY_FROZEN, "frozen", 3),
    ]
    action = Scheduler(max_active_branches=4).select_next(branches)
    assert action.action == "run_existing"
    assert action.branch is branches[3]
    assert action.reason == "state_priority_1:ready_frozen"


def test_same_state_uses_created_at_then_branch_id_fifo() -> None:
    branches = [
        _branch(BranchState.READY_VALIDATE, "z", 0),
        _branch(BranchState.READY_VALIDATE, "a", 0),
        _branch(BranchState.READY_VALIDATE, "older", -1),
    ]
    first = Scheduler(max_active_branches=3).select_next(branches)
    assert first.branch is branches[2]
    second = Scheduler(max_active_branches=3).select_next(branches[:2])
    assert second.branch is branches[1]


def test_free_slot_admission_does_not_read_research_evidence() -> None:
    branch = _branch(BranchState.EXPLORE, "existing")
    branch.direction = "ignored"
    branch.branch_evidence_summary = {
        "median_delta": -100,
        "runtime_ratio_median": 9,
        "telemetry_outcome": "ignored",
    }
    action = Scheduler(max_active_branches=2).select_next([branch])
    assert action.action == "create_new"
    assert action.branch is None


def test_full_portfolio_runs_explore_fifo() -> None:
    branches = [
        _branch(BranchState.EXPLORE, "newer", 2),
        _branch(BranchState.EXPLORE, "older", 1),
    ]
    action = Scheduler(max_active_branches=2).select_next(branches)
    assert action.action == "run_existing"
    assert action.branch is branches[1]
    assert action.reason == "state_priority_explore_fifo"


def test_blocked_infra_and_execution_hold_are_not_schedulable_but_hold_slots() -> None:
    blocked = _branch(BranchState.BLOCKED_INFRA, "blocked")
    held = _branch(BranchState.EXPLORE, "held")
    install_branch_execution_hold(
        held,
        ExecutionOutcomeRecord(
            outcome=ExecutionOutcome.NOT_EVALUATED,
            reason_code="OPERATOR_RESUME_REQUIRED",
        ),
    )
    action = Scheduler(max_active_branches=2).select_next([blocked, held])
    assert action.action == "at_capacity"
    assert action.slot == "capacity_blocked"
    assert action.audit_metadata["branch_ids"] == ["blocked", "held"]
    assert branch_scheduling_status(blocked).lane == "blocked_infra"
    assert branch_scheduling_status(held).lane == "execution_hold"


def test_terminal_states_release_slots() -> None:
    branches = [
        _branch(BranchState.PROMOTED, "promoted"),
        _branch(BranchState.ABANDONED, "abandoned"),
        _branch(BranchState.PARKED_LINEAGE, "historical-parked"),
    ]
    inventory = active_slot_inventory(branches, max_active_branches=1)
    assert inventory["used"] == 0
    assert inventory["available"] == 1
    assert inventory["released_active_slot_ids"] == [
        "promoted",
        "abandoned",
        "historical-parked",
    ]


def test_scheduler_selection_is_pure() -> None:
    branch = _branch(BranchState.READY_VALIDATE, "candidate")
    before = (branch.state, branch.updated_at, dict(branch.branch_evidence_summary))
    Scheduler(max_active_branches=1).select_next([branch])
    assert (branch.state, branch.updated_at, branch.branch_evidence_summary) == before
