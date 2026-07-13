"""Tests for Sprint O1: classifier wire, memory views, failure summary v2."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scion.core.campaign import CampaignManager
from scion.core.models import HypothesisRecord
from scion.lineage.registry import LineageRegistry
from scion.lineage.branch_store import HypothesisStore
from scion.proposal.classifier import (
    ClassificationResult,
    HypothesisFamilyClassifier,
    TAXONOMY_VERSION,
)
from scion.proposal.mock_client import MockLLMClient
from scion.tests.campaign_test_support import (
    AlwaysPassVerificationGate,
    _make_champion,
    _make_problem_spec,
    _make_protocol_config,
    _make_seed_ledger,
    _make_split_manifest,
)
from scion.tests.taxonomy_helpers import warehouse_family_taxonomy

WAREHOUSE_MECHANISM_TAXONOMY = warehouse_family_taxonomy()


# ---------------------------------------------------------------------------
# W7: Classifier wired into HypothesisRecord
# ---------------------------------------------------------------------------


class TestClassifierWiring:
    def test_classify_and_store(self, tmp_path) -> None:
        registry = LineageRegistry(str(tmp_path / "test.db"))
        store = HypothesisStore(registry)
        classifier = HypothesisFamilyClassifier(taxonomy=WAREHOUSE_MECHANISM_TAXONOMY)

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
        assert loaded.family_id == "destroy_rebuild"
        assert loaded.family_source == "keyword"
        assert loaded.taxonomy_version == TAXONOMY_VERSION

    def test_campaign_has_classifier(self) -> None:
        from scion.core import campaign_composition
        import inspect
        src = inspect.getsource(campaign_composition.compose_campaign_services)
        assert "HypothesisFamilyClassifier" in src

    def test_composed_campaign_classifies_full_text_without_provider_call(
        self,
        tmp_path: Path,
    ) -> None:
        class CountingClient(MockLLMClient):
            def __init__(self, hypothesis_response) -> None:
                super().__init__(hypothesis_response=hypothesis_response)
                self.classifier_call_count = 0

            def call_text(self, prompt, model=None):
                del prompt, model
                self.classifier_call_count += 1
                return "subcategory_consolidation"

        code_dir = tmp_path / "champion_code"
        operators_dir = code_dir / "operators"
        operators_dir.mkdir(parents=True)
        source = (
            "class LocalSearch:\n"
            "    def execute(self, solution, rng):\n"
            "        return solution\n"
        )
        (operators_dir / "local_search.py").write_text(source, encoding="utf-8")
        (code_dir / "solver.py").write_text(source, encoding="utf-8")
        problem_spec = _make_problem_spec(str(code_dir))
        object.__setattr__(
            problem_spec,
            "family_taxonomy",
            WAREHOUSE_MECHANISM_TAXONOMY,
        )
        full_hypothesis_text = (
            "neutral mechanism context " * 30
            + "merge subcategories using a deterministic consolidation move"
        )
        assert len(full_hypothesis_text) > 500
        assert "merge subcategories" not in full_hypothesis_text[:500]
        client = CountingClient(
            {
                "hypothesis_text": full_hypothesis_text,
                "change_locus": "local_search",
                "action": "modify",
                "target_file": "operators/local_search.py",
                "predicted_direction": "improve",
                "target_weakness": "The current merge policy is too coarse.",
                "expected_effect": "Improve consolidation deterministically.",
            }
        )
        campaign = CampaignManager(
            problem_spec=problem_spec,
            protocol_config=_make_protocol_config(),
            split_manifest=_make_split_manifest(),
            seed_ledger=_make_seed_ledger(),
            llm_client=client,
            champion=_make_champion(str(code_dir)),
            campaign_dir=str(tmp_path / "campaign"),
            verification_gate=AlwaysPassVerificationGate(),
        )
        branch = campaign._branch_ctrl.create_branch(campaign._champion)

        hypothesis, record = campaign._round1_generate_hypothesis(branch)

        assert hypothesis is not None
        assert record is not None
        assert not hasattr(campaign._classifier, "_client")
        assert client.call_count == 1
        assert client.classifier_call_count == 0
        assert record.hypothesis_text == full_hypothesis_text
        assert record.family_id == "subcategory_consolidation"
        assert record.family_source == "keyword"
        assert record.taxonomy_version == WAREHOUSE_MECHANISM_TAXONOMY.version


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
