"""Sprint I unit tests: T4 soft-abandon separation, PROMOTE counter resets,
soft-stagnation locus diversification, hard-stagnation escape."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from scion.core.branch import BranchController, StateTransitionError
from scion.core.campaign import CampaignManager
from scion.core.models import (
    Branch, BranchState, ChampionState, Decision, HypothesisProposal,
    HypothesisRecord, PatchProposal, ProtocolResult, StepRecord,
)
from scion.core.termination import CampaignState, TerminationChecker, TerminationConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_champion(tmpdir: Optional[str] = None) -> ChampionState:
    return ChampionState(
        version=1,
        code_snapshot_path=tmpdir or tempfile.mkdtemp(),
        solver_config_hash="abc",
        code_snapshot_hash="abc123",
        operator_pool={},
    )


def _make_hypothesis(change_locus: str = "vehicle_level") -> HypothesisProposal:
    return HypothesisProposal(
        change_locus=change_locus,
        hypothesis_text="test hypothesis",
        action="modify",
    )


def _make_step(
    round_num: int = 0,
    branch_id: str = "b1",
    change_locus: str = "vehicle_level",
    decision: Optional[Decision] = None,
) -> StepRecord:
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=_make_hypothesis(change_locus),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=None,
        decision=decision,
        failure_stage=None,
        failure_detail=None,
    )


def _make_campaign(**overrides) -> CampaignManager:
    """Create a minimal CampaignManager with mocked dependencies."""
    tmpdir = tempfile.mkdtemp()
    champion = _make_champion(tmpdir)
    spec = MagicMock()
    spec.search_space.frozen = []
    spec.operator_categories = []
    spec.parameter_search.enabled = False

    defaults = dict(
        problem_spec=spec,
        protocol_config=MagicMock(),
        split_manifest=MagicMock(),
        seed_ledger=MagicMock(),
        llm_client=MagicMock(),
        champion=champion,
        campaign_dir=tmpdir,
        termination_config=TerminationConfig(),
    )
    defaults.update(overrides)
    return CampaignManager(**defaults)


def _register_branch(cm: CampaignManager, bid: str) -> Branch:
    """Register a branch in the controller directly and return it."""
    branch = Branch(
        branch_id=bid,
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="abc123",
    )
    cm._branch_ctrl._branches[bid] = branch
    return branch


# ===========================================================================
# I1: T4 soft-abandon does not affect hard stagnation counter
# ===========================================================================

class TestI1SoftAbandon:
    def test_t4_soft_abandon_does_not_increment_hard_counter(self):
        """T4 path (wr<0.3) must not increment _recent_abandoned_count."""
        cm = _make_campaign()
        assert cm._recent_abandoned_count == 0
        assert cm._soft_abandon_streak == 0

        branch = _register_branch(cm, "b1")
        cm._apply_soft_abandon("b1", branch, None)
        cm._soft_abandon_streak += 1

        assert cm._recent_abandoned_count == 0
        assert cm._soft_abandon_streak == 1

    def test_t4_soft_abandon_increments_soft_streak(self):
        """Consecutive T4 abandons accumulate in _soft_abandon_streak only."""
        cm = _make_campaign()
        for i in range(3):
            bid = f"b{i}"
            branch = _register_branch(cm, bid)
            cm._apply_soft_abandon(bid, branch, None)
            cm._soft_abandon_streak += 1

        assert cm._soft_abandon_streak == 3
        assert cm._recent_abandoned_count == 0

    def test_normal_abandon_increments_hard_counter(self):
        """Non-T4 ABANDON must increment _recent_abandoned_count, not _soft_abandon_streak."""
        cm = _make_campaign()
        initial_soft = cm._soft_abandon_streak

        # Simulate normal ABANDON dispatch
        cm._recent_abandoned_count += 1

        assert cm._recent_abandoned_count == 1
        assert cm._soft_abandon_streak == initial_soft

    def test_t4_branch_state_becomes_abandoned(self):
        """After soft_abandon, branch state must be ABANDONED."""
        cm = _make_campaign()
        branch = _register_branch(cm, "b1")
        cm._apply_soft_abandon("b1", branch, None)

        updated = cm._branch_ctrl.get_branch("b1")
        assert updated.state == BranchState.ABANDONED


# ===========================================================================
# I2: PROMOTE resets counters
# ===========================================================================

class TestI2PromoteReset:
    def _setup_for_promote(self) -> CampaignManager:
        cm = _make_campaign()
        cm._recent_abandoned_count = 5
        cm._soft_abandon_streak = 7
        cm._hard_stagnation_escape_used = True

        # Register branch and give it a workspace
        branch = _register_branch(cm, "bp")
        ws = tempfile.mkdtemp()
        cm._branch_workspaces["bp"] = ws
        return cm

    def test_promote_resets_hard_counter(self):
        cm = self._setup_for_promote()
        branch = cm._branch_ctrl.get_branch("bp")
        cm._on_promote(branch)
        assert cm._recent_abandoned_count == 0

    def test_promote_resets_soft_streak(self):
        cm = self._setup_for_promote()
        branch = cm._branch_ctrl.get_branch("bp")
        cm._on_promote(branch)
        assert cm._soft_abandon_streak == 0

    def test_promote_resets_escape_used(self):
        cm = self._setup_for_promote()
        branch = cm._branch_ctrl.get_branch("bp")
        cm._on_promote(branch)
        assert cm._hard_stagnation_escape_used is False


# ===========================================================================
# I3: Soft stagnation triggers locus diversification
# ===========================================================================

class TestI3SoftStagnation:
    def test_soft_stagnation_triggers_at_limit(self):
        """When _soft_abandon_streak reaches soft_stagnation_limit, forced_next_locus is set."""
        cm = _make_campaign(termination_config=TerminationConfig(soft_stagnation_limit=15))
        cm._soft_abandon_streak = 15
        for i in range(15):
            cm._step_history.append(_make_step(i, change_locus="vehicle_level"))

        cm._check_soft_stagnation()

        assert cm._forced_next_locus is not None

    def test_soft_stagnation_below_limit_no_action(self):
        """Below limit, no forced locus is set."""
        cm = _make_campaign(termination_config=TerminationConfig(soft_stagnation_limit=15))
        cm._soft_abandon_streak = 14
        cm._check_soft_stagnation()
        assert cm._forced_next_locus is None

    def test_soft_stagnation_flips_vehicle_to_order(self):
        """Dominant vehicle_level → forced order_level."""
        cm = _make_campaign(termination_config=TerminationConfig(soft_stagnation_limit=5))
        cm._soft_abandon_streak = 5
        for i in range(5):
            cm._step_history.append(_make_step(i, change_locus="vehicle_level"))

        cm._check_soft_stagnation()
        assert cm._forced_next_locus == "order_level"

    def test_soft_stagnation_flips_order_to_vehicle(self):
        """Dominant order_level → forced vehicle_level."""
        cm = _make_campaign(termination_config=TerminationConfig(soft_stagnation_limit=5))
        cm._soft_abandon_streak = 5
        for i in range(5):
            cm._step_history.append(_make_step(i, change_locus="order_level"))

        cm._check_soft_stagnation()
        assert cm._forced_next_locus == "vehicle_level"

    def test_forced_locus_consumed_on_next_branch(self):
        """_consume_forced_locus returns the value and resets to None."""
        cm = _make_campaign()
        cm._forced_next_locus = "order_level"

        consumed = cm._consume_forced_locus()
        assert consumed == "order_level"
        assert cm._forced_next_locus is None

    def test_soft_stagnation_resets_streak_after_acting(self):
        """After triggering, _soft_abandon_streak resets to 0."""
        cm = _make_campaign(termination_config=TerminationConfig(soft_stagnation_limit=5))
        cm._soft_abandon_streak = 5
        for i in range(5):
            cm._step_history.append(_make_step(i, change_locus="vehicle_level"))

        cm._check_soft_stagnation()
        assert cm._soft_abandon_streak == 0


# ===========================================================================
# I4: Hard stagnation escape
# ===========================================================================

class TestI4HardStagnationEscape:
    def test_hard_stagnation_first_trigger_returns_false(self):
        """First stagnation trigger → should_stop returns False (escape used)."""
        cm = _make_campaign(termination_config=TerminationConfig(stagnation_limit=10))
        cm._recent_abandoned_count = 10
        cm._start_time = datetime.now()
        cm._n_experiments = 0

        result = cm.should_stop()

        assert result is False
        assert cm._hard_stagnation_escape_used is True
        assert cm._recent_abandoned_count == 0

    def test_hard_stagnation_second_trigger_returns_true(self):
        """After escape used, second stagnation trigger → should_stop True."""
        cm = _make_campaign(termination_config=TerminationConfig(stagnation_limit=10))
        cm._hard_stagnation_escape_used = True
        cm._recent_abandoned_count = 10
        cm._start_time = datetime.now()
        cm._n_experiments = 0

        result = cm.should_stop()
        assert result is True

    def test_hard_stagnation_escape_resets_on_promote(self):
        """After promote, escape opportunity resets for the new champion cycle."""
        cm = _make_campaign()
        cm._hard_stagnation_escape_used = True

        branch = _register_branch(cm, "bp")
        ws = tempfile.mkdtemp()
        cm._branch_workspaces["bp"] = ws

        cm._on_promote(branch)
        assert cm._hard_stagnation_escape_used is False

    def test_non_stagnation_termination_not_affected(self):
        """max_experiments termination is not intercepted by escape logic."""
        cm = _make_campaign(termination_config=TerminationConfig(
            max_experiments=5,
            stagnation_limit=100,
        ))
        cm._n_experiments = 5
        cm._recent_abandoned_count = 0
        cm._start_time = datetime.now()

        result = cm.should_stop()
        assert result is True
        assert cm._hard_stagnation_escape_used is False


# ===========================================================================
# Integration scenarios
# ===========================================================================

class TestIntegrationScenarios:
    def test_f2_scenario_does_not_terminate_early(self):
        """Simulate F2: 2 promotes + 10 consecutive T4 soft-abandons.

        Campaign must NOT terminate, and forced_next_locus should be set
        after hitting soft_stagnation_limit.
        """
        cm = _make_campaign(termination_config=TerminationConfig(
            stagnation_limit=10,
            soft_stagnation_limit=10,
        ))
        cm._start_time = datetime.now()
        cm._n_experiments = 0

        # Simulate 2 promotes
        for i in range(2):
            bid = f"promote_{i}"
            branch = _register_branch(cm, bid)
            ws = tempfile.mkdtemp()
            cm._branch_workspaces[bid] = ws
            cm._on_promote(branch)

        # Simulate 10 consecutive T4 soft-abandons
        for i in range(10):
            bid = f"soft_{i}"
            branch = _register_branch(cm, bid)
            cm._apply_soft_abandon(bid, branch, None)
            cm._soft_abandon_streak += 1
            cm._step_history.append(_make_step(i, bid, change_locus="vehicle_level"))

        # should_stop should be False (hard counter is 0)
        assert cm.should_stop() is False
        # _recent_abandoned_count should still be 0 (only soft)
        assert cm._recent_abandoned_count == 0
        # Soft stagnation should trigger when we call check
        cm._check_soft_stagnation()
        assert cm._forced_next_locus is not None

    def test_hard_stagnation_escape_then_terminate(self):
        """10 hard-abandons → escape → 10 more hard-abandons → should_stop True."""
        cm = _make_campaign(termination_config=TerminationConfig(stagnation_limit=10))
        cm._start_time = datetime.now()
        cm._n_experiments = 0

        # First round: 10 hard abandons
        cm._recent_abandoned_count = 10

        # First trigger: escape
        assert cm.should_stop() is False
        assert cm._hard_stagnation_escape_used is True
        assert cm._recent_abandoned_count == 0

        # Second round: 10 more hard abandons
        cm._recent_abandoned_count = 10

        # Second trigger: terminate
        assert cm.should_stop() is True
