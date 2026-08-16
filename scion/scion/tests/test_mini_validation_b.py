"""Mini-Validation B: async weight-update smoke."""
from __future__ import annotations

from scion.core.branch import BranchController
from scion.core.models import BranchState, ChampionState


# ---------------------------------------------------------------------------
# Async weight update stress
# ---------------------------------------------------------------------------

class TestAsyncWeightStress:
    def _setup(self):
        ctrl = BranchController()
        champ = ChampionState(
            version=1, operator_pool={},
            code_snapshot_path="/tmp",
        )
        branches = []
        for state in [
            BranchState.EXPLORE, BranchState.EXPLORE_EXPAND,
            BranchState.READY_VALIDATE, BranchState.VALIDATING,
            BranchState.VALIDATING_EXPAND, BranchState.FROZEN_TESTING,
        ]:
            b = ctrl.create_branch(champ)
            b.state = state
            branches.append((state, b))
        return ctrl, branches

    def test_weight_update_marks_non_frozen_active_branches(self) -> None:
        ctrl, branches = self._setup()
        affected = ctrl.mark_stale_for_weight_update(1)
        assert len(affected) == 5
        for orig_state, b in branches:
            if orig_state == BranchState.FROZEN_TESTING:
                assert b.state == orig_state
            else:
                assert b.state == BranchState.STALE_WEIGHT_UPDATE

    def test_champion_promotion_marks_broader(self) -> None:
        ctrl, branches = self._setup()
        affected = ctrl.mark_all_stale(2)
        # All except FROZEN_TESTING
        assert len(affected) == 5
        for orig_state, b in branches:
            if orig_state == BranchState.FROZEN_TESTING:
                assert b.state == BranchState.FROZEN_TESTING
            else:
                assert b.state == BranchState.STALE

    def test_sequential_weight_updates(self) -> None:
        ctrl = BranchController()
        champ = ChampionState(
            version=1, operator_pool={},
            code_snapshot_path="/tmp",
        )
        b = ctrl.create_branch(champ)
        assert b.state == BranchState.EXPLORE

        ctrl.mark_stale_for_weight_update(1)
        assert b.state == BranchState.STALE_WEIGHT_UPDATE

        ctrl.reconcile_stale(b.branch_id, True, champ)
        assert b.state == BranchState.EXPLORE

        ctrl.mark_stale_for_weight_update(1)
        assert b.state == BranchState.STALE_WEIGHT_UPDATE

    def test_weight_revision_tracking(self) -> None:
        c1 = ChampionState(
            version=1, operator_pool={},
            code_snapshot_path="/v1",
            weight_revision=0,
        )
        c2 = ChampionState(
            version=1, operator_pool={},
            code_snapshot_path="/v1_r1",
            weight_revision=1,
        )
        assert c2.weight_revision == c1.weight_revision + 1
        assert c2.code_snapshot_path != c1.code_snapshot_path
