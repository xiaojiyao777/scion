"""Tests for Sprint O1: classifier wire, memory views, failure summary v2."""
from __future__ import annotations

import sqlite3
import pytest

from scion.core.models import HypothesisRecord
from scion.lineage.registry import LineageRegistry
from scion.lineage.branch_store import HypothesisStore
from scion.proposal.classifier import (
    ClassificationResult,
    HypothesisFamilyClassifier,
    TAXONOMY_VERSION,
)


# ---------------------------------------------------------------------------
# W7: Classifier wired into HypothesisRecord
# ---------------------------------------------------------------------------


class TestClassifierWiring:
    def test_classify_and_store(self, tmp_path) -> None:
        registry = LineageRegistry(str(tmp_path / "test.db"))
        store = HypothesisStore(registry)
        classifier = HypothesisFamilyClassifier()

        result = classifier.classify("destroy and rebuild all vehicles")
        h = HypothesisRecord(
            hypothesis_id="h1",
            branch_id="b1",
            change_locus="vehicle_level",
            action="create_new",
            status="active",
            hypothesis_text="destroy and rebuild all vehicles",
            family_id=result.family_id,
            family_source=result.source,
            taxonomy_version=result.taxonomy_version,
        )
        store.save(h)
        loaded = store.get_one("h1")
        assert loaded.family_id == "subcat_rebuild_destroy"
        assert loaded.family_source == "keyword"
        assert loaded.taxonomy_version == TAXONOMY_VERSION

    def test_campaign_has_classifier(self) -> None:
        from scion.core.campaign import CampaignManager
        import inspect
        src = inspect.getsource(CampaignManager.__init__)
        assert "HypothesisFamilyClassifier" in src


# ---------------------------------------------------------------------------
# W5: Lineage-derived family views
# ---------------------------------------------------------------------------


class TestFamilyViews:
    @pytest.fixture
    def store(self, tmp_path) -> HypothesisStore:
        registry = LineageRegistry(str(tmp_path / "test.db"))
        return HypothesisStore(registry)

    def _save_hyp(self, store, hid, family_id, status="active"):
        store.save(HypothesisRecord(
            hypothesis_id=hid,
            branch_id="b1",
            change_locus="order_level",
            action="modify",
            status=status,
            family_id=family_id,
            family_source="keyword",
            taxonomy_version="v1",
        ))

    def test_family_stats_empty(self, store) -> None:
        stats = store.get_family_stats()
        assert stats == []

    def test_family_stats_aggregation(self, store) -> None:
        self._save_hyp(store, "h1", "subcategory_merge_consolidate", "active")
        self._save_hyp(store, "h2", "subcategory_merge_consolidate", "promoted")
        self._save_hyp(store, "h3", "subcategory_merge_consolidate", "rejected")
        self._save_hyp(store, "h4", "vehicle_elimination_cost", "rejected")

        stats = store.get_family_stats()
        assert len(stats) == 2

        merge_stat = next(s for s in stats if s["family_id"] == "subcategory_merge_consolidate")
        assert merge_stat["total"] == 3
        assert merge_stat["promoted"] == 1
        assert merge_stat["rejected"] == 1

    def test_failure_summary(self, store) -> None:
        self._save_hyp(store, "h1", "a", "active")
        self._save_hyp(store, "h2", "b", "rejected")
        self._save_hyp(store, "h3", "c", "rejected")
        self._save_hyp(store, "h4", "d", "promoted")

        summary = store.get_failure_summary()
        status_map = {s["status"]: s["count"] for s in summary}
        assert status_map["rejected"] == 2
        assert status_map["active"] == 1
        assert status_map["promoted"] == 1


# ---------------------------------------------------------------------------
# W8: Failure summary v2
# ---------------------------------------------------------------------------


class TestFailureSummaryV2:
    def test_empty_db(self, tmp_path) -> None:
        registry = LineageRegistry(str(tmp_path / "test.db"))
        summary = registry.get_failure_summary_v2()
        assert summary["by_stage"] == {}
        assert summary["by_decision"] == {}
        assert summary["recent_failures"] == []

    def test_with_events(self, tmp_path) -> None:
        registry = LineageRegistry(str(tmp_path / "test.db"))
        with sqlite3.connect(registry.db_path) as conn:
            for i in range(3):
                conn.execute("""
                    INSERT INTO experiment_events
                    (event_id, branch_id, timestamp, event_kind, contract_result)
                    VALUES (?, ?, datetime('now'), 'experiment', 'failed')
                """, (f"e{i}", f"b{i}"))
            conn.execute("""
                INSERT INTO experiment_events
                (event_id, branch_id, timestamp, event_kind, verification_result, decision)
                VALUES ('e10', 'b10', datetime('now'), 'experiment', 'failed', 'abandon')
            """)

        summary = registry.get_failure_summary_v2()
        assert summary["by_stage"].get("contract", 0) == 3
        assert summary["by_stage"].get("verification", 0) == 1
        assert len(summary["recent_failures"]) == 4
