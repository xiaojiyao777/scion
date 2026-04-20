"""HypothesisFamilyClassifier — LLM-assisted semantic classification (J5/O0)."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

TAXONOMY_VERSION = "v1"

TAXONOMY = [
    "subcategory_merge_consolidate",
    "subcategory_chain_rotation",
    "intra_subcat_repack",
    "cross_subcat_displacement",
    "vehicle_elimination_cost",
    "subcat_rebuild_destroy",
    "order_level_reassign",
    "generic_merge",
    "NEW_FAMILY",
]

_TAXONOMY_SET = frozenset(TAXONOMY)

_CLASSIFIER_PROMPT = """\
You are a hypothesis classifier for a vehicle-assignment operator search system.

Given a hypothesis text, classify it into exactly ONE of these family categories:
{taxonomy}

Respond with ONLY the category name, nothing else.

Hypothesis: {hypothesis_text}
"""

_FALLBACK_KEYWORDS = [
    (["destroy", "rebuild"], "subcat_rebuild_destroy"),
    (["subcategor", "consolidat", "merge"], "subcategory_merge_consolidate"),
    (["chain", "rotat"], "subcategory_chain_rotation"),
    (["drain", "evacuate", "evict", "purif", "repack"], "intra_subcat_repack"),
    (["displace", "cross"], "cross_subcat_displacement"),
    (["eliminat", "remove_vehicle", "kill", "cost", "downsize"], "vehicle_elimination_cost"),
    (["reassign", "order_level"], "order_level_reassign"),
    (["swap", "generic", "merge"], "generic_merge"),
]


@dataclass(frozen=True)
class ClassificationResult:
    family_id: str
    source: Literal["classifier", "keyword"]
    taxonomy_version: str = TAXONOMY_VERSION


def _keyword_classify(hypothesis_text: str) -> str:
    text_lower = hypothesis_text.lower()
    for keywords, label in _FALLBACK_KEYWORDS:
        if any(kw in text_lower for kw in keywords):
            return label
    return "NEW_FAMILY"


class HypothesisFamilyClassifier:
    """Semantic hypothesis classifier using a lightweight LLM call.

    Falls back to keyword matching if the LLM call fails.
    Returns ClassificationResult with provenance (source + taxonomy_version).
    """

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        self._client = llm_client
        self._model = os.environ.get("SCION_CLASSIFIER_MODEL", "claude-sonnet-4-6")

    def classify(self, hypothesis_text: str) -> ClassificationResult:
        if self._client is None:
            return ClassificationResult(
                family_id=_keyword_classify(hypothesis_text),
                source="keyword",
            )

        try:
            family_id = self._classify_via_llm(hypothesis_text)
            return ClassificationResult(family_id=family_id, source="classifier")
        except Exception as exc:
            logger.debug("Classifier LLM call failed, using keyword fallback: %s", exc)
            return ClassificationResult(
                family_id=_keyword_classify(hypothesis_text),
                source="keyword",
            )

    def _classify_via_llm(self, hypothesis_text: str) -> str:
        taxonomy_str = "\n".join(f"- {t}" for t in TAXONOMY)
        prompt = _CLASSIFIER_PROMPT.format(
            taxonomy=taxonomy_str,
            hypothesis_text=hypothesis_text[:500],
        )

        raw = self._client.call_text(prompt, model=self._model)
        result = raw.strip()

        if result in _TAXONOMY_SET:
            return result

        for t in TAXONOMY:
            if t in result or result in t:
                return t

        return _keyword_classify(hypothesis_text)
