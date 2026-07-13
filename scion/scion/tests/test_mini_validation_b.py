"""Mini-Validation B: classifier and async weight-update smoke."""
from __future__ import annotations

from scion.core.branch import BranchController
from scion.core.models import BranchState, ChampionState, HypothesisRecord
from scion.lineage.registry import LineageRegistry
from scion.lineage.branch_store import HypothesisStore
from scion.proposal.classifier import HypothesisFamilyClassifier, ClassificationResult
from scion.tests.taxonomy_helpers import warehouse_family_taxonomy

WAREHOUSE_MECHANISM_TAXONOMY = warehouse_family_taxonomy()


# ---------------------------------------------------------------------------
# Classifier on/off smoke
# ---------------------------------------------------------------------------

class TestDeterministicClassifierSmoke:
    def test_default_taxonomy_is_domain_neutral(self) -> None:
        c = HypothesisFamilyClassifier()
        r = c.classify("destroy and rebuild vehicles")
        assert r.source == "keyword"
        assert r.family_id == "NEW_FAMILY"

    def test_problem_taxonomy_classifies_without_provider_call(self) -> None:
        c = HypothesisFamilyClassifier(
            taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
        )
        r = c.classify("eliminate weak vehicles")
        assert r.source == "keyword"
        assert r.family_id == "vehicle_elimination"

    def test_classification_persists_to_lineage(self, tmp_path) -> None:
        registry = LineageRegistry(str(tmp_path / "test.db"))
        store = HypothesisStore(registry)
        classifier = HypothesisFamilyClassifier(taxonomy=WAREHOUSE_MECHANISM_TAXONOMY)

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
        assert "destroy_rebuild" in families
        assert "subcategory_consolidation" in families


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
