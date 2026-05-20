"""Tests for scion/core/scheduler.py — Scheduler."""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta
import pytest

from scion.core.models import Branch, BranchState
from scion.core.scheduler import Scheduler, SchedulerAction


def _branch(
    state: BranchState,
    created_offset_s: float = 0,
    updated_offset_s: float | None = None,
) -> Branch:
    created_at = datetime(2026, 1, 1) + timedelta(seconds=created_offset_s)
    return Branch(
        branch_id=str(uuid.uuid4()),
        state=state,
        base_champion_id=0,
        base_champion_hash="h",
        created_at=created_at,
        updated_at=(
            datetime(2026, 1, 1)
            + timedelta(
                seconds=created_offset_s
                if updated_offset_s is None
                else updated_offset_s
            )
        ),
    )


sched = Scheduler()


def test_no_branches_creates_new():
    action = sched.select_next([])
    assert action.action == "create_new"
    assert action.branch is None


def test_ready_frozen_has_highest_priority():
    branches = [
        _branch(BranchState.READY_VALIDATE),
        _branch(BranchState.EXPLORE),
        _branch(BranchState.READY_FROZEN),
        _branch(BranchState.STALE),
    ]
    action = sched.select_next(branches)
    assert action.action == "run_existing"
    assert action.branch.state == BranchState.READY_FROZEN


def test_ready_validate_over_stale():
    branches = [
        _branch(BranchState.STALE),
        _branch(BranchState.READY_VALIDATE),
        _branch(BranchState.EXPLORE),
    ]
    action = sched.select_next(branches)
    assert action.branch.state == BranchState.READY_VALIDATE


def test_stale_over_explore():
    branches = [
        _branch(BranchState.EXPLORE),
        _branch(BranchState.STALE),
    ]
    action = sched.select_next(branches)
    assert action.branch.state == BranchState.STALE


def test_unestablished_explore_over_create_new():
    branches = [_branch(BranchState.EXPLORE)]
    action = sched.select_next(branches)
    assert action.action == "run_existing"
    assert action.branch.state == BranchState.EXPLORE


def test_established_explore_under_capacity_creates_new_branch():
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: bounded construction"

    action = Scheduler(max_active_branches=3).select_next([branch])

    assert action.action == "create_new"
    assert action.branch is None


def test_verified_code_hash_without_direction_does_not_create_new_branch():
    branch = _branch(BranchState.EXPLORE)
    branch.current_code_hash = "candidate"
    branch.last_clean_code_hash = "candidate"

    action = Scheduler(max_active_branches=3).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch


def test_pending_retry_under_capacity_runs_existing_branch():
    branch = _branch(BranchState.EXPLORE)
    branch.direction = "solver: bounded construction"
    branch.pending_retry = True

    action = Scheduler(max_active_branches=3).select_next([branch])

    assert action.action == "run_existing"
    assert action.branch is branch


def test_at_capacity_multiple_explore_branches_selects_oldest_updated_at():
    b_recent = _branch(
        BranchState.EXPLORE,
        created_offset_s=0,
        updated_offset_s=30,
    )
    b_oldest_updated = _branch(
        BranchState.EXPLORE,
        created_offset_s=10,
        updated_offset_s=5,
    )
    b_middle = _branch(
        BranchState.EXPLORE,
        created_offset_s=20,
        updated_offset_s=15,
    )
    for branch in (b_recent, b_oldest_updated, b_middle):
        branch.direction = "solver: established"

    action = Scheduler(max_active_branches=3).select_next(
        [b_recent, b_middle, b_oldest_updated]
    )

    assert action.action == "run_existing"
    assert action.branch.branch_id == b_oldest_updated.branch_id


def test_fifo_within_same_tier_for_unestablished_branches():
    b_old = _branch(BranchState.EXPLORE, created_offset_s=0)
    b_new = _branch(BranchState.EXPLORE, created_offset_s=10)
    action = sched.select_next([b_new, b_old])
    assert action.branch.branch_id == b_old.branch_id


def test_ready_validate_prioritized_over_create_new_under_capacity():
    explore = _branch(BranchState.EXPLORE)
    explore.direction = "solver: established"
    ready = _branch(BranchState.READY_VALIDATE)

    action = Scheduler(max_active_branches=3).select_next([explore, ready])

    assert action.action == "run_existing"
    assert action.branch.branch_id == ready.branch_id


def test_ready_frozen_prioritized_over_create_new_under_capacity():
    explore = _branch(BranchState.EXPLORE)
    explore.current_code_hash = "candidate"
    ready = _branch(BranchState.READY_FROZEN)

    action = Scheduler(max_active_branches=3).select_next([explore, ready])

    assert action.action == "run_existing"
    assert action.branch.branch_id == ready.branch_id


def test_explore_expand_prioritized_over_create_new_under_capacity():
    explore = _branch(BranchState.EXPLORE)
    explore.direction = "solver: established"
    expand = _branch(BranchState.EXPLORE_EXPAND)

    action = Scheduler(max_active_branches=3).select_next([explore, expand])

    assert action.action == "run_existing"
    assert action.branch.branch_id == expand.branch_id


def test_only_terminal_branches_creates_new():
    from scion.core.models import BranchState
    branches = [
        _branch(BranchState.PROMOTED),
        _branch(BranchState.ABANDONED),
    ]
    action = sched.select_next(branches)
    assert action.action == "create_new"
