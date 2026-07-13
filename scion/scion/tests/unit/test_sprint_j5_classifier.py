"""Sprint J5 unit tests: HypothesisFamilyClassifier (updated for O0 API)."""
from __future__ import annotations

import pytest

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
# Tests: deterministic classifier
# ---------------------------------------------------------------------------

class TestDeterministicClassifier:
    def test_default_uses_keyword(self):
        c = HypothesisFamilyClassifier()
        result = c.classify("subcategory consolidation of orders")
        assert isinstance(result, ClassificationResult)
        assert result.family_id == "NEW_FAMILY"
        assert result.source == "keyword"

    def test_explicit_taxonomy_classifies_without_provider_call(self):
        c = HypothesisFamilyClassifier(
            taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
        )
        result = c.classify("drain orders from small vehicles")
        assert result.family_id == "intra_subcat_repack"
        assert result.source == "keyword"

    def test_explicit_taxonomy_maps_complete_hypothesis_text(self):
        c = HypothesisFamilyClassifier(
            taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
        )
        hypothesis_text = "neutral context " * 40 + "merge subcategories at the tail"
        result = c.classify(hypothesis_text)
        assert result.family_id == "subcategory_consolidation"
        assert result.source == "keyword"

    def test_default_taxonomy_is_neutral(self):
        assert "subcategory_merge_consolidate" not in TAXONOMY
        assert "intra_subcat_repack" not in TAXONOMY
        assert "vehicle_elimination_cost" not in TAXONOMY
        assert "NEW_FAMILY" in TAXONOMY
