from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _first_regex_span, _has_any
from scion.problems.cvrp.mechanism_novelty.destroy_repair.shared import (
    _is_non_regret_repair_variant,
    _mentions_regret_insertion_repair,
)

def _claims_missing_regret_insertion_repair(text: str) -> bool:
    if not _mentions_regret_insertion_repair(text):
        return False
    if _is_non_regret_repair_variant(text) and not _missing_regret_insertion_repair_span(
        text
    ):
        return False
    if _uses_existing_regret_repair_after_new_destroy(text):
        return False
    if _describes_existing_regret_repair_improvement(text):
        return False
    return bool(_missing_regret_insertion_repair_span(text))

def _mischaracterizes_regret_insertion_repair(text: str) -> bool:
    return bool(_regret_semantic_mischaracterization_span(text))

def _duplicates_regret_insertion_repair(text: str) -> bool:
    if not _mentions_regret_insertion_repair(text):
        return False
    if _is_non_regret_repair_variant(text):
        return False
    if _uses_existing_regret_repair_after_new_destroy(text):
        return False
    if _describes_existing_regret_repair_improvement(text):
        return False
    return bool(_duplicate_regret_insertion_repair_span(text))

def _missing_regret_insertion_repair_span(text: str) -> str:
    span = _first_regex_span(
        text,
        (
            r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
            r"doesn't have|doesn't include)\b.{0,120}\b(?:regret[- ]?[23k]?|"
            r"regret insertion|regret repair)\b",
            r"\b(?:regret[- ]?[23k]?|regret insertion|regret repair)\b"
            r".{0,120}\b(?:missing|lacks?|absent|without|no|does not have|"
            r"does not include|doesn't have|doesn't include)\b",
        ),
    )
    if span and re.search(
        r"\bwithout\b.{0,80}\b(?:add|adding|introduce|introducing|create|creating|new)\b",
        span,
    ):
        return ""
    return span

def _regret_semantic_mischaracterization_span(text: str) -> str:
    if not _mentions_regret_insertion_repair(text):
        return ""
    return _first_regex_span(
        text,
        (
            r"\b(?:regret[- ]?[23k]?|regret insertion|regret repair)\b"
            r".{0,160}\b(?:globally cheapest|cheapest positions?|"
            r"without considering regret|ignores? regret|no regret score|"
            r"not use regret score)\b",
            r"\b(?:globally cheapest|cheapest positions?|without considering regret|"
            r"ignores? regret|no regret score|not use regret score)\b"
            r".{0,160}\b(?:regret[- ]?[23k]?|regret insertion|regret repair)\b",
        ),
    )

def _duplicate_regret_insertion_repair_span(text: str) -> str:
    return _first_regex_span(
        text,
        (
            r"\b(?:add|introduce|implement|enable|create|build|register)\b"
            r".{0,120}\b(?:regret[- ]?[23k]?|regret insertion|regret repair)"
            r"\b.{0,80}\b(?:repair|insertion|operator|heuristic|capability)\b",
            r"\b(?:regret[- ]?[23k]?|regret insertion|regret repair)\b"
            r".{0,100}\b(?:new|novel|additional|first|missing|absent|lacks?)\b",
        ),
    )

def _uses_existing_regret_repair_after_new_destroy(text: str) -> bool:
    if not _mentions_regret_insertion_repair(text):
        return False
    if _missing_regret_insertion_repair_span(text):
        return False
    if not _has_any(
        text,
        (
            "destroy",
            "removal",
            "remove",
            "operator",
            "removed customers",
            "removed customer",
        ),
    ):
        return False
    return _has_any(
        text,
        (
            "use existing regret",
            "uses existing regret",
            "using existing regret",
            "call existing regret",
            "calls existing regret",
            "use regret repair",
            "uses regret repair",
            "using regret repair",
            "call regret repair",
            "calls regret repair",
            "apply regret repair",
            "applies regret repair",
            "reuse regret",
            "reuses regret",
            "route through regret",
            "routes through regret",
            "then regret",
            "then use regret",
            "then uses regret",
            "then calls regret",
            "after removal regret",
            "after destroy regret",
            "repair removed customers with regret",
            "reinsert removed customers with regret",
            "forces regret repair",
            "force regret repair",
            "paired with regret repair",
            "followed by regret repair",
        ),
    )

def _regret_insertion_allowed_variant_guidance(text: str) -> str:
    if not _uses_existing_regret_repair_after_new_destroy(text):
        return ""
    return (
        "Allowed variant: the proposal may add or modify a destroy/removal "
        "operator that routes removed customers through the existing regret "
        "repair portfolio; do not treat that as claiming regret repair is absent."
    )

def _describes_existing_regret_repair_improvement(text: str) -> bool:
    if _has_any(
        text,
        (
            "missing",
            "lacks",
            "lack ",
            "absent",
            "new capability",
            "new repair capability",
            "new operator",
            "new heuristic",
            "entirely new",
            "additional repair",
        ),
    ):
        return False
    if not _has_any(
        text,
        ("existing", "current", "already", "_regret2_insertion", "_regret3_insertion"),
    ):
        return False
    return _has_any(
        text,
        (
            "refine",
            "tune",
            "adjust",
            "adapt",
            "bias",
            "sampling",
            "weight",
            "candidate ordering",
            "budget",
        ),
    )
