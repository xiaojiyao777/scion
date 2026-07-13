"""Deterministic problem-taxonomy hypothesis classification."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from scion.proposal.mechanism_labels import (
    UNKNOWN_FAMILY_LABEL,
    extract_mechanism_label,
    taxonomy_family_labels,
)

TAXONOMY_VERSION = "v1"

TAXONOMY = [
    UNKNOWN_FAMILY_LABEL,
]

@dataclass(frozen=True)
class ClassificationResult:
    family_id: str
    source: Literal["keyword"]
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
    """Classify hypotheses against a problem-owned taxonomy.

    The framework default taxonomy is intentionally domain-neutral. Problem
    packages that want semantic families must pass an explicit taxonomy from
    their problem spec.

    Returns ClassificationResult with provenance (source + taxonomy_version).
    """

    def __init__(
        self,
        *,
        taxonomy: Any = None,
        taxonomy_version: str = TAXONOMY_VERSION,
    ) -> None:
        custom_taxonomy = taxonomy if taxonomy_family_labels(taxonomy) else None
        self._custom_taxonomy = custom_taxonomy
        self._taxonomy = taxonomy_family_labels(custom_taxonomy) or list(TAXONOMY)
        self._taxonomy_version = taxonomy_version

    def classify(self, hypothesis_text: str) -> ClassificationResult:
        return ClassificationResult(
            family_id=_keyword_classify(hypothesis_text, self._custom_taxonomy),
            source="keyword",
            taxonomy_version=self._taxonomy_version,
        )
