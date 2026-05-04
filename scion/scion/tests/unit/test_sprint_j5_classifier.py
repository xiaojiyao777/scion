"""Sprint J5 unit tests: HypothesisFamilyClassifier (updated for O0 API)."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from scion.proposal.classifier import (
    ClassificationResult,
    HypothesisFamilyClassifier,
    TAXONOMY,
    _keyword_classify,
)
from scion.tests.taxonomy_helpers import warehouse_family_taxonomy

WAREHOUSE_MECHANISM_TAXONOMY = warehouse_family_taxonomy()


# ---------------------------------------------------------------------------
# Tests: Keyword-based fallback
# ---------------------------------------------------------------------------

class TestKeywordClassify:
    def test_default_is_domain_neutral(self):
        assert _keyword_classify("subcategory merge of vehicles") == "NEW_FAMILY"

    def test_explicit_warehouse_merge_consolidate(self):
        assert (
            _keyword_classify(
                "subcategory merge of vehicles",
                taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
            )
            == "subcategory_consolidation"
        )

    def test_drain_repack(self):
        assert (
            _keyword_classify(
                "drain small vehicles into larger",
                taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
            )
            == "intra_subcat_repack"
        )

    def test_destroy_rebuild(self):
        assert (
            _keyword_classify(
                "destroy and rebuild solution",
                taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
            )
            == "destroy_rebuild"
        )

    def test_eliminate_cost(self):
        assert (
            _keyword_classify(
                "eliminate weak vehicles to reduce cost",
                taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
            )
            == "vehicle_elimination"
        )

    def test_reassign_order(self):
        assert (
            _keyword_classify(
                "reassign orders at order_level",
                taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
            )
            == "order_swap"
        )

    def test_new_family(self):
        assert _keyword_classify("random perturbation of solution") == "NEW_FAMILY"

    def test_chain_rotation(self):
        assert _keyword_classify("chain rotation of three vehicles") == "NEW_FAMILY"


# ---------------------------------------------------------------------------
# Tests: Classifier with mock LLM
# ---------------------------------------------------------------------------

class TestClassifierWithMock:
    def test_no_client_uses_keyword(self):
        c = HypothesisFamilyClassifier(llm_client=None)
        result = c.classify("subcategory consolidation of orders")
        assert isinstance(result, ClassificationResult)
        assert result.family_id == "NEW_FAMILY"
        assert result.source == "keyword"

    def test_llm_returns_valid_taxonomy(self):
        client = MagicMock()
        client.call_text.return_value = "intra_subcat_repack"
        c = HypothesisFamilyClassifier(
            llm_client=client,
            taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
        )
        result = c.classify("drain orders from small vehicles")
        assert result.family_id == "intra_subcat_repack"
        assert result.source == "classifier"

    def test_llm_failure_fallback(self):
        client = MagicMock()
        client.call_text.side_effect = RuntimeError("API error")
        c = HypothesisFamilyClassifier(
            llm_client=client,
            taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
        )
        result = c.classify("drain orders from small vehicles")
        assert result.family_id == "intra_subcat_repack"
        assert result.source == "keyword"

    def test_llm_invalid_response_fallback(self):
        client = MagicMock()
        client.call_text.return_value = "nonsense_label"
        c = HypothesisFamilyClassifier(
            llm_client=client,
            taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
        )
        result = c.classify("subcategory merge")
        assert result.family_id == "subcategory_consolidation"

    def test_default_taxonomy_is_neutral(self):
        assert "subcategory_merge_consolidate" not in TAXONOMY
        assert "intra_subcat_repack" not in TAXONOMY
        assert "vehicle_elimination_cost" not in TAXONOMY
        assert "NEW_FAMILY" in TAXONOMY

    def test_llm_partial_match(self):
        client = MagicMock()
        client.call_text.return_value = "  subcategory_consolidation  "
        c = HypothesisFamilyClassifier(
            llm_client=client,
            taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
        )
        result = c.classify("merge subcategories")
        assert result.family_id == "subcategory_consolidation"
        assert result.source == "classifier"
