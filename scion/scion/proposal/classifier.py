"""HypothesisFamilyClassifier — LLM-assisted semantic classification (J5)."""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

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

_CLASSIFIER_PROMPT = """\
You are a hypothesis classifier for a vehicle-assignment operator search system.

Given a hypothesis text, classify it into exactly ONE of these family categories:
{taxonomy}

Respond with ONLY the category name, nothing else.

Hypothesis: {hypothesis_text}
"""


# Keyword-based fallback (same as search_memory.py but maps to J5 taxonomy)
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


def _keyword_classify(hypothesis_text: str) -> str:
    """Keyword-based fallback classifier."""
    text_lower = hypothesis_text.lower()
    for keywords, label in _FALLBACK_KEYWORDS:
        if any(kw in text_lower for kw in keywords):
            return label
    return "NEW_FAMILY"


class HypothesisFamilyClassifier:
    """Semantic hypothesis classifier using a lightweight LLM call.

    Falls back to keyword matching if the LLM call fails.
    Uses a separate model (default: claude-sonnet-4-6) to avoid
    interfering with the main proposal LLM.
    """

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        self._client = llm_client
        self._model = os.environ.get("SCION_CLASSIFIER_MODEL", "claude-sonnet-4-6")

    def classify(self, hypothesis_text: str) -> str:
        """Classify a hypothesis into a taxonomy family.

        Returns a taxonomy label string.
        """
        if self._client is None:
            return _keyword_classify(hypothesis_text)

        try:
            return self._classify_via_llm(hypothesis_text)
        except Exception as exc:
            logger.debug("Classifier LLM call failed, using keyword fallback: %s", exc)
            return _keyword_classify(hypothesis_text)

    def _classify_via_llm(self, hypothesis_text: str) -> str:
        """Use LLM for semantic classification."""
        taxonomy_str = "\n".join(f"- {t}" for t in TAXONOMY)
        prompt = _CLASSIFIER_PROMPT.format(
            taxonomy=taxonomy_str,
            hypothesis_text=hypothesis_text[:500],
        )

        # Use simple call (not tool_use) for classification
        if hasattr(self._client, 'call_simple'):
            raw = self._client.call_simple(prompt, self._model)
        else:
            # Fallback: try call_with_tool with a simple schema
            raw = self._client.call(prompt, model=self._model)

        if isinstance(raw, str):
            result = raw.strip()
        elif isinstance(raw, dict):
            result = raw.get("category", raw.get("text", "")).strip()
        else:
            result = str(raw).strip()

        # Validate against taxonomy
        if result in TAXONOMY:
            return result

        # Try partial match
        for t in TAXONOMY:
            if t in result or result in t:
                return t

        return _keyword_classify(hypothesis_text)
