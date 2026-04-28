"""Tests for Sprint O0: family persistence + classifier API repair."""
from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from scion.core.models import HypothesisRecord
from scion.lineage.registry import LineageRegistry
from scion.lineage.branch_store import HypothesisStore
from scion.proposal.classifier import (
    ClassificationResult,
    HypothesisFamilyClassifier,
    TAXONOMY,
    TAXONOMY_VERSION,
    _keyword_classify,
)


# ---------------------------------------------------------------------------
# Family persistence in lineage
# ---------------------------------------------------------------------------


class TestFamilyPersistence:
    @pytest.fixture
    def store(self, tmp_path) -> HypothesisStore:
        db_path = str(tmp_path / "test.db")
        registry = LineageRegistry(db_path)
        return HypothesisStore(registry)

    def test_save_and_load_with_family(self, store: HypothesisStore) -> None:
        hyp = HypothesisRecord(
            hypothesis_id="h1",
            branch_id="b1",
            change_locus="order_level",
            action="modify",
            status="active",
            hypothesis_text="consolidate subcategories",
            family_id="subcategory_merge_consolidate",
            family_source="classifier",
            taxonomy_version="v1",
        )
        store.save(hyp)
        loaded = store.get_one("h1")
        assert loaded is not None
        assert loaded.family_id == "subcategory_merge_consolidate"
        assert loaded.family_source == "classifier"
        assert loaded.taxonomy_version == "v1"

    def test_save_without_family(self, store: HypothesisStore) -> None:
        hyp = HypothesisRecord(
            hypothesis_id="h2",
            branch_id="b1",
            change_locus="vehicle_level",
            action="create_new",
            status="active",
        )
        store.save(hyp)
        loaded = store.get_one("h2")
        assert loaded is not None
        assert loaded.family_id is None
        assert loaded.family_source is None

    def test_family_columns_in_schema(self, store: HypothesisStore) -> None:
        with sqlite3.connect(store.registry.db_path) as conn:
            info = conn.execute("PRAGMA table_info(hypotheses)").fetchall()
            col_names = [row[1] for row in info]
        assert "family_id" in col_names
        assert "family_source" in col_names
        assert "taxonomy_version" in col_names


# ---------------------------------------------------------------------------
# Classifier API
# ---------------------------------------------------------------------------


class TestClassifier:
    def test_keyword_fallback(self) -> None:
        c = HypothesisFamilyClassifier()
        r = c.classify("destroy and rebuild vehicles to reduce cost")
        assert isinstance(r, ClassificationResult)
        assert r.family_id == "subcat_rebuild_destroy"
        assert r.source == "keyword"
        assert r.taxonomy_version == TAXONOMY_VERSION

    def test_keyword_consolidate(self) -> None:
        r = _keyword_classify("merge subcategories for consolidation")
        assert r == "subcategory_merge_consolidate"

    def test_keyword_unknown(self) -> None:
        r = _keyword_classify("something completely different")
        assert r == "NEW_FAMILY"

    def test_all_taxonomy_entries_valid(self) -> None:
        for t in TAXONOMY:
            assert isinstance(t, str)
            assert len(t) > 0

    def test_classification_result_immutable(self) -> None:
        r = ClassificationResult(family_id="test", source="keyword")
        with pytest.raises(AttributeError):
            r.family_id = "other"  # type: ignore[misc]

    def test_classifier_without_client_uses_keywords(self) -> None:
        c = HypothesisFamilyClassifier(llm_client=None)
        r = c.classify("reassign orders between vehicles")
        assert r.source == "keyword"
        assert r.family_id == "order_level_reassign"

    def test_classifier_with_failing_client_falls_back(self) -> None:
        class FailingClient:
            def call_text(self, prompt, model=None):
                raise RuntimeError("API down")

        c = HypothesisFamilyClassifier(llm_client=FailingClient())
        r = c.classify("merge subcategories")
        assert r.source == "keyword"
        assert r.family_id == "subcategory_merge_consolidate"

    def test_classifier_with_mock_client(self) -> None:
        class MockClient:
            def call_text(self, prompt, model=None):
                return "vehicle_elimination_cost"

        c = HypothesisFamilyClassifier(llm_client=MockClient())
        r = c.classify("eliminate expensive vehicles")
        assert r.source == "classifier"
        assert r.family_id == "vehicle_elimination_cost"

    def test_classifier_uses_problem_taxonomy_without_warehouse_keywords(self) -> None:
        c = HypothesisFamilyClassifier(
            llm_client=None,
            taxonomy=["two_opt_local_search", "nearest_neighbor_seed"],
            taxonomy_version="tsp-v1",
        )
        r = c.classify("Try a two opt local search move for tour improvement")
        assert r.source == "keyword"
        assert r.family_id == "two_opt_local_search"
        assert r.taxonomy_version == "tsp-v1"

    def test_classifier_invalid_response_falls_back(self) -> None:
        class MockClient:
            def call_text(self, prompt, model=None):
                return "not_a_valid_taxonomy_entry_at_all"

        c = HypothesisFamilyClassifier(llm_client=MockClient())
        r = c.classify("destroy and rebuild")
        assert r.family_id == "subcat_rebuild_destroy"


# ---------------------------------------------------------------------------
# LLMClient.call_text
# ---------------------------------------------------------------------------


class TestLLMClientCallText:
    def test_call_text_method_exists(self) -> None:
        from scion.proposal.llm_client import LLMClient
        assert callable(getattr(LLMClient, "call_text", None))
