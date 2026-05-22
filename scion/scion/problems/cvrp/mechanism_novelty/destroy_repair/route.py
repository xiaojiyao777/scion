from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _first_regex_span, _has_any
from scion.problems.cvrp.mechanism_novelty.destroy_repair.shared import (
    _mentions_route_removal,
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
    if _describes_existing_route_removal_improvement(text):
        return ""
    return _first_regex_span(
        text,
        (
            r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
            r"doesn't have|doesn't include)\b.{0,100}\b(?:whole route|"
            r"entire route|route level|route removal|route destroy)"
            r"\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)\b",
            r"\b(?:whole route|entire route|route level|route removal|"
            r"route destroy)\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)"
            r"\b.{0,100}\b(?:missing|lacks?|absent|without|no|does not have|"
            r"does not include|doesn't have|doesn't include)\b",
        ),
    )

def _duplicates_route_removal(text: str) -> bool:
    if not _mentions_route_removal(text):
        return False
    if (
        _targets_contiguous_segment_destroy_not_whole_route_removal(text)
        or _targets_perturbation_or_restart_not_removal_family(text)
    ):
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
