"""Tests for Sprint N2: async weight-opt redesign + early-stop redesign."""
from __future__ import annotations

import pytest

from scion.core.branch import BranchController
from scion.core.early_stop import EarlyStopController, EarlyStopDecision
from scion.core.models import Branch, BranchState, ChampionState
from scion.core.stagnation import StagnationSignal
from scion.core.termination import CampaignState, TerminationChecker
from scion.proposal.saturation import SaturationSignal


# ---------------------------------------------------------------------------
# W2: Weight revision tracking
# ---------------------------------------------------------------------------

class TestWeightRevision:
    def test_champion_default_revision(self) -> None:
        c = ChampionState(
            version=1, operator_pool={}, solver_config_hash="abc",
            code_snapshot_path="/tmp", code_snapshot_hash="def",
        )
        assert c.weight_revision == 0

    def test_champion_revision_increments(self) -> None:
        c = ChampionState(
            version=1, operator_pool={}, solver_config_hash="abc",
            code_snapshot_path="/tmp", code_snapshot_hash="def",
            weight_revision=3,
        )
        assert c.weight_revision == 3

    def test_branch_default_revision(self) -> None:
        b = Branch(
            branch_id="test", state=BranchState.EXPLORE,
            base_champion_id=1, base_champion_hash="abc",
        )
        assert b.weight_revision == 0


# ---------------------------------------------------------------------------
# W2: Stage-aware stale invalidation
# ---------------------------------------------------------------------------

