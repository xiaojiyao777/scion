"""Acceptance/adaptive-weight premise predicates for CVRP mechanism novelty."""

from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _has_any


def _claims_weights_non_adaptive(text: str) -> bool:
    if "weight" not in text:
        return False
    if (
        "uniform" in text
        and _has_any(text, ("initial", "initialize", "start"))
        and not _has_any(text, ("throughout", "entire", "whole", "always", "remain"))
    ):
        return False
    patterns = (
        r"\b(?:adaptive|operator|destroy|repair)\b.{0,40}\bweights?\b.{0,35}"
        r"\b(?:remain|stays?|are|is|currently|still|always)\b.{0,25}"
        r"\b(?:uniform|static|fixed|non adaptive|nonadaptive|not adaptive)\b"
        r"(?:.{0,45}\b(?:throughout|entire|whole|all iterations|all run)\b)?",
        r"\bweights?\b.{0,35}\b(?:never|do not|does not|don't|without)\b.{0,25}"
        r"\b(?:update|adapt|record|learn)\b",
        r"\b(?:non adaptive|nonadaptive|not adaptive|static|fixed)\b.{0,35}"
        r"\b(?:operator|destroy|repair|adaptive)\b.{0,20}\bweights?\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)
