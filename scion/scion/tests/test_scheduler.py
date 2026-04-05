"""Tests for scion/core/scheduler.py — Scheduler."""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta
import pytest

from scion.core.models import Branch, BranchState
from scion.core.scheduler import Scheduler, SchedulerAction


def _branch(state: BranchState, created_offset_s: float = 0) -> Branch:
    return Branch(
        branch_id=str(uuid.uuid4()),
        state=state,
        base_champion_id=0,
        base_champion_hash="h",
        created_at=datetime(2026, 1, 1) + timedelta(seconds=created_offset_s),
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


def test_explore_over_create_new():
    branches = [_branch(BranchState.EXPLORE)]
    action = sched.select_next(branches)
    assert action.action == "run_existing"
    assert action.branch.state == BranchState.EXPLORE


def test_fifo_within_same_tier():
    b_old = _branch(BranchState.EXPLORE, created_offset_s=0)
    b_new = _branch(BranchState.EXPLORE, created_offset_s=10)
    action = sched.select_next([b_new, b_old])
    assert action.branch.branch_id == b_old.branch_id


def test_only_terminal_branches_creates_new():
    from scion.core.models import BranchState
    branches = [
        _branch(BranchState.PROMOTED),
        _branch(BranchState.ABANDONED),
    ]
    action = sched.select_next(branches)
    assert action.action == "create_new"
