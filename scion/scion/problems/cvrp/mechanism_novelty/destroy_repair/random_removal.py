from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _first_regex_span, _has_any
from scion.problems.cvrp.mechanism_novelty.destroy_repair.shared import (
    _mentions_random_removal_destroy,
)

def _claims_missing_random_removal_destroy(text: str) -> bool:
    return bool(_missing_random_removal_destroy_span(text))

def _missing_random_removal_destroy_span(text: str) -> str:
    if not _mentions_random_removal_destroy(text):
        return ""
    if _describes_existing_random_removal_variant(text):
        return ""
    if _describes_existing_random_removal_contrast_variant(text):
        return ""
    span = _first_regex_span(text, _MISSING_RANDOM_REMOVAL_DESTROY_PATTERNS)
    if _span_is_random_exploration_weakness_not_missing_removal(span):
        return ""
    if _span_is_noop_condition_not_missing_random_removal(span):
        return ""
    return span

_MISSING_RANDOM_REMOVAL_DESTROY_PATTERNS = (
    r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
    r"doesn'?t have|doesn'?t include)\b.{0,100}"
    r"\b(?:random(?: customer)? removal|random customer destroy|"
    r"random destroy|randomized removal|randomized destroy|uniform random removal)\b",
    r"\b(?:random(?: customer)? removal|random customer destroy|"
    r"random destroy|randomized removal|randomized destroy|uniform random removal)"
    r"\b.{0,100}\b(?:missing|lacks?|absent|without|no|does not have|"
    r"does not include|doesn'?t have|doesn'?t include)\b",
)

def _duplicates_random_removal_destroy(text: str) -> bool:
    if not _mentions_random_removal_destroy(text):
        return False
    if _describes_existing_random_removal_variant(text):
        return False
    if _describes_existing_random_removal_contrast_variant(text):
        return False
    patterns = (
        r"\b(?:add|introduce|implement|enable|create|build|register)\b"
        r".{0,100}\b(?:random(?: customer)? removal|random customer destroy|"
        r"random destroy|randomized removal|randomized destroy|"
        r"uniform random removal)\b",
        r"\b(?:random(?: customer)? removal|random customer destroy|"
        r"random destroy|randomized removal|randomized destroy|"
        r"uniform random removal)\b.{0,100}"
        r"\b(?:new|novel|additional|first|missing|absent|lacks?|new capability|"
        r"new operator|new destroy)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)

def _span_is_random_exploration_weakness_not_missing_removal(span: str) -> bool:
    if not span:
        return False
    return bool(
        re.search(r"\blacks?\b.{0,40}\brandom exploration\b", span)
        or re.search(r"\bmissing\b.{0,40}\brandom exploration\b", span)
    )

def _span_is_noop_condition_not_missing_random_removal(span: str) -> bool:
    if not span:
        return False
    return _has_any(span, ("no-op", "no op", "noop", "no-op condition"))

def _describes_existing_random_removal_variant(text: str) -> bool:
    if not _mentions_random_removal_destroy(text):
        return False
    if not _acknowledges_existing_random_removal_destroy(text):
        return False
    if _has_any(
        text,
        (
            "missing random removal",
            "lacks random removal",
            "lack random removal",
            "absent random removal",
            "no random removal",
            "without random removal",
            "missing random customer removal",
            "lacks random customer removal",
            "new random removal capability",
            "new random removal operator",
        ),
    ):
        return False
    return _has_any(
        text,
        (
            "refine",
            "tune",
            "adjust",
            "adapt",
            "adaptive",
            "variant",
            "distribution",
            "biased",
            "bias",
            "weighted",
            "weight",
            "noise",
            "schedule",
            "sampling",
            "probability",
            "probabilistic",
            "trigger",
            "budget",
            "q budget",
            "telemetry",
            "instrumentation",
        ),
    )

def _describes_existing_random_removal_contrast_variant(text: str) -> bool:
    if not _mentions_random_removal_destroy(text):
        return False
    if not _has_any(
        text,
        (
            "cluster",
            "proximity",
            "geographic",
            "spatial",
            "nearest customer",
            "nearest customers",
            "nearby customer",
            "nearby customers",
        ),
    ):
        return False
    return _has_any(
        text,
        (
            "distinct from random",
            "different from random",
            "unlike random",
            "rather than random",
            "not random removal",
            "not a random removal",
            "random removal (uniform",
            "uniform random",
            "uniform sampling",
            "existing random removal",
            "current random removal",
            "baseline random removal",
            "random removal is uniform",
            "random removal samples uniformly",
        ),
    )

def _acknowledges_existing_random_removal_destroy(text: str) -> bool:
    if not _mentions_random_removal_destroy(text):
        return False
    random_family = (
        r"(?:random removal|random destroy|random customer removal|"
        r"scheduler random|randomized removal|uniform random removal)"
    )
    return bool(
        re.search(
            r"\b(?:existing|current|active|baseline|already)\b.{0,100}\b"
            + random_family
            + r"\b",
            text,
        )
        or re.search(
            r"\b"
            + random_family
            + r"\b.{0,100}\b(?:already|exists?|registered|wired|present|"
            r"available|in the portfolio|in destroy ops)\b",
            text,
        )
    )
