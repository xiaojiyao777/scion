from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _first_regex_span, _has_any
from scion.problems.cvrp.mechanism_novelty.destroy_repair.shared import (
    _is_positional_or_arc_destroy_variant,
    _is_pure_geographic_cluster_variant_acknowledging_shaw,
    _is_random_or_noise_removal_variant,
    _mentions_exact_shaw_related_fact,
    _mentions_shaw_related_removal,
    _targets_perturbation_or_restart_not_removal_family,
    _targets_segment_chain_unit_not_related_removal,
    _targets_worst_removal_savings_not_shaw,
)

def _claims_missing_shaw_related_removal(text: str) -> bool:
    return bool(_missing_shaw_related_removal_span(text))

def _missing_shaw_related_removal_span(text: str) -> str:
    if not _mentions_shaw_related_removal(text):
        return ""
    if not _mentions_exact_shaw_related_fact(text):
        return ""
    if _targets_perturbation_or_restart_not_removal_family(text):
        return ""
    if _targets_worst_removal_savings_not_shaw(text):
        return ""
    if _targets_segment_chain_unit_not_related_removal(text):
        return ""
    if _is_pure_geographic_cluster_variant_acknowledging_shaw(text):
        return ""
    if _is_cluster_variant_contrasting_existing_shaw(text):
        return ""
    if (
        _scopes_change_to_existing_shaw_related_removal(text)
        or _is_existing_shaw_variant_with_negated_missing_claim(text)
    ):
        return ""
    span = _first_regex_span(text, _MISSING_SHAW_RELATED_REMOVAL_PATTERNS)
    if _span_is_shaw_contrast_not_missing_claim(span):
        return ""
    return span

_MISSING_SHAW_RELATED_REMOVAL_PATTERNS = (
        r"\b(?:missing|lacks?|absent|without|no)\b.{0,80}"
        r"\b(?:shaw|related|relatedness|proximity|cluster(?:ed)?)\b.{0,80}"
        r"\b(?:destroy|remov(?:al|e)|operator|mechanism)\b",
        r"\b(?:shaw|related|relatedness|proximity|cluster(?:ed)?)\b.{0,80}"
        r"\b(?:destroy|remov(?:al|e)|operator|mechanism)\b.{0,80}"
        r"\b(?:missing|lacks?|absent|without|no)\b",
        r"\b(?:current|existing|active|champion|baseline|solver)\b.{0,90}"
        r"\b(?:missing|lacks?|absent|without|no)\b.{0,90}"
        r"\b(?:shaw|related|relatedness|proximity|cluster(?:ed)?)\b",
)

