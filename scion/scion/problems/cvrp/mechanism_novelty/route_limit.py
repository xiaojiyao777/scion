"""Route-limit and fleet-violation premise predicates for CVRP novelty."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from scion.proposal.tools import ProposalObservation

from scion.problems.cvrp.mechanism_novelty.text import _has_any

_RUNTIME_EVIDENCE_TOOLS = frozenset(
    {
        "feedback.query_runtime",
        "feedback.query_screening",
        "proposal.algorithm_smoke",
        "algorithm_smoke",
    }
)


def _claims_unproven_route_limit_or_fleet_repair(text: str) -> bool:
    if _has_any(
        text,
        (
            "construction route merge",
            "construction route merging",
            "route merge post construction",
            "route merging post construction",
            "route merge after construction",
            "route merging after construction",
        ),
    ):
        return True
    patterns = (
        r"\bconstruction\b.{0,140}\b(?:more routes than|route limit excess|excess routes|positive fleet violation|nonzero fleet violation)",
        r"\b(?:more routes than|exceeds? route limit|route limit excess|excess routes)",
        r"\blen\s*\(\s*routes\s*\)\s*>\s*(?:route limit|allowed routes|max routes)",
        r"\broute count\b.{0,80}\b(?:exceeds?|above|over)\b.{0,40}\b(?:route limit|allowed routes|max routes)\b",
        r"\b(?:route limit|allowed routes|max routes)\b.{0,80}\b(?:exceeded|excess|violat(?:e|es|ing|ion))\b",
        r"\bpositive fleet violation\b",
        r"\b(?:nonzero|non zero) fleet violation\b",
        r"\bfleet violation\s*(?:=|:|>)\s*[1-9]",
        r"\bfleet violation deficit\b",
        r"\bleav(?:e|es|ing)\b.{0,80}\bfleet violation\b.{0,60}\brepair\b",
        r"\bfleet violation\b.{0,80}\b(?:repair|recover|reduce|eliminate|zero out)\b",
        r"\b(?:repair|recover|reduce|eliminate|zero out)\s+(?:positive|nonzero|non zero)?\s*fleet violation\b",
        r"\bcurrent search state\b.{0,100}\b(?:route cap violating|route limit excess|positive fleet violation)\b",
        r"\b(?:route cap violating|route limit excess|positive fleet violation)\b.{0,100}\bcurrent search state\b",
        (
            r"\binfeasible(?: to | 2 |-)feasible\b.{0,100}\b"
            r"(?:fleet violation|route limit|route count)"
        ),
        (
            r"\b(?:fleet violation|route limit|route count)\b.{0,100}"
            r"\binfeasible(?: to | 2 |-)feasible\b"
        ),
        r"\bdefault\b.{0,100}\b(?:positive fleet violation|route limit excess|route cap violating|fleet violation repair)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _has_explicit_route_limit_runtime_evidence(
    observations: Sequence[ProposalObservation],
    *,
    context: Any | None = None,
) -> bool:
    for observation in observations:
        if observation.is_error or observation.tool_name not in _RUNTIME_EVIDENCE_TOOLS:
            continue
        if _payload_has_positive_route_limit_signal(observation.structured_payload):
            return True
    return _context_has_positive_route_limit_signal(context)


def _context_has_positive_route_limit_signal(context: Any | None) -> bool:
    if context is None:
        return False
    for step in getattr(context, "step_history", ()) or ():
        protocol = getattr(step, "protocol_result", None)
        if protocol is None:
            continue
        for value in (
            getattr(protocol, "candidate_surface_runtime_summary", None),
            getattr(protocol, "candidate_first_runtime_failure", None),
            getattr(protocol, "exposed_summary", None),
        ):
            if _payload_has_positive_route_limit_signal(value):
                return True
    return False


def _payload_has_positive_route_limit_signal(value: Any, path: str = "") -> bool:
    if isinstance(value, Mapping):
        return any(
            _payload_has_positive_route_limit_signal(
                child,
                f"{path}.{key}" if path else str(key),
            )
            for key, child in value.items()
        )
    if isinstance(value, (list, tuple, set)):
        return any(
            _payload_has_positive_route_limit_signal(child, path) for child in value
        )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        path_text = path.lower().replace("_", " ")
        return float(value) > 0.0 and _has_any(
            f" {path_text} ",
            (
                " fleet violation ",
                " route limit excess ",
                " route excess ",
                " excess routes ",
            ),
        )
    if isinstance(value, str):
        return _text_has_positive_route_limit_signal(value)
    return False


def _text_has_positive_route_limit_signal(value: str) -> bool:
    text = str(value or "").lower().replace("_", " ")
    text = re.sub(r"[-/]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    if re.search(r"\bfleet violation\s*(?:=|:|>|positive|nonzero|non zero)\s*[1-9]", text):
        return True
    return any(
        re.search(pattern, text)
        for pattern in (
            r"\bfleet violation\b.{0,40}\b(?:positive|nonzero|non zero|observed)",
            r"\b(?:route limit|route count)\b.{0,60}\b(?:excess|exceeded|above|positive)",
            r"\blen\s*\(\s*routes\s*\)\s*>\s*(?:route limit|allowed routes|max routes)",
        )
    )


__all__ = [
    "_claims_unproven_route_limit_or_fleet_repair",
    "_has_explicit_route_limit_runtime_evidence",
]