class TestStageAwareStale:
    def _make_ctrl_with_branches(self):
        ctrl = BranchController()
        champion = ChampionState(
            version=1, operator_pool={}, solver_config_hash="x",
            code_snapshot_path="/tmp", code_snapshot_hash="y",
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

    def test_mark_stale_only_screening(self) -> None:
        ctrl, branches = self._make_ctrl_with_branches()
        affected = ctrl.mark_stale_for_weight_update(1)

        explore = branches[BranchState.EXPLORE]
        expand = branches[BranchState.EXPLORE_EXPAND]
        validate = branches[BranchState.READY_VALIDATE]
        validating = branches[BranchState.VALIDATING]
        frozen = branches[BranchState.FROZEN_TESTING]

        assert explore.state == BranchState.STALE_WEIGHT_UPDATE
        assert expand.state == BranchState.STALE_WEIGHT_UPDATE
        # Validation and frozen are NOT affected
        assert validate.state == BranchState.READY_VALIDATE
        assert validating.state == BranchState.VALIDATING
        assert frozen.state == BranchState.FROZEN_TESTING
        assert len(affected) == 2

    def test_mark_all_stale_broader(self) -> None:
        ctrl, branches = self._make_ctrl_with_branches()
        affected = ctrl.mark_all_stale(2)
        # mark_all_stale affects all active except FROZEN_TESTING
        assert branches[BranchState.EXPLORE].state == BranchState.STALE
        assert branches[BranchState.READY_VALIDATE].state == BranchState.STALE
        assert branches[BranchState.VALIDATING].state == BranchState.STALE
        assert branches[BranchState.FROZEN_TESTING].state == BranchState.FROZEN_TESTING
        assert len(affected) == 4


# ---------------------------------------------------------------------------
# W3: Hard/soft saturation
# ---------------------------------------------------------------------------

class TestSaturationTypes:
    def test_hard_saturation(self) -> None:
        from scion.proposal.saturation import ChampionSaturationAnalyzer
        analyzer = ChampionSaturationAnalyzer(
            {"subcategory_splits": 0.5, "total_cost": 50000},
            lower_bounds={"subcategory_splits": 0.0},
        )
        signals = analyzer.analyze({"subcategory_splits": 0.3, "total_cost": 30000})
        splits_sig = next(s for s in signals if s.objective == "subcategory_splits")
        assert splits_sig.saturation_type == "hard"
        assert splits_sig.at_absolute_minimum is True

    def test_soft_saturation(self) -> None:
        from scion.proposal.saturation import ChampionSaturationAnalyzer
        analyzer = ChampionSaturationAnalyzer({"total_cost": 100000})
        signals = analyzer.analyze({"total_cost": 20000})
        cost_sig = signals[0]
        assert cost_sig.saturation_type == "soft"
        assert cost_sig.saturation_level == "high"
        assert cost_sig.improvement_ratio > 0.7

    def test_no_saturation(self) -> None:
        from scion.proposal.saturation import ChampionSaturationAnalyzer
        analyzer = ChampionSaturationAnalyzer({"total_cost": 100000})
        signals = analyzer.analyze({"total_cost": 90000})
        cost_sig = signals[0]
        assert cost_sig.saturation_type == "none"
        assert cost_sig.saturation_level == "low"


# ---------------------------------------------------------------------------
# W3: EarlyStopController
# ---------------------------------------------------------------------------

class TestEarlyStopController:
    def _hard_signal(self, obj: str = "splits") -> SaturationSignal:
        return SaturationSignal(
            objective=obj, improvement_ratio=0.0,
            saturation_level="high", opportunity_hint="at minimum",
            at_absolute_minimum=True, saturation_type="hard",
        )

    def _soft_high_signal(self, obj: str = "cost") -> SaturationSignal:
        return SaturationSignal(
            objective=obj, improvement_ratio=0.8,
            saturation_level="high", opportunity_hint="near optimal",
            saturation_type="soft",
        )

    def _low_signal(self, obj: str = "cost") -> SaturationSignal:
        return SaturationSignal(
            objective=obj, improvement_ratio=0.1,
            saturation_level="low", opportunity_hint="room to improve",
            saturation_type="none",
        )

    def _plateau_signal(self) -> StagnationSignal:
        return StagnationSignal(
            kind="plateau", severity="warning",
            detail="flat win rate", suggested_action="switch_action",
        )

    def test_all_bounded_stops(self) -> None:
        ctrl = EarlyStopController()
        d = ctrl.should_early_stop(
            [self._hard_signal("a"), self._hard_signal("b")], [],
        )
        assert d.stop is True
        assert d.rule == "all_bounded"

    def test_budget_efficiency_stops(self) -> None:
        ctrl = EarlyStopController(max_idle_ratio=0.6)
        d = ctrl.should_early_stop(
            [], [],
            total_rounds=50, rounds_since_last_promote=35,
        )
        assert d.stop is True
        assert d.rule == "budget_efficiency"

    def test_budget_efficiency_under_threshold_continues(self) -> None:
        ctrl = EarlyStopController(max_idle_ratio=0.6)
        d = ctrl.should_early_stop(
            [], [],
            total_rounds=50, rounds_since_last_promote=20,
        )
        assert d.stop is False

    def test_diminishing_returns_with_plateau_stops(self) -> None:
        ctrl = EarlyStopController(stagnation_window=15)
        d = ctrl.should_early_stop(
            [self._hard_signal(), self._soft_high_signal()],
            [self._plateau_signal()],
            total_rounds=50, rounds_since_last_promote=20,
        )
        assert d.stop is True
        assert d.rule == "diminishing_returns"

    def test_high_without_plateau_continues(self) -> None:
        ctrl = EarlyStopController()
        d = ctrl.should_early_stop(
            [self._hard_signal(), self._soft_high_signal()], [],
        )
        assert d.stop is False
        assert d.rule == "continue"

    def test_low_saturation_continues(self) -> None:
        ctrl = EarlyStopController()
        d = ctrl.should_early_stop(
            [self._hard_signal(), self._low_signal()],
            [self._plateau_signal()],
        )
        assert d.stop is False

    def test_force_continue_overrides(self) -> None:
        ctrl = EarlyStopController(force_continue=True)
        d = ctrl.should_early_stop(
            [self._hard_signal(), self._hard_signal()], [],
        )
        assert d.stop is False
        assert d.rule == "override"

    def test_empty_signals(self) -> None:
        ctrl = EarlyStopController()
        d = ctrl.should_early_stop([], [])
        assert d.stop is False


# ---------------------------------------------------------------------------
# W3: Termination with early-stop
# ---------------------------------------------------------------------------

class TestTerminationWithEarlyStop:
    def test_early_stop_flag_triggers_termination(self) -> None:
        checker = TerminationChecker()
        state = CampaignState(early_stop_detected=True, early_stop_reason="all hard")
        assert checker.should_stop(state) is True

    def test_no_early_stop_normal_behavior(self) -> None:
        checker = TerminationChecker()
        state = CampaignState(can_create_new=True)
        assert checker.should_stop(state) is False
