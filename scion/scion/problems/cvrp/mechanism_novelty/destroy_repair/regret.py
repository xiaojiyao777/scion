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
    if _negates_regret_absence_claim(text):
        return False
    if _acknowledges_existing_regret_repair_variant(text):
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
    if _negates_regret_absence_claim(text):
        return False
    if _acknowledges_existing_regret_repair_variant(text):
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
    if span and _absence_word_does_not_target_regret(span):
        return ""
    if span and re.search(
        r"\bwithout\b.{0,80}\b(?:add|adding|introduce|introducing|create|creating|new)\b",
        span,
    ):
        return ""
    if span and _acknowledges_existing_regret_repair(text) and _span_targets_variant_not_regret(
        span
    ):
        return ""
    if span and _acknowledges_existing_regret_repair(text):
        if re.search(r"\bnot\b.{0,30}\b(?:claim|premise|assert)", span):
            return ""
        if _uses_regret_after_stagnation_escape_variant(text):
            return ""
        if _acknowledged_regret_lacks_variant_only(text):
            return ""
        if _describes_route_merge_compaction_variant(text):
            return ""
    return span


def _negates_regret_absence_claim(text: str) -> bool:
    regret = r"(?:regret[- ]?[23k]?|regret insertion|regret repair)"
    absence = r"(?:absent|missing|lacks?|does not have|doesn't have)"
    return bool(
        re.search(
            r"\b(?:without|not|does not|doesn't)\s+"
            r"(?:claim(?:ing)?|assert(?:ing)?|premis(?:e|ing))\b"
            r".{0,120}\b" + regret + r"\b.{0,100}\b" + absence + r"\b",
            text,
        )
        or re.search(
            r"\b(?:is not|isn't|not)\b.{0,40}\b(?:a\s+)?claim\b"
            r".{0,120}\b" + regret + r"\b.{0,100}\b" + absence + r"\b",
            text,
        )
    )


def _absence_word_does_not_target_regret(span: str) -> bool:
    """Return true when a broad absence word points at a variant, not regret."""

    normalized = span.lower()
    regret = r"(?:regret[- ]?[23k]?|regret insertion|regret repair)"
    if "without" in normalized and not re.search(
        r"\bwithout\b\s+(?:any\s+)?(?:(?:a|an)\s+)?(?:new\s+)?"
        r"(?:regret[- ]?[23k]?|regret insertion|regret repair)",
        normalized,
    ):
        return True
    if re.search(
        regret
        + r".{0,100}\b(?:without|no)\b.{0,80}"
        + r"(?:escape|escaping|stagnation|restart|perturbation|"
        + r"embedded|vns|local search|operator|fallback)",
        normalized,
    ):
        return True
    if re.search(
        r"\b(?:without|no)\b.{0,80}"
        + r"(?:escape|escaping|stagnation|restart|perturbation|embedded|vns|"
        + r"local search|operator|fallback).{0,120}"
        + regret,
        normalized,
    ):
        return True
    return False


def _span_targets_variant_not_regret(span: str) -> bool:
    return _has_any(
        span,
        (
            "candidate",
            "candidate list",
            "candidate-list",
            "filter",
            "filtered",
            "nearest",
            "neighbor",
            "neighbour",
            "knn",
            "nn",
            "spatial",
            "proximity",
            "cluster",
            "nearby",
            "co removed",
            "co-removed",
            "reinsertion",
            "re-insertion",
            "insertion opportunity",
            "position cost",
            "position-cost",
            "merge",
            "merging",
            "compaction",
            "compact",
            "route shaping",
            "route-shaping",
            "small route",
            "near-empty route",
            "short route",
            "stagnation escape",
            "escape",
            "restart",
            "perturbation",
            "large perturbation",
        ),
    )


