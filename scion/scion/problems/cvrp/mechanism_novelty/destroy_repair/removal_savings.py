from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _first_regex_span, _has_any
from scion.problems.cvrp.mechanism_novelty.destroy_repair.shared import (
    _acknowledges_existing_removal_savings_destroy,
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
    span = _first_regex_span(text, _MISSING_REMOVAL_SAVINGS_DESTROY_PATTERNS)
    if span and _span_is_negated_removal_savings_absence_claim(text, span):
        return ""
    if span and _span_is_distinct_variant_acknowledging_removal_savings(text, span):
        return ""
    return span

_MISSING_REMOVAL_SAVINGS_DESTROY_PATTERNS = (
        r"\b(?:current|existing|active|baseline|solver|portfolio|"
        r"destroy portfolio|operator portfolio)\b.{0,100}"
        r"\b(?:missing|lacks?|absent|no)\b.{0,120}"
        r"\b(?:removal savings?|savings removal|detour cost|marginal distance contribution|cost of remove)\b",
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


_REMOVAL_SAVINGS_TERM_RE = (
    r"(?:removal savings?|savings removal|savings worst|worst removal|"
    r"detour cost|marginal distance contribution|cost of remove|"
    r"cost of removal)"
)
_ABSENCE_TERM_RE = (
    r"(?:missing|absent|absence|lacks?|lack|not present|not implemented|"
    r"unavailable|does not exist|no)"
)
_CLAIM_VERB_RE = r"(?:claim(?:ing)?|assert(?:ing)?|stat(?:e|ing)|argu(?:e|ing))"


def _span_is_negated_removal_savings_absence_claim(
    text: str,
    span: str,
) -> bool:
    window = _span_window(text, span, radius=180)
    if not window:
        return False
    patterns = (
        r"\b(?:not|without|rather than|instead of)\s+"
        + _CLAIM_VERB_RE
        + r"\b.{0,140}\b"
        + _REMOVAL_SAVINGS_TERM_RE
        + r"\b.{0,140}\b"
        + _ABSENCE_TERM_RE
        + r"\b",
        r"\b(?:not|without|rather than|instead of)\s+"
        + _CLAIM_VERB_RE
        + r"\b.{0,140}\b"
        + _ABSENCE_TERM_RE
        + r"\b.{0,140}\b"
        + _REMOVAL_SAVINGS_TERM_RE
        + r"\b",
        r"\b(?:does not|doesn t)\s+"
        + _CLAIM_VERB_RE
        + r"\b.{0,140}\b"
        + _REMOVAL_SAVINGS_TERM_RE
        + r"\b.{0,140}\b"
        + _ABSENCE_TERM_RE
        + r"\b",
        r"\b(?:does not|doesn t)\s+"
        + _CLAIM_VERB_RE
        + r"\b.{0,140}\b"
        + _ABSENCE_TERM_RE
        + r"\b.{0,140}\b"
        + _REMOVAL_SAVINGS_TERM_RE
        + r"\b",
        r"\bnot\s+a\s+claim\b.{0,100}\b"
        + _REMOVAL_SAVINGS_TERM_RE
        + r"\b.{0,140}\b"
        + _ABSENCE_TERM_RE
        + r"\b",
        r"\bnot\s+a\s+claim\b.{0,100}\b"
        + _ABSENCE_TERM_RE
        + r"\b.{0,140}\b"
        + _REMOVAL_SAVINGS_TERM_RE
        + r"\b",
        r"\bnot\s+a\b.{0,60}\b"
        + _ABSENCE_TERM_RE
        + r"\b.{0,140}\b"
        + _REMOVAL_SAVINGS_TERM_RE
        + r"\b.{0,80}\bclaim\b",
        r"\bnot\s+a\b.{0,60}\b"
        + _REMOVAL_SAVINGS_TERM_RE
        + r"\b.{0,140}\b"
        + _ABSENCE_TERM_RE
        + r"\b.{0,80}\bclaim\b",
    )
    return any(re.search(pattern, window) for pattern in patterns)


def _span_is_distinct_variant_acknowledging_removal_savings(
    text: str,
    span: str,
) -> bool:
    if not (
        _acknowledges_existing_removal_savings_destroy(text)
        or re.search(
            r"\b(?:existing|current|active|baseline|portfolio|already)\b"
            r".{0,120}\b(?:savings worst|removal savings?|removal saving|"
            r"worst removal|cost of remove)\b",
            text,
        )
        or re.search(
            r"\b(?:removal savings?|removal saving|savings worst|worst removal|"
            r"cost of remove)\b.{0,120}\b(?:existing|current|active|baseline|"
            r"portfolio|already|includes?|contains?)\b",
            text,
        )
    ):
        return False
    window = _span_window(text, span, radius=180)
    distinct_target = (
        r"(?:route pair|load complementarity|capacity slack|residual capacity|"
        r"exchange potential|slack cluster|cluster|complementarity|"
        r"alternative insertion|insertion opportunity|geographic|spatial|variant)"
    )
    return bool(
        re.search(
            r"\b"
            + _REMOVAL_SAVINGS_TERM_RE
            + r"\b.{0,160}\b(?:but|however|whereas|while|different|differs|variant)"
            r"\b.{0,120}\b(?:no|lacks?|without)\b.{0,120}\b"
            + distinct_target
            + r"\b",
            window,
        )
        or re.search(
            r"\b(?:no|lacks?|without)\b.{0,120}\b"
            + distinct_target
            + r"\b.{0,160}\b(?:while|but|however|rather than|instead of)\b"
            r".{0,120}\b"
            + _REMOVAL_SAVINGS_TERM_RE
            + r"\b",
            window,
        )
    )


def _span_window(text: str, span: str, *, radius: int) -> str:
    start = text.find(span)
    if start < 0:
        return text[: radius * 2]
    end = start + len(span)
    return text[max(0, start - radius) : min(len(text), end + radius)]
