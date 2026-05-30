from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _has_any
from scion.problems.cvrp.mechanism_novelty.destroy_repair.shared import (
    _mentions_route_removal,
    _span_acknowledges_existing_route_removal,
    _span_negates_missing_route_removal_claim,
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
            "reuse",
            "route reuse",
            "route pool",
            "route-pool",
            "recombination",
            "recombine",
            "cross incumbent",
            "cross-incumbent",
            "elite route",
            "but",
            "however",
            "while",
            "distinct from",
            "different from",
            "without claiming route removal is missing",
            "does not claim whole route destroy is missing",
        ),
    ):
        return False
    span = _missing_route_removal_span_without_variant_allowance(text)
    if not span:
        return True
    if _span_negates_missing_route_removal_claim(span):
        return True
    if _span_absence_referent_is_route_reuse_variant(span):
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
            "reuse",
            "route pool",
            "route-pool",
            "recombination",
            "cross incumbent",
            "cross-incumbent",
            "elite route",
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
        r"\b(?:missing|lacks?|absent|does not have|does not include|"
        r"doesn't have|doesn't include)\b.{0,100}\b"
        + route_family
        + r"\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)\b",
        r"\bno\b.{0,30}\b"
        + route_family
        + r"\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)\b",
        r"\b"
        + route_family
        + r"\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)\b.{0,100}"
        r"\b(?:missing|lacks?|absent|no|does not have|"
        r"does not include|doesn't have|doesn't include)\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            span = text[match.start() : match.end()].strip()[:220]
            if _route_absence_window_is_negated(text, match.start(), match.end()):
                continue
            if _span_negates_missing_route_removal_claim(span):
                continue
            if _span_absence_referent_is_route_reuse_variant(span):
                continue
            if allow_existing_acknowledgement and _span_acknowledges_existing_route_removal(
                span
            ):
                continue
            return span
    return ""


def _route_absence_window_is_negated(text: str, start: int, end: int) -> bool:
    window_start = max(0, start - 120)
    window_end = min(len(text), end + 180)
    window = text[window_start:window_end].replace("-", " ")
    route_family = (
        r"(?:_route_removal|route removal|whole route removal|whole route "
        r"destroy|entire route removal|route level removal|route destroy)"
    )
    absence = r"(?:missing|absent|lacking|lacks?|without|no)"
    return bool(
        re.search(
            r"\b(?:this\s+is\s+)?(?:not|is not|isn't)\s+"
            r"(?:a\s+)?"
            + absence
            + r"\b.{0,160}\b"
            + route_family
            + r"\b",
            window,
        )
        or re.search(
            r"\b(?:does not|doesn't|do not|don't)\s+"
            r"(?:claim|assert|premise)\b.{0,140}\b"
            + route_family
            + r"\b.{0,80}\b(?:is|are)?\s*"
            + absence
            + r"\b",
            window,
        )
        or re.search(
            r"\bnot\s+(?:a\s+)?claim\b.{0,120}\b"
            + route_family
            + r"\b.{0,80}\b(?:is|are)?\s*"
            + absence
            + r"\b",
            window,
        )
        or re.search(
            r"\bnot\s+adding\b.{0,120}\b"
            + route_family
            + r"\b.{0,80}\b(?:itself|as\s+(?:a\s+)?new|newly)\b",
            window,
        )
    )


def _span_absence_referent_is_route_reuse_variant(span: str) -> bool:
    text = str(span or "").replace("-", " ").lower()
    if not _has_any(
        text,
        (
            "cross incumbent route reuse",
            "cross incumbent",
            "route reuse",
            "route pool",
            "elite route",
            "route fragment",
            "recombination",
            "recombine",
        ),
    ):
        return False
    if not _has_any(text, ("absent", "missing", "lacks", "lack ")):
        return False
    return bool(
        _has_any(
            text,
            (
                "already has route removal",
                "has route removal",
                "route removal premise",
                "existing route removal",
                "current route removal",
                "_route_removal",
            ),
        )
        or _span_negates_missing_route_removal_claim(span)
    )
