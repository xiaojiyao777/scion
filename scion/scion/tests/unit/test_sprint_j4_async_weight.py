"""Sprint J4 unit tests: STALE_WEIGHT_UPDATE state + async weight opt integration."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from scion.core.models import (
    Branch, BranchState, ChampionState, Decision, OperatorConfig,
    WeightOptimizationResult,
)
from scion.core.branch import BranchController, StateTransitionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_branch(
    branch_id: str = "b1",
    state: BranchState = BranchState.EXPLORE,
) -> Branch:
    return Branch(
        branch_id=branch_id,
        state=state,
        base_champion_id=1,
        base_champion_hash="abc",
    )


def _make_champion(version: int = 1) -> ChampionState:
    return ChampionState(
        version=version,
        operator_pool={"op1": OperatorConfig("op1", "op1.py", "vehicle_level", 1.0, "Op1")},
        solver_config_hash="hash",
        code_snapshot_path="/tmp/v1",
        code_snapshot_hash="snap_hash",
    )


# ---------------------------------------------------------------------------
# Tests: BranchState.STALE_WEIGHT_UPDATE
# ---------------------------------------------------------------------------

class TestStaleWeightUpdateState:
    def test_stale_weight_update_is_valid_state(self):
        """STALE_WEIGHT_UPDATE is a valid BranchState."""
        assert BranchState.STALE_WEIGHT_UPDATE.value == "stale_weight_update"

    def test_branch_can_have_stale_weight_update(self):
        """Branch can be set to STALE_WEIGHT_UPDATE."""
        b = _make_branch(state=BranchState.STALE_WEIGHT_UPDATE)
        assert b.state == BranchState.STALE_WEIGHT_UPDATE

    def test_reconcile_stale_accepts_weight_update(self):
        """reconcile_stale works for both STALE and STALE_WEIGHT_UPDATE."""
        ctrl = BranchController()
        champ = _make_champion()
        branch = ctrl.create_branch(champ)
        bid = branch.branch_id

        # Manually set to STALE_WEIGHT_UPDATE
        ctrl._branches[bid].state = BranchState.STALE_WEIGHT_UPDATE
        ctrl.reconcile_stale(bid, success=True, new_champion=champ)
        assert ctrl.get_branch(bid).state == BranchState.EXPLORE

    def test_reconcile_stale_abandon_on_failure(self):
        ctrl = BranchController()
        champ = _make_champion()
        branch = ctrl.create_branch(champ)
        bid = branch.branch_id

        ctrl._branches[bid].state = BranchState.STALE_WEIGHT_UPDATE
        ctrl.reconcile_stale(bid, success=False, new_champion=champ)
        assert ctrl.get_branch(bid).state == BranchState.ABANDONED


class TestMarkAllStale:
    def test_mark_all_stale_from_explore(self):
        """mark_all_stale transitions EXPLORE branches to STALE."""
        ctrl = BranchController()
        champ = _make_champion()
        b1 = ctrl.create_branch(champ)
        # create_branch puts branch in EXPLORE state already
        affected = ctrl.mark_all_stale(2)
        assert b1.branch_id in affected
        assert ctrl.get_branch(b1.branch_id).state == BranchState.STALE


class TestGetCodeBase:
    def test_stale_weight_update_returns_champion(self):
        """get_code_base returns 'champion' for STALE_WEIGHT_UPDATE branches."""
        ctrl = BranchController()
        champ = _make_champion()
        branch = ctrl.create_branch(champ)
        bid = branch.branch_id
        ctrl._branches[bid].state = BranchState.STALE_WEIGHT_UPDATE
        assert ctrl.get_code_base(bid) == "champion"


class TestSchedulerIncludesStaleWeight:
    def test_stale_weight_update_is_schedulable(self):
        """STALE_WEIGHT_UPDATE branches are in the scheduler's priority tiers."""
        from scion.core.scheduler import _PRIORITY_TIERS
        stale_tier = [tier for tier in _PRIORITY_TIERS if BranchState.STALE in tier]
        assert len(stale_tier) == 1
        assert BranchState.STALE_WEIGHT_UPDATE in stale_tier[0]


class TestTerminationIncludesStaleWeight:
    def test_stale_weight_update_is_active_for_termination(self):
        """STALE_WEIGHT_UPDATE is counted as active for termination check."""
        from scion.core.termination import _ACTIVE_STATES
        assert BranchState.STALE_WEIGHT_UPDATE in _ACTIVE_STATES


class TestWeightOptResult:
    def test_weight_opt_result_dataclass(self):
        """WeightOptimizationResult can be created and queried."""
        result = WeightOptimizationResult(
            baseline_weights={"op1": 1.0},
            best_weights={"op1": 2.5},
            baseline_score=0.5,
            best_score=0.7,
            improved=True,
            n_evaluations=20,
            elapsed_seconds=120.0,
            observations_ref="/tmp/obs.json",
        )
        assert result.improved is True
        assert result.best_weights["op1"] == 2.5
