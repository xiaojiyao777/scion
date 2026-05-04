"""Mini-Validation B: classifier on/off, async weight stress, early-stop replay."""
from __future__ import annotations

import pytest

from scion.core.branch import BranchController
from scion.core.early_stop import EarlyStopController
from scion.core.models import BranchState, ChampionState, HypothesisRecord
from scion.core.stagnation import StagnationSignal
from scion.core.termination import CampaignState, TerminationChecker
from scion.lineage.registry import LineageRegistry
from scion.lineage.branch_store import HypothesisStore
from scion.proposal.classifier import HypothesisFamilyClassifier, ClassificationResult
from scion.proposal.saturation import ChampionSaturationAnalyzer, SaturationSignal


# ---------------------------------------------------------------------------
# Classifier on/off smoke
# ---------------------------------------------------------------------------

class TestClassifierOnOffSmoke:
    def test_off_keyword_only(self) -> None:
        c = HypothesisFamilyClassifier(llm_client=None)
        r = c.classify("destroy and rebuild vehicles")
        assert r.source == "keyword"
        assert r.family_id == "subcat_rebuild_destroy"

    def test_on_with_mock(self) -> None:
        class MockLLM:
            def call_text(self, prompt, model=None):
                return "vehicle_elimination_cost"

        c = HypothesisFamilyClassifier(llm_client=MockLLM())
        r = c.classify("eliminate expensive vehicles")
        assert r.source == "classifier"
        assert r.family_id == "vehicle_elimination_cost"

    def test_classification_persists_to_lineage(self, tmp_path) -> None:
        registry = LineageRegistry(str(tmp_path / "test.db"))
        store = HypothesisStore(registry)
        classifier = HypothesisFamilyClassifier()

        for i, text in enumerate([
            "destroy and rebuild solution",
            "merge subcategories for consolidation",
            "eliminate weak vehicles to reduce cost",
        ]):
            r = classifier.classify(text)
            store.save(HypothesisRecord(
                hypothesis_id=f"h{i}", branch_id="b1",
                change_locus="vehicle_level", action="create_new", status="active",
                hypothesis_text=text,
                family_id=r.family_id, family_source=r.source,
                taxonomy_version=r.taxonomy_version,
            ))

        stats = store.get_family_stats()
        assert len(stats) == 3
        families = {s["family_id"] for s in stats}
        assert "subcat_rebuild_destroy" in families
        assert "subcategory_merge_consolidate" in families


# ---------------------------------------------------------------------------
# Async weight update stress
# ---------------------------------------------------------------------------

class TestAsyncWeightStress:
    def _setup(self):
        ctrl = BranchController()
        champ = ChampionState(
            version=1, operator_pool={}, solver_config_hash="x",
            code_snapshot_path="/tmp", code_snapshot_hash="y",
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
            version=1, operator_pool={}, solver_config_hash="x",
            code_snapshot_path="/tmp", code_snapshot_hash="y",
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
            version=1, operator_pool={}, solver_config_hash="x",
            code_snapshot_path="/v1", code_snapshot_hash="h1",
            weight_revision=0,
        )
        c2 = ChampionState(
            version=1, operator_pool={}, solver_config_hash="x",
            code_snapshot_path="/v1_r1", code_snapshot_hash="h2",
            weight_revision=1,
        )
        assert c2.weight_revision == c1.weight_revision + 1
        assert c2.code_snapshot_path != c1.code_snapshot_path


# ---------------------------------------------------------------------------
# Early-stop replay smoke
# ---------------------------------------------------------------------------

class TestEarlyStopReplaySmoke:
    def test_hard_saturation_stops_campaign(self) -> None:
        analyzer = ChampionSaturationAnalyzer(
            {"subcategory_splits": 0.5},
            lower_bounds={"subcategory_splits": 0.0},
        )
        signals = analyzer.analyze({"subcategory_splits": 0.3})
        assert signals[0].saturation_type == "hard"

        ctrl = EarlyStopController()
        decision = ctrl.should_early_stop(signals, [])
        assert decision.stop is True
        assert decision.rule == "all_bounded"

    def test_soft_saturation_needs_plateau(self) -> None:
        analyzer = ChampionSaturationAnalyzer({"total_cost": 100000})
        signals = analyzer.analyze({"total_cost": 20000})
        assert signals[0].saturation_type == "soft"

        ctrl = EarlyStopController()
        decision = ctrl.should_early_stop(signals, [])
        assert decision.stop is False

        plateau = StagnationSignal(
            kind="plateau", severity="warning",
            detail="flat", suggested_action="switch",
        )
        decision2 = ctrl.should_early_stop(
            signals, [plateau],
            total_rounds=50, rounds_since_last_promote=30,
        )
        assert decision2.stop is True
        assert decision2.rule == "diminishing_returns"

    def test_termination_integration(self) -> None:
        checker = TerminationChecker()
        state = CampaignState(
            early_stop_detected=True,
            early_stop_reason="all objectives at absolute minimum",
        )
        assert checker.should_stop(state) is True

    def test_force_continue_overrides_everything(self) -> None:
        ctrl = EarlyStopController(force_continue=True)
        hard = SaturationSignal(
            objective="x", improvement_ratio=0.0,
            saturation_level="high", opportunity_hint="at min",
            at_absolute_minimum=True, saturation_type="hard",
        )
        decision = ctrl.should_early_stop([hard], [])
        assert decision.stop is False
        assert decision.rule == "override"
