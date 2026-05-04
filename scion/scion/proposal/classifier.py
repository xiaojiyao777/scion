"""HypothesisFamilyClassifier — LLM-assisted semantic classification (J5/O0)."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Literal, Optional

from scion.proposal.mechanism_labels import (
    UNKNOWN_FAMILY_LABEL,
    extract_mechanism_label,
    taxonomy_family_labels,
)

logger = logging.getLogger(__name__)

TAXONOMY_VERSION = "v1"

TAXONOMY = [
    UNKNOWN_FAMILY_LABEL,
]

_CLASSIFIER_PROMPT = """\
You are a hypothesis classifier for a combinatorial-optimization operator search system.

Given a hypothesis text, classify it into exactly ONE of these family categories:
{taxonomy}

Respond with ONLY the category name, nothing else.

Hypothesis: {hypothesis_text}
"""

@dataclass(frozen=True)
class ClassificationResult:
    family_id: str
    source: Literal["classifier", "keyword"]
    taxonomy_version: str = TAXONOMY_VERSION


def _normalise_taxonomy(taxonomy: Any = None) -> list[str]:
    values = taxonomy_family_labels(taxonomy)
    return values or list(TAXONOMY)


def _keyword_classify(
    hypothesis_text: str,
    taxonomy: Any = None,
) -> str:
    candidate_labels = _normalise_taxonomy(taxonomy)
    label = extract_mechanism_label(hypothesis_text, taxonomy=taxonomy or candidate_labels)
    if label in candidate_labels:
        return label
    return UNKNOWN_FAMILY_LABEL


class HypothesisFamilyClassifier:
    """Semantic hypothesis classifier using a lightweight LLM call.

    The framework default taxonomy is intentionally domain-neutral. Problem
    packages that want semantic families must pass an explicit taxonomy from
    their problem spec.

    Falls back to keyword matching if the LLM call fails.
    Returns ClassificationResult with provenance (source + taxonomy_version).
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        *,
        taxonomy: Any = None,
        taxonomy_version: str = TAXONOMY_VERSION,
    ) -> None:
        self._client = llm_client
        self._model = os.environ.get("SCION_CLASSIFIER_MODEL", "claude-sonnet-4-6")
        custom_taxonomy = taxonomy if taxonomy_family_labels(taxonomy) else None
        self._custom_taxonomy = custom_taxonomy
        self._taxonomy = taxonomy_family_labels(custom_taxonomy) or list(TAXONOMY)
        self._taxonomy_set = frozenset(self._taxonomy)
        self._taxonomy_version = taxonomy_version

    def classify(self, hypothesis_text: str) -> ClassificationResult:
        if self._client is None:
            return ClassificationResult(
                family_id=_keyword_classify(hypothesis_text, self._custom_taxonomy),
                source="keyword",
                taxonomy_version=self._taxonomy_version,
            )

        try:
            family_id = self._classify_via_llm(hypothesis_text)
            return ClassificationResult(
                family_id=family_id,
                source="classifier",
                taxonomy_version=self._taxonomy_version,
            )
        except Exception as exc:
            logger.debug("Classifier LLM call failed, using keyword fallback: %s", exc)
            return ClassificationResult(
                family_id=_keyword_classify(hypothesis_text, self._custom_taxonomy),
                source="keyword",
                taxonomy_version=self._taxonomy_version,
            )

    def _classify_via_llm(self, hypothesis_text: str) -> str:
        taxonomy_str = "\n".join(f"- {t}" for t in self._taxonomy)
        prompt = _CLASSIFIER_PROMPT.format(
            taxonomy=taxonomy_str,
            hypothesis_text=hypothesis_text[:500],
        )

        raw = self._client.call_text(prompt, model=self._model)
        result = raw.strip()

        if result in self._taxonomy_set:
            return result

        for t in self._taxonomy:
            if t in result or result in t:
                return t

        return _keyword_classify(hypothesis_text, self._custom_taxonomy)
