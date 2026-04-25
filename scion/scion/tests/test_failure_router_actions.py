"""Tests for T1: FailureRouter actions executed in CampaignManager._handle_failure()."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from unittest.mock import MagicMock

import pytest

from scion.core.branch import BranchController
from scion.core.models import (
    Branch, BranchState, FailureEvent, ChampionState, OperatorConfig,
)
from scion.core.scheduler import Scheduler
from scion.failure.router import FailureRouter, RetryConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _branch(state: BranchState = BranchState.EXPLORE, retry_count: int = 0) -> Branch:
    return Branch(
        branch_id=str(uuid.uuid4()),
        state=state,
        base_champion_id=0,
        base_champion_hash="hash0",
        retry_count=retry_count,
    )


def _failure(category: str) -> FailureEvent:
    return FailureEvent(category=category, detail="test detail")


def _champion() -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="sc",
        code_snapshot_path="/tmp/snap",
        code_snapshot_hash="snap_hash",
    )


def _make_campaign_handle_failure():
    """Return a minimal stub that exposes _handle_failure for testing."""
    from scion.core.features import BudgetState

    router = FailureRouter(RetryConfig(max_llm_retries=3, max_infra_retries=5))
    budget = BudgetState(total=100, used=0)
    branch_ctrl = BranchController()
    hyp_store = MagicMock()
    hyp_store.save = MagicMock()

    class _Stub:
        def __init__(self):
            self._failure_router = router
            self._budget = budget
            self._branch_ctrl = branch_ctrl
            self._branch_hypotheses = {}
            self._branch_patches = {}
            self._hyp_store = hyp_store
            # Sprint H2 T1: failure counters required by _handle_failure
            self._failure_streak = {}
            self._total_failures = {}
            self._recent_abandoned_count = 0
            self._hard_abandon_counted_branches = set()
            self._campaign_id = "stub-campaign"
            _registry = MagicMock()
            _registry.record_event = MagicMock()
            self._registry = _registry

        # Pull in the real _handle_failure + _tick_blocked_branches
        from scion.core.campaign import CampaignManager
        _handle_failure = CampaignManager._handle_failure
        _tick_blocked_branches = CampaignManager._tick_blocked_branches
        _record_hard_abandon = CampaignManager._record_hard_abandon

    stub = _Stub()
    # Register a branch in the controller so block_infra / apply_decision work
    return stub, branch_ctrl


# ---------------------------------------------------------------------------
# retry_llm: branch stays active and gets pending_retry flag
# ---------------------------------------------------------------------------

class TestRetryLLM:
    def test_retry_llm_sets_pending_retry(self):
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        stub._handle_failure(b, _failure("proposal"))
        assert b.pending_retry is True
        assert b.state == BranchState.EXPLORE

    def test_retry_llm_increments_consecutive_counter(self):
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        stub._handle_failure(b, _failure("proposal"))
        assert b.consecutive_llm_retries == 1

    def test_retry_llm_branch_stays_schedulable_next_round(self):
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        stub._handle_failure(b, _failure("contract"))
        # Scheduler should prioritise the pending_retry branch
        sched = Scheduler()
        action = sched.select_next([b])
        assert action.action == "run_existing"
        assert action.branch.branch_id == b.branch_id

    def test_retry_llm_three_consecutive_downgrades_to_discard(self):
        """After 3 consecutive retry_llm actions the branch resets to EXPLORE without pending_retry."""
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        # Simulate 2 prior retries already recorded
        b.consecutive_llm_retries = 2
        stub._handle_failure(b, _failure("proposal"))
        # Third hit should downgrade
        assert b.pending_retry is False
        assert b.consecutive_llm_retries == 0
        assert b.state == BranchState.EXPLORE


# ---------------------------------------------------------------------------
# retry_infra: branch enters BLOCKED_INFRA, scheduler skips it
# ---------------------------------------------------------------------------

class TestRetryInfra:
    def test_infra_failure_blocks_branch(self):
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        stub._handle_failure(b, _failure("infra"))
        assert b.state == BranchState.BLOCKED_INFRA

    def test_scheduler_skips_blocked_branch(self):
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        stub._handle_failure(b, _failure("infra"))
        sched = Scheduler()
        action = sched.select_next([b])
        # Only branch is blocked — nothing schedulable, below capacity → create_new
        assert action.action == "create_new"

    def test_blocked_branch_auto_unblocks_after_3_rounds(self):
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        stub._handle_failure(b, _failure("infra"))
        assert b.state == BranchState.BLOCKED_INFRA
        # Tick 3 rounds
        for _ in range(3):
            stub._tick_blocked_branches()
        assert b.state != BranchState.BLOCKED_INFRA

    def test_second_infra_failure_abandons_branch(self):
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        # First block
        stub._handle_failure(b, _failure("infra"))
        assert b.state == BranchState.BLOCKED_INFRA
        # Manually unblock so we can hit a second infra failure
        ctrl.unblock_infra(b.branch_id)
        b.blocked_rounds = 0
        # Second infra failure → permanent abandon
        stub._handle_failure(b, _failure("infra"))
        assert b.state == BranchState.ABANDONED
        assert stub._recent_abandoned_count == 1


# ---------------------------------------------------------------------------
# discard: branch resets to EXPLORE, patch cleared
# ---------------------------------------------------------------------------

class TestDiscard:
    def test_discard_resets_to_explore(self):
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        b.state = BranchState.EXPLORE
        # verification_heavy always → discard
        stub._handle_failure(b, _failure("verification_heavy"))
        assert b.state == BranchState.EXPLORE

    def test_discard_clears_branch_patches(self):
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        bid = b.branch_id
        stub._branch_patches[bid] = MagicMock()  # simulate a patch
        stub._handle_failure(b, _failure("verification_heavy"))
        assert bid not in stub._branch_patches

    def test_discard_clears_pending_retry(self):
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        b.pending_retry = True
        b.consecutive_llm_retries = 2
        stub._handle_failure(b, _failure("verification_heavy"))
        assert b.pending_retry is False
        assert b.consecutive_llm_retries == 0
        assert stub._recent_abandoned_count == 0

    def test_abandon_fast_increments_hard_counter_once(self):
        stub, ctrl = _make_campaign_handle_failure()
        b = ctrl.create_branch(_champion())
        stub._failure_streak["verification_heavy"] = 1

        stub._handle_failure(b, _failure("verification_heavy"))
        stub._handle_failure(b, _failure("verification_heavy"))

        assert b.state == BranchState.ABANDONED
        assert stub._recent_abandoned_count == 1


# ---------------------------------------------------------------------------
# Scheduler: pending_retry prioritisation
# ---------------------------------------------------------------------------

class TestSchedulerPendingRetry:
    def test_pending_retry_branch_beats_regular_explore(self):
        from datetime import timedelta
        sched = Scheduler()
        regular = _branch(BranchState.EXPLORE)
        regular.created_at = datetime(2026, 1, 1)
        retry = _branch(BranchState.EXPLORE)
        retry.pending_retry = True
        retry.created_at = datetime(2026, 1, 1) + timedelta(seconds=10)  # newer but prioritised
        action = sched.select_next([regular, retry])
        assert action.branch.branch_id == retry.branch_id

    def test_blocked_infra_not_selected(self):
        sched = Scheduler()
        blocked = _branch(BranchState.BLOCKED_INFRA)
        normal = _branch(BranchState.EXPLORE)
        action = sched.select_next([blocked, normal])
        assert action.branch.branch_id == normal.branch_id
