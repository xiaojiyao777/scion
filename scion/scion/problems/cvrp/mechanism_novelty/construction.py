"""Construction-seed premise predicates for CVRP mechanism novelty."""

from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _first_regex_span, _has_any


def _claims_nearest_neighbor_only(text: str) -> bool:
    if not _has_any(text, ("nearest neighbor", " nn ")):
        return False
    if _acknowledges_diverse_construction_portfolio(text):
        return False
    return any(re.search(pattern, text) for pattern in _NEAREST_NEIGHBOR_ONLY_PATTERNS)


def _nearest_neighbor_only_span(text: str) -> str:
    if not _claims_nearest_neighbor_only(text):
        return ""
    return _first_regex_span(text, _NEAREST_NEIGHBOR_ONLY_PATTERNS)


_NEAREST_NEIGHBOR_ONLY_PATTERNS = (
    r"\b(?:baseline|current|existing|active|champion|solver)\b.{0,90}"
    r"\b(?:only|single|sole|just|exclusively)\b.{0,60}"
    r"\b(?:nearest neighbor|nn)\b.{0,50}\b(?:seed|construction|initial)",
    r"\b(?:single|only|sole|just|exclusively)\b.{0,30}"
    r"\b(?:nearest neighbor|nn)\b.{0,40}\b(?:seed|construction|initial)",
    r"\b(?:nearest neighbor|nn)\b.{0,25}\b(?:only|single|sole)\b",
)


def _acknowledges_diverse_construction_portfolio(text: str) -> bool:
    if not _has_any(text, ("portfolio", "construction", "seed")):
        return False
    if not all(
        _has_any(text, group)
        for group in (
            ("sweep",),
            ("clarke wright", "clarke-wright", "savings"),
            ("capacity balanced", "capacity-balanced"),
            ("nearest neighbor", " nn "),
        )
    ):
        return False
    missing_portfolio_terms = (
        "no sweep",
        "without sweep",
        "lacks sweep",
        "missing sweep",
        "no clarke",
        "without clarke",
        "lacks clarke",
        "missing clarke",
        "no capacity balanced",
        "without capacity balanced",
        "lacks capacity balanced",
        "missing capacity balanced",
    )
    return not _has_any(text, missing_portfolio_terms)
