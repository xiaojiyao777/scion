from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _has_any
from scion.problems.cvrp.mechanism_novelty.destroy_repair.shared import (
    _mentions_route_removal,
    _span_acknowledges_existing_route_removal,
    _targets_contiguous_segment_destroy_not_whole_route_removal,
    _targets_perturbation_or_restart_not_removal_family,
)

def _claims_missing_route_removal(text: str) -> bool:
    return bool(_missing_route_removal_span(text))

def _missing_route_removal_span(text: str) -> str:
    if not _mentions_route_removal(text):
        return ""
    if (
        _targets_contiguous_segment_destroy_not_whole_route_removal(text)
        or _targets_perturbation_or_restart_not_removal_family(text)
    ):
        return ""
    if _acknowledges_existing_route_removal_variant(text):
        return ""
    if _describes_existing_route_removal_improvement(text):
        return ""
    return _first_missing_route_removal_claim_span(text)

def _duplicates_route_removal(text: str) -> bool:
    if not _mentions_route_removal(text):
        return False
    if (
        _targets_contiguous_segment_destroy_not_whole_route_removal(text)
        or _targets_perturbation_or_restart_not_removal_family(text)
    ):
        return False
    if _acknowledges_existing_route_removal_variant(text):
        return False
    if _describes_existing_route_removal_improvement(text):
        return False
    return bool(
        re.search(
            r"\b(?:add|introduce|implement|enable|create|build|register)\b"
            r".{0,100}\b(?:whole route|entire route|route level|route removal|"
            r"route destroy)\b.{0,60}"
            r"\b(?:destroy|remov(?:al|e)|operator|capability)\b",
            text,
        )
        or re.search(
            r"\b(?:whole route|entire route|route level|route removal|"
            r"route destroy)\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)"
            r"\b.{0,100}\b(?:new|novel|additional|first|missing|absent|lacks?)\b",
            text,
        )
    )

def _describes_existing_route_removal_improvement(text: str) -> bool:
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
            "entirely new",
        ),
    ):
        return False
    if not _has_any(text, ("existing", "current", "already", "_route_removal")):
        return False
    return _has_any(
        text,
        (
            "refine",
            "tune",
            "adjust",
            "adapt",
            "sampling",
            "weight",
            "trigger",
            "budget",
            "candidate",
        ),
    )


def _acknowledges_existing_route_removal_variant(text: str) -> bool:
    if not _text_acknowledges_existing_route_removal(text):
        return False
    if not _has_any(
        text,
        (
            "variant",
            "extension",
            "extend",
            "zone",
            "zonal",
            "cluster",
            "clustered",
            "spatial",
            "edge",
            "edge guided",
            "route edge",
            "boundary",
            "geographic",
            "filter",
            "filtered",
            "candidate",
            "repair",
            "reinsert",
            "reinsertion",
            "schedule",
            "scheduler",
            "trigger",
            "parameter",
            "bounded",
            "sampling",
            "scoring",
            "but",
            "however",
            "while",
            "distinct from",
            "different from",
            "without claiming route removal is missing",
        ),
    ):
        return False
    span = _missing_route_removal_span_without_variant_allowance(text)
    if not span:
        return True
    return _has_any(
        span,
        (
            "variant",
            "zone",
            "zonal",
            "cluster",
            "clustered",
            "spatial",
            "geographic",
            "filter",
            "candidate",
            "edge",
            "repair",
            "schedule",
            "trigger",
            "parameter",
            "bounded",
        ),
    )


def _text_acknowledges_existing_route_removal(text: str) -> bool:
    if _has_any(
        text,
        (
            "existing route removal",
            "current route removal",
            "active route removal",
            "existing whole route removal",
            "current whole route removal",
            "active whole route removal",
            "uses route removal",
            "route removal operators",
            "already has route removal",
            "already has whole route removal",
            "already includes route removal",
            "already includes whole route removal",
            "route removal already",
            "whole route removal already",
        ),
    ):
        return True
    route_family = (
        r"(?:route removal|whole route removal|entire route removal|"
        r"route level removal|route destroy)"
    )
    return bool(
        re.search(
            r"\b(?:already|current|existing|active)\b[^.;]{0,80}\b"
            + route_family
            + r"\b",
            text,
        )
        or re.search(
            r"\b(?:destroy portfolio|operator portfolio|portfolio|scheduler|"
            r"operator list)\b[^.;]{0,80}\b(?:already|includes?|contains?|has|uses?)\b"
            r"[^.;]{0,100}\b"
            + route_family
            + r"\b",
            text,
        )
        or re.search(
            r"\b"
            + route_family
            + r"\b[^.;]{0,80}\b(?:already|exists?|existing|current|active|"
            r"present|included|wired|available)\b",
            text,
        )
    )


def _missing_route_removal_span_without_variant_allowance(text: str) -> str:
    return _first_missing_route_removal_claim_span(
        text,
        allow_existing_acknowledgement=False,
    )


def _first_missing_route_removal_claim_span(
    text: str,
    *,
    allow_existing_acknowledgement: bool = True,
) -> str:
    route_family = (
        r"(?:whole route|entire route|route level|route removal|route destroy)"
    )
    patterns = (
        r"\b(?:missing|lacks?|absent|without|does not have|does not include|"
        r"doesn't have|doesn't include)\b.{0,100}\b"
        + route_family
        + r"\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)\b",
        r"\bno\b.{0,30}\b"
        + route_family
        + r"\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)\b",
        r"\b"
        + route_family
        + r"\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)\b.{0,100}"
        r"\b(?:missing|lacks?|absent|without|no|does not have|"
        r"does not include|doesn't have|doesn't include)\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            span = text[match.start() : match.end()].strip()[:220]
            if allow_existing_acknowledgement and _span_acknowledges_existing_route_removal(
                span
            ):
                continue
            return span
    return ""
