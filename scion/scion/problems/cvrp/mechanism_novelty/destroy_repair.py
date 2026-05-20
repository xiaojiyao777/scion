"""Destroy/repair premise predicates for CVRP mechanism novelty."""

from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _has_any


def _claims_missing_shaw_related_removal(text: str) -> bool:
    if not _mentions_shaw_related_removal(text):
        return False
    if _targets_segment_chain_unit_not_related_removal(text):
        return False
    if _scopes_change_to_existing_shaw_related_removal(text):
        return False
    patterns = (
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
    return any(re.search(pattern, text) for pattern in patterns)


def _duplicates_shaw_related_removal(text: str) -> bool:
    if not _mentions_shaw_related_removal(text):
        return False
    if _targets_segment_chain_unit_not_related_removal(text):
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


def _claims_missing_removal_savings_destroy(text: str) -> bool:
    if not _mentions_removal_savings_destroy(text):
        return False
    if _describes_existing_removal_savings_improvement(text):
        return False
    patterns = (
        r"\b(?:missing|lacks?|absent|without|no)\b.{0,120}"
        r"\b(?:removal savings?|savings removal|detour cost|marginal distance contribution|cost of remove)\b",
        r"\b(?:removal savings?|savings removal|detour cost|marginal distance contribution|cost of remove)\b.{0,120}"
        r"\b(?:missing|lacks?|absent|without|no)\b",
        r"\b(?:worst removal|current|existing|active|baseline|solver)\b.{0,140}"
        r"\b(?:not|does not|doesn t|isn t|is not)\b.{0,80}"
        r"\b(?:removal savings?|savings from removal|cost of remove|detour cost)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _duplicates_removal_savings_destroy(text: str) -> bool:
    if not _mentions_removal_savings_destroy(text):
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


def _mentions_shaw_related_removal(text: str) -> bool:
    if "shaw" in text and _has_any(text, ("removal", "remove", "destroy")):
        return True
    phrases = (
        "related removal",
        "relatedness removal",
        "related destroy",
        "relatedness destroy",
        "proximity cluster",
        "proximity based removal",
        "proximity removal",
        "cluster removal",
        "clustered removal",
        "cluster destroy",
        "clustered destroy",
        "nearby customer removal",
        "neighbor removal",
        "neighbour removal",
    )
    if _has_any(text, phrases):
        return True
    return bool(
        re.search(
            r"\b(?:related|relatedness|proximity|cluster(?:ed)?|nearby|neighbou?r)\b"
            r".{0,50}\b(?:destroy|remov(?:al|e)|operator)\b",
            text,
        )
        or re.search(
            r"\b(?:destroy|remov(?:al|e)|operator)\b.{0,50}"
            r"\b(?:related|relatedness|proximity|cluster(?:ed)?|nearby|neighbou?r)\b",
            text,
        )
    )


def _mentions_removal_savings_destroy(text: str) -> bool:
    if _has_any(
        text,
        (
            "savings removal",
            "removal saving",
            "removal savings",
            "savings from removal",
            "cost of remove",
            "detour cost",
            "detour based removal",
            "position aware targeted removal",
            "marginal distance contribution",
            "geometric detour",
        ),
    ):
        return True
    return bool(
        re.search(
            r"\b(?:saving|savings|detour|marginal distance)\b.{0,70}"
            r"\b(?:destroy|remov(?:al|e)|operator|heuristic)\b",
            text,
        )
    )


def _describes_existing_shaw_related_improvement(text: str) -> bool:
    if _scopes_change_to_existing_shaw_related_removal(text):
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


def _targets_segment_chain_unit_not_related_removal(text: str) -> bool:
    if not _has_any(
        text,
        (
            "segment chain",
            "segment-chain",
            "contiguous segment",
            "ordered segment",
            "chain as a unit",
            "segment as a unit",
            "contiguous customer",
        ),
    ):
        return False
    if re.search(
        r"\b(?:add|introduce|implement|create|build)\b.{0,70}"
        r"\b(?:shaw|relatedness|related removal|related destroy|"
        r"proximity cluster|cluster removal)\b",
        text,
    ):
        return False
    return True
