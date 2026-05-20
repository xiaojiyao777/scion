"""Acceptance/adaptive-weight premise predicates for CVRP mechanism novelty."""

from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _first_regex_span, _has_any


def _claims_weights_non_adaptive(text: str) -> bool:
    if "weight" not in text:
        return False
    if (
        "uniform" in text
        and _has_any(text, ("initial", "initialize", "start"))
        and not _has_any(text, ("throughout", "entire", "whole", "always", "remain"))
    ):
        return False
    if _claims_alns_weights_non_adaptive(text):
        return True
    if _claims_global_weights_non_adaptive(text):
        return True
    if _is_vns_neighborhood_weight_scope(text):
        return False
    return _claims_unscoped_operator_weights_non_adaptive(text)


def _weights_non_adaptive_span(text: str) -> str:
    if not _claims_weights_non_adaptive(text):
        return ""
    return _first_regex_span(
        text,
        (
            *_ALNS_WEIGHT_NON_ADAPTIVE_PATTERNS,
            *_GLOBAL_WEIGHT_NON_ADAPTIVE_PATTERNS,
            *_UNSCOPED_WEIGHT_NON_ADAPTIVE_PATTERNS,
        ),
    )


_NON_ADAPTIVE_WEIGHT_TERMS = (
    r"(?:uniform|static|fixed|non adaptive|nonadaptive|not adaptive)"
)


def _is_vns_neighborhood_weight_scope(text: str) -> bool:
    return _has_any(
        text,
        (
            " vns ",
            " variable neighborhood ",
            " local search ",
            " neighborhood ",
            " neighbourhood ",
        ),
    )


def _claims_alns_weights_non_adaptive(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in _ALNS_WEIGHT_NON_ADAPTIVE_PATTERNS)


def _claims_global_weights_non_adaptive(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in _GLOBAL_WEIGHT_NON_ADAPTIVE_PATTERNS)


def _claims_unscoped_operator_weights_non_adaptive(text: str) -> bool:
    return any(
        re.search(pattern, text)
        for pattern in _UNSCOPED_WEIGHT_NON_ADAPTIVE_PATTERNS
    )


_WEIGHT_SCOPE = r"(?:alns|destroy|repair|destroy repair|destroy and repair)"

_ALNS_WEIGHT_NON_ADAPTIVE_PATTERNS = (
        rf"\b{_WEIGHT_SCOPE}\b.{{0,50}}\bweights?\b.{{0,35}}"
        rf"\b(?:remain|stays?|are|is|currently|still|always)\b.{{0,25}}"
        rf"\b{_NON_ADAPTIVE_WEIGHT_TERMS}\b",
        rf"\b{_WEIGHT_SCOPE}\b.{{0,50}}\bweights?\b.{{0,35}}"
        r"\b(?:never|do not|does not|don't|without)\b.{0,25}"
        r"\b(?:update|adapt|record|learn)\b",
        rf"\b{_NON_ADAPTIVE_WEIGHT_TERMS}\b.{{0,35}}\b{_WEIGHT_SCOPE}\b.{{0,35}}"
        r"\bweights?\b",
)

_GLOBAL_WEIGHT_NON_ADAPTIVE_PATTERNS = (
        r"\b(?:all|every|global|overall)\b.{0,35}\b(?:operator\s+)?weights?\b"
        r".{0,35}\b(?:remain|stays?|are|is|currently|still|always)\b.{0,25}"
        rf"\b{_NON_ADAPTIVE_WEIGHT_TERMS}\b",
        r"\b(?:operator|adaptive)\b.{0,20}\bweights?\b.{0,35}"
        r"\b(?:remain|stays?|are|is|currently|still|always)\b.{0,25}"
        rf"\b{_NON_ADAPTIVE_WEIGHT_TERMS}\b"
        r"(?:.{0,45}\b(?:throughout|entire|whole|all iterations|all run|run|solver)\b)",
        r"\b(?:all|every|operator|adaptive)\b.{0,20}\bweights?\b.{0,35}"
        r"\b(?:never|do not|does not|don't|without)\b.{0,25}"
        r"\b(?:update|adapt|record|learn)\b",
        rf"\b{_NON_ADAPTIVE_WEIGHT_TERMS}\b.{{0,35}}"
        r"\b(?:all|every|operator|adaptive)\b.{0,20}\bweights?\b"
        r".{0,45}\b(?:throughout|entire|whole|all iterations|all run|run|solver)\b",
)

_UNSCOPED_WEIGHT_NON_ADAPTIVE_PATTERNS = (
        r"\b(?:adaptive|operator)\b.{0,30}\bweights?\b.{0,30}"
        r"\b(?:remain|stays?|are|is|currently|still|always)\b.{0,20}"
        rf"\b{_NON_ADAPTIVE_WEIGHT_TERMS}\b",
        r"\bweights?\b.{0,30}\b(?:never|do not|does not|don't|without)\b.{0,25}"
        r"\b(?:update|adapt|record|learn)\b",
        rf"\b(?:non adaptive|nonadaptive|not adaptive|static)\b.{{0,30}}"
        r"\b(?:operator|adaptive)\b.{0,20}\bweights?\b",
)
