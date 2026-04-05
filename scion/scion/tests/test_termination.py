"""Tests for scion/core/termination.py — TerminationChecker."""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta
import pytest

from scion.core.models import Branch, BranchState
from scion.core.termination import TerminationChecker, TerminationConfig, CampaignState


def _branch(state: BranchState) -> Branch:
    return Branch(
        branch_id=str(uuid.uuid4()),
        state=state,
        base_champion_id=0,
        base_champion_hash="h",
    )


def _checker(
    max_experiments: int = 100,
    max_wall_clock_hours: float = 24.0,
    stagnation_limit: int = 10,
) -> TerminationChecker:
    return TerminationChecker(TerminationConfig(
        max_experiments=max_experiments,
        max_wall_clock_hours=max_wall_clock_hours,
        stagnation_limit=stagnation_limit,
    ))


def _state(**kwargs) -> CampaignState:
    defaults = dict(
        n_experiments=0,
        start_time=datetime.now(),
        recent_abandoned_count=0,
        active_branches=[_branch(BranchState.EXPLORE)],
        can_create_new=True,
    )
    defaults.update(kwargs)
    return CampaignState(**defaults)


# ─────────────────────────────────────────────────────────────────────────────

def test_max_experiments_stop():
    checker = _checker(max_experiments=50)
    state = _state(n_experiments=50)
    assert checker.should_stop(state) is True


def test_max_experiments_not_yet():
    checker = _checker(max_experiments=50)
    state = _state(n_experiments=49)
    assert checker.should_stop(state) is False


def test_wall_clock_exceeded():
    checker = _checker(max_wall_clock_hours=1.0)
    state = _state(start_time=datetime.now() - timedelta(hours=2))
    assert checker.should_stop(state) is True


def test_wall_clock_not_exceeded():
    checker = _checker(max_wall_clock_hours=24.0)
    state = _state(start_time=datetime.now())
    assert checker.should_stop(state) is False


def test_stagnation_stop():
    checker = _checker(stagnation_limit=5)
    state = _state(recent_abandoned_count=5)
    assert checker.should_stop(state) is True


def test_stagnation_not_yet():
    checker = _checker(stagnation_limit=5)
    state = _state(recent_abandoned_count=4)
    assert checker.should_stop(state) is False


def test_no_active_branches_and_cannot_create_new():
    checker = _checker()
    state = _state(active_branches=[], can_create_new=False)
    assert checker.should_stop(state) is True


def test_no_active_branches_but_can_create_new():
    checker = _checker()
    state = _state(active_branches=[], can_create_new=True)
    assert checker.should_stop(state) is False


def test_has_active_branches():
    checker = _checker()
    state = _state(
        active_branches=[_branch(BranchState.EXPLORE)],
        can_create_new=False,
    )
    assert checker.should_stop(state) is False


def test_all_terminal_branches_no_create():
    checker = _checker()
    state = _state(
        active_branches=[_branch(BranchState.PROMOTED), _branch(BranchState.ABANDONED)],
        can_create_new=False,
    )
    assert checker.should_stop(state) is True