def _acknowledged_regret_lacks_variant_only(text: str) -> bool:
    variant = (
        r"(?:candidate[- ]?list|candidate filter|filtered|filtering|nearest[- ]?"
        r"neighbou?r|knn|nn|spatial|proximity|cluster|nearby|reinsertion|"
        r"re[- ]?insertion|insertion opportunity|position[- ]?cost)"
    )
    regret = r"(?:regret[- ]?[23k]?|regret insertion|regret repair)"
    return bool(
        re.search(regret + r".{0,100}\blacks?\b.{0,100}" + variant, text)
        or re.search(
            r"\blacks?\b.{0,100}" + variant + r".{0,160}" + regret,
            text,
        )
    )


def _describes_route_merge_compaction_variant(text: str) -> bool:
    if not _has_any(
        text,
        (
            "merge",
            "merging",
            "compaction",
            "compact",
            "route shaping",
            "route-shaping",
        ),
    ):
        return False
    return _has_any(
        text,
        (
            "small route",
            "near empty route",
            "near-empty route",
            "short route",
            "post repair",
            "post-repair",
            "alns merge",
            "merge small routes",
        ),
    )


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
            "perturbation",
            "restart",
            "stagnation",
            "escape",
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
            "followed by regret-2",
            "followed by regret-3",
            "followed by regret 2",
            "followed by regret 3",
            "uses regret-2",
            "uses regret-3",
            "using regret-2",
            "using regret-3",
            "leverages existing regret",
            "combines with regret",
        ),
    )


def _uses_regret_after_stagnation_escape_variant(text: str) -> bool:
    if not _mentions_regret_insertion_repair(text):
        return False
    if not _has_any(
        text,
        (
            "stagnation",
            "escape",
            "restart",
            "perturbation",
            "large perturbation",
            "local optimum",
            "plateau",
        ),
    ):
        return False
    return _has_any(
        text,
        (
            "uses regret",
            "using regret",
            "leverages existing regret",
            "existing regret",
            "followed by regret",
            "combines with regret",
            "then regret",
            "after perturbation regret",
            "after restart regret",
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

def _acknowledges_existing_regret_repair_variant(text: str) -> bool:
    """Allow material variants that explicitly acknowledge existing regret repair."""
    if not _acknowledges_existing_regret_repair(text):
        return False
    variant_terms = (
        "bounded",
        "bound ",
        "cap ",
        "capped",
        "top-k",
        "top k",
        "k-nearest",
        "knn",
        "nn-filtered",
        "nn filtered",
        "nearest-neighbor",
        "nearest neighbor",
        "nearest-neighbor filtered",
        "neighbor-limited",
        "neighbour-limited",
        "candidate filter",
        "candidate-filter",
        "candidate list",
        "candidate-list",
        "candidate-list filtering",
        "filtered",
        "filtering",
        "candidate subset",
        "spatial",
        "proximity",
        "cluster",
        "nearby",
        "co-removed",
        "co removed",
        "reinsertion",
        "re-insertion",
        "insertion opportunity",
        "position-cost",
        "position cost",
        "locality",
        "route-local",
        "merge",
        "merging",
        "compaction",
        "compact",
        "route shaping",
        "route-shaping",
        "small route",
        "near-empty route",
        "short route",
        "variant",
    )
    if not _has_any(text, variant_terms):
        return False
    missing_span = _missing_regret_insertion_repair_span(text)
    if missing_span and not _has_any(missing_span, variant_terms):
        return False
    return True


def _acknowledges_existing_regret_repair(text: str) -> bool:
    if _has_any(
        text,
        (
            "existing regret",
            "current regret",
            "already has regret",
            "already includes regret",
            "already contains regret",
            "regret already",
            "_regret2_insertion",
            "_regret3_insertion",
        ),
    ):
        return True
    regret_terms = (
        r"regret[- ]?2",
        r"regret[- ]?3",
        r"regret insertion",
        r"regret repair",
    )
    regret = r"(?:%s)" % "|".join(regret_terms)
    return bool(
        re.search(
            regret
            + r".{0,100}\b(?:exists?|existing|current|available|already|included)\b",
            text,
        )
        or re.search(
            r"\b(?:exists?|existing|current|available|already|included)\b"
            r".{0,100}"
            + regret,
            text,
        )
    )
