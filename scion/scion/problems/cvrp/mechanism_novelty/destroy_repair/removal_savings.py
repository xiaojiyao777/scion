from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _first_regex_span, _has_any
from scion.problems.cvrp.mechanism_novelty.destroy_repair.shared import (
    _explicit_removal_savings_claim,
    _is_insertion_aware_variant_acknowledging_removal_savings,
    _is_pure_geographic_cluster_variant_acknowledging_removal_savings,
    _is_random_or_noise_removal_variant,
    _is_removal_savings_contrast_or_negated_addition,
    _mentions_removal_savings_destroy,
)

def _claims_missing_removal_savings_destroy(text: str) -> bool:
    return bool(_missing_removal_savings_destroy_span(text))

def _missing_removal_savings_destroy_span(text: str) -> str:
    if not _mentions_removal_savings_destroy(text):
        return ""
    if _is_pure_geographic_cluster_variant_acknowledging_removal_savings(text):
        return ""
    if _is_insertion_aware_variant_acknowledging_removal_savings(text):
        return ""
    if _describes_existing_removal_savings_improvement(text):
        return ""
    return _first_regex_span(text, _MISSING_REMOVAL_SAVINGS_DESTROY_PATTERNS)

_MISSING_REMOVAL_SAVINGS_DESTROY_PATTERNS = (
        r"\b(?:missing|lacks?|absent|without|no)\b.{0,120}"
        r"\b(?:removal savings?|savings removal|detour cost|marginal distance contribution|cost of remove)\b",
        r"\b(?:removal savings?|savings removal|detour cost|marginal distance contribution|cost of remove)\b.{0,120}"
        r"\b(?:missing|lacks?|absent|without|no)\b",
        r"\b(?:worst removal|current|existing|active|baseline|solver)\b.{0,140}"
        r"\b(?:not|does not|doesn t|isn t|is not)\b.{0,80}"
        r"\b(?:removal savings?|savings from removal|cost of remove|detour cost)\b",
)

def _duplicates_removal_savings_destroy(text: str) -> bool:
    if not _mentions_removal_savings_destroy(text):
        return False
    if _is_pure_geographic_cluster_variant_acknowledging_removal_savings(text):
        return False
    if _is_insertion_aware_variant_acknowledging_removal_savings(text):
        return False
    if (
        _is_random_or_noise_removal_variant(text)
        and _is_removal_savings_contrast_or_negated_addition(text)
    ):
        return False
    if _is_random_or_noise_removal_variant(text) and not _explicit_removal_savings_claim(
        text
    ):
        return False
    if _describes_existing_removal_savings_improvement(text):
        return False
    patterns = (
        r"\b(?:add|introduce|implement|enable|create|build|register)\b.{0,80}"
        r"\b(?:new|novel|entirely new|fourth|additional)?\b.{0,80}"
        r"\b(?:savings removal|removal savings?|detour cost|marginal distance contribution|cost of remove)\b"
        r".{0,100}\b(?:destroy|remov(?:al|e)|operator|heuristic|capability)\b",
        r"\b(?:add|introduce|implement|enable|create|build|register)\b.{0,100}"
        r"\b(?:savings removal|savings based removal|detour based removal|position aware targeted removal)\b",
        r"\b(?:savings removal|removal savings?|detour cost|marginal distance contribution|cost of remove)\b"
        r".{0,100}\b(?:destroy|remov(?:al|e)|operator|heuristic|capability)\b.{0,80}"
        r"\b(?:new|novel|entirely new|fourth|additional|absent|missing|lacks?)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)

def _describes_existing_removal_savings_improvement(text: str) -> bool:
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
            "new heuristic",
            "entirely new",
            "fourth destroy",
            "additional destroy",
            "savings removal",
        ),
    ):
        return False
    if not _has_any(text, ("existing", "current", "already", "worst removal")):
        return False
    return _has_any(
        text,
        (
            "refine",
            "tune",
            "adjust",
            "adapt",
            "adaptive",
            "diversify",
            "sampling",
            "noise",
            "p sampling",
            "weight",
            "weights",
            "budget",
            "candidate ordering",
        ),
    )