def _duplicates_shaw_related_removal(text: str) -> bool:
    if not _mentions_shaw_related_removal(text):
        return False
    if _targets_perturbation_or_restart_not_removal_family(text):
        return False
    if _is_shaw_contrast_or_negated_addition(text):
        return False
    if _is_positional_or_arc_destroy_variant(text):
        return False
    if _is_random_or_noise_removal_variant(text) and not _mentions_exact_shaw_related_fact(
        text
    ):
        return False
    if _targets_worst_removal_savings_not_shaw(text):
        return False
    if _targets_segment_chain_unit_not_related_removal(text):
        return False
    if _is_pure_geographic_cluster_variant_acknowledging_shaw(text):
        return False
    if _describes_existing_shaw_related_improvement(text):
        return False
    patterns = (
        r"\b(?:add|introduce|implement|enable|create|build)\b.{0,50}"
        r"\b(?:new|novel|entirely new|first)\b.{0,60}"
        r"\b(?:shaw|related|relatedness|proximity|cluster(?:ed)?)\b.{0,80}"
        r"\b(?:destroy|remov(?:al|e)|operator|mechanism|capability)\b",
        r"\b(?:add|introduce|implement|enable|create|build)\b.{0,80}"
        r"\b(?:shaw style|shaw|related removal|relatedness removal|"
        r"proximity cluster|proximity based|cluster removal|clustered removal)\b"
        r".{0,80}\b(?:destroy|remov(?:al|e)|operator|mechanism|capability)\b",
        r"\b(?:shaw|related|relatedness|proximity|cluster(?:ed)?)\b.{0,80}"
        r"\b(?:destroy|remov(?:al|e)|operator|mechanism|capability)\b.{0,80}"
        r"\b(?:new|novel|entirely new|first)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)

def _span_is_shaw_contrast_not_missing_claim(span: str) -> bool:
    if not span:
        return False
    return _has_any(
        span,
        (
            " unlike ",
            " distinct from ",
            " different from ",
            " rather than ",
            " not a related ",
            " not related ",
            " does not add ",
            " does not add shaw ",
            " without adding shaw ",
            " not shaw removal ",
            " not a proximity cluster ",
            " not proximity cluster ",
        ),
    )


def _is_cluster_variant_contrasting_existing_shaw(text: str) -> bool:
    if not _mentions_shaw_related_removal(text):
        return False
    if not _has_any(text, ("cluster", "zone", "centroid", "geographic", "spatial")):
        return False
    if not _has_any(text, ("existing shaw removal", "current shaw removal")):
        return False
    return _has_any(
        text,
        (
            "unlike the existing shaw",
            "unlike existing shaw",
            "unlike current shaw",
            "distinct from existing shaw",
            "different from existing shaw",
            "rather than existing shaw",
            "compared with existing shaw",
            "instead of existing shaw",
        ),
    )


def _is_shaw_contrast_or_negated_addition(text: str) -> bool:
    return _has_any(
        text,
        (
            " unlike shaw ",
            " unlike _shaw_removal ",
            " unlike shaw related ",
            " unlike the existing shaw ",
            " unlike existing shaw ",
            " unlike current shaw ",
            " distinct from shaw ",
            " distinct from _shaw_removal ",
            " distinct from shaw related ",
            " distinct from related removal ",
            " distinct from existing shaw ",
            " different from shaw ",
            " different from existing shaw ",
            " rather than shaw ",
            " rather than existing shaw ",
            " not a related destroy ",
            " not a related removal ",
            " not related removal ",
            " not a new shaw ",
            " not a new shaw related ",
            " not a new related removal ",
            " not shaw removal ",
            " not shaw or proximity removal ",
            " not shaw related removal ",
            " not shaw related ",
            " not shaw related removal and not proximity removal ",
            " not a proximity cluster ",
            " not proximity cluster ",
            " not proximity removal ",
            " not a cluster destroy ",
            " not cluster destroy ",
            " does not add shaw ",
            " does not add shaw/proximity ",
            " without adding shaw ",
        ),
    )

def _describes_existing_shaw_related_improvement(text: str) -> bool:
    if _scopes_change_to_existing_shaw_related_removal(text):
        return True
    if _is_existing_shaw_variant_with_negated_missing_claim(text):
        return True
    if _has_any(
        text,
        (
            "missing",
            "lacks",
            "lack ",
            "absent",
            "new capability",
            "new destroy capability",
            "new operator",
            "new mechanism",
            "entirely new",
        ),
    ):
        return False
    if _has_any(text, ("existing", "current", "already", "_shaw_removal", "shaw removal")):
        return True
    return _has_any(
        text,
        (
            "refine",
            "tune",
            "adjust",
            "adapt",
            "adaptive",
            "diversify",
            "stochastic",
            "sampling",
            "p sampling",
            "weight",
            "weights",
            "relatedness criteria",
            "score",
            "scoring",
            "phi",
        ),
    )

def _scopes_change_to_existing_shaw_related_removal(text: str) -> bool:
    return _has_any(
        text,
        (
            "without adding",
            "without introducing",
            "without creating",
            "without building",
            "without changing the operator set",
        ),
    ) and _has_any(
        text,
        (
            "existing",
            "current",
            "improve",
            "refine",
            "tune",
            "adjust",
            "adapt",
            "adaptive",
            "diversify",
            "stochastic",
            "sampling",
            "weight",
            "weights",
        ),
    )

def _is_existing_shaw_variant_with_negated_missing_claim(text: str) -> bool:
    if not _has_any(
        text,
        (
            "existing _shaw_removal",
            "existing shaw removal",
            "variant of the existing shaw",
            "modify existing _shaw_removal",
        ),
    ):
        return False
    if not _has_any(
        text,
        (
            "trigger",
            "scoring",
            "score",
            "schedule",
            "candidate filtering",
            "filtering",
            "adaptive",
            "weights",
        ),
    ):
        return False
    return _has_any(
        text,
        (
            "not a new missing",
            "not claiming",
            "do not claim",
            "does not claim",
            "without claiming",
        ),
    )
