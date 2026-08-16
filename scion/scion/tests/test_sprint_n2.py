"""Tests for Sprint N2 async weight-update behavior."""
from __future__ import annotations

from scion.core.branch import BranchController
from scion.core.models import Branch, BranchState, ChampionState


# ---------------------------------------------------------------------------
# W2: Weight revision tracking
# ---------------------------------------------------------------------------

class TestWeightRevision:
    def test_champion_default_revision(self) -> None:
        c = ChampionState(
            version=1, operator_pool={},
            code_snapshot_path="/tmp",
        )
        assert c.weight_revision == 0

    def test_champion_revision_increments(self) -> None:
        c = ChampionState(
            version=1, operator_pool={},
            code_snapshot_path="/tmp",
            weight_revision=3,
        )
        assert c.weight_revision == 3

    def test_branch_default_revision(self) -> None:
        b = Branch(
            branch_id="test", state=BranchState.EXPLORE,
            base_champion_id=1,
        )
        assert b.weight_revision == 0


# ---------------------------------------------------------------------------
# W2: Stage-aware stale invalidation
# ---------------------------------------------------------------------------

class TestStageAwareStale:
    def _make_ctrl_with_branches(self):
        ctrl = BranchController()
        champion = ChampionState(
            version=1, operator_pool={},
            code_snapshot_path="/tmp",
        )
        branches = {}
        for state in [
            BranchState.EXPLORE,
            BranchState.EXPLORE_EXPAND,
            BranchState.READY_VALIDATE,
            BranchState.VALIDATING,
            BranchState.FROZEN_TESTING,
        ]:
            b = ctrl.create_branch(champion)
            b.state = state
            branches[state] = b
        return ctrl, branches

    def test_mark_stale_for_weight_update_excludes_frozen_holdout(self) -> None:
        ctrl, branches = self._make_ctrl_with_branches()
        affected = ctrl.mark_stale_for_weight_update(1)

        explore = branches[BranchState.EXPLORE]
        expand = branches[BranchState.EXPLORE_EXPAND]
        validate = branches[BranchState.READY_VALIDATE]
        validating = branches[BranchState.VALIDATING]
        frozen = branches[BranchState.FROZEN_TESTING]

        assert explore.state == BranchState.STALE_WEIGHT_UPDATE
        assert expand.state == BranchState.STALE_WEIGHT_UPDATE
        # Validation branches must re-screen before spending more validation/frozen budget.
        assert validate.state == BranchState.STALE_WEIGHT_UPDATE
        assert validating.state == BranchState.STALE_WEIGHT_UPDATE
        # Frozen holdout is already in the final evidence gate and is not interrupted.
        assert frozen.state == BranchState.FROZEN_TESTING
        assert len(affected) == 4

    def test_mark_all_stale_broader(self) -> None:
        ctrl, branches = self._make_ctrl_with_branches()
        affected = ctrl.mark_all_stale(2)
        # mark_all_stale affects all active except FROZEN_TESTING
        assert branches[BranchState.EXPLORE].state == BranchState.STALE
        assert branches[BranchState.READY_VALIDATE].state == BranchState.STALE
        assert branches[BranchState.VALIDATING].state == BranchState.STALE
        assert branches[BranchState.FROZEN_TESTING].state == BranchState.FROZEN_TESTING
        assert len(affected) == 4
