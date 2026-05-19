"""Construction-seed premise predicates for CVRP mechanism novelty."""

from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _has_any


def _claims_nearest_neighbor_only(text: str) -> bool:
    if not _has_any(text, ("nearest neighbor", " nn ")):
        return False
    patterns = (
        r"\b(?:baseline|current|existing|active|champion|solver)\b.{0,90}"
        r"\b(?:only|single|sole|just|exclusively)\b.{0,60}"
        r"\b(?:nearest neighbor|nn)\b.{0,50}\b(?:seed|construction|initial)",
        r"\b(?:single|only|sole|just|exclusively)\b.{0,30}"
        r"\b(?:nearest neighbor|nn)\b.{0,40}\b(?:seed|construction|initial)",
        r"\b(?:nearest neighbor|nn)\b.{0,25}\b(?:only|single|sole)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)
