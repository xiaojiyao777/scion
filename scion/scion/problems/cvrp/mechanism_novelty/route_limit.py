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

_ROUTE_LIMIT_CONTRADICTION_PATTERNS = (
    r"\bconstruction\b.{0,140}\b(?:more routes than|route limit excess|excess routes|positive fleet violation|nonzero fleet violation)",
    r"\b(?:more routes than|exceeds? route limit|route limit excess|excess routes)",
    r"\blen\s*\(\s*routes\s*\)\s*>\s*(?:route limit|allowed routes|max routes)",
    r"\broute count\b.{0,80}\b(?:exceeds?|above|over)\b.{0,40}\b(?:route limit|allowed routes|max routes)\b",
    r"\b(?:route limit|allowed routes|max routes)\b.{0,80}\b(?:exceeded|excess|violat(?:e|es|ing|ion))\b",
    r"\broutes?\b.{0,40}\bexceeds?\b.{0,40}\b(?:route limit|allowed routes|max routes)\b",
    r"\bpositive fleet violation\b",
    r"\b(?:nonzero|non zero) fleet violation\b",
    r"\bfleet violation\s*(?:=|:|>)\s*[1-9]",
    r"\bfleet violation deficit\b",
    r"\bleav(?:e|es|ing)\b.{0,80}\b(?:positive|nonzero|non zero)?\s*fleet violation\b.{0,60}\brepair\b",
    r"\b(?:positive|nonzero|non zero)\s+fleet violation\b.{0,80}\b(?:repair|recover|reduce|eliminate|zero out)\b",
    r"\bfleet violation\s*(?:=|:|>)\s*[1-9]\b.{0,80}\b(?:repair|recover|reduce|eliminate|zero out)\b",
    r"\b(?:repair|recover|reduce|eliminate|zero out)\s+(?:positive|nonzero|non zero)\s+fleet violation\b",
    r"\bcurrent search state\b.{0,100}\b(?:route cap violating|route limit excess|positive fleet violation)\b",
    r"\b(?:route cap violating|route limit excess|positive fleet violation)\b.{0,100}\bcurrent search state\b",
    r"\b(?:current|baseline|default|active|existing)\b.{0,100}\b(?:accepts?|allows?|permits?|uses)\b.{0,80}\binfeasible(?: current)? states?\b",
    r"\binfeasible(?: current)? states?\b.{0,100}\b(?:current|baseline|default|active|existing)\b",
    (
        r"\binfeasible(?: to | 2 |-)feasible\b.{0,100}\b"
        r"(?:fleet violation|route limit|route count)"
    ),
    (
        r"\b(?:fleet violation|route limit|route count)\b.{0,100}"
        r"\binfeasible(?: to | 2 |-)feasible\b"
    ),
    r"\bdefault\b.{0,100}\b(?:positive fleet violation|route limit excess|route cap violating|fleet violation repair)\b",
    r"\bdefault\b.{0,100}\binfeasible(?: current)? states?\b",
)

_FORBIDDEN_ROUTE_LIMIT_PHRASE = (
    r"(?:more routes than|route limit excess|excess routes|"
    r"routes?\s+exceeds?\s+(?:route limit|allowed routes|max routes)|"
    r"route[- ]?cap violating|positive fleet violation|"
    r"nonzero fleet violation|non zero fleet violation|"
    r"infeasible(?: current)? states?|"
    r"fleet violation\s*(?:=|:|>)\s*[1-9]|"
    r"len\s*\(\s*routes\s*\)\s*>\s*"
    r"(?:route limit|allowed routes|max routes))"
)

_CURRENT_FORBIDDEN_STATE_PATTERNS = (
    r"\b(?:current|baseline|default|active|existing)\b.{0,100}"
    rf"\b{_FORBIDDEN_ROUTE_LIMIT_PHRASE}\b",
    rf"\b{_FORBIDDEN_ROUTE_LIMIT_PHRASE}\b.{0,100}"
    r"\b(?:current|baseline|default|active|existing)\b",
)


def _claims_unproven_route_limit_or_fleet_repair(text: str) -> bool:
    if _route_limit_or_feasibility_guard_variant(text):
        return False
    if (
        _protects_route_limit_as_constraint(text)
        and not _has_explicit_positive_route_limit_premise(text)
    ):
        return False
    return bool(_route_limit_or_fleet_repair_span(text))


def _route_limit_or_fleet_repair_span(text: str) -> str:
    return _first_unprotected_regex_span(text, _ROUTE_LIMIT_CONTRADICTION_PATTERNS)


def _protects_route_limit_as_constraint(text: str) -> bool:
    protective_patterns = (
        r"\bpreserv(?:e|es|ing)\b.{0,80}\bfleet violation\b",
        r"\bfleet violation\b.{0,80}\b(?:remain|remains|stays|stay)\b.{0,20}\bzero\b",
        r"\bwithout increasing\b.{0,60}\bfleet violation\b",
        r"\b(?:capacity|route) feasibility guard\b",
        r"\bfeasibility (?:guard|filter|check|constraint)\b",
        r"\broute[- ]?limit[- ]?aware\b",
        r"\broute[- ]?cap\b.{0,60}\b(?:guard|filter|reject|skip|avoid|prevent)\b",
        r"\brepair ordering\b",
        r"\broute count\b.{0,80}\bprotected constraint\b",
        r"\bfleet violation\b.{0,80}\bprotected objective\b",
        rf"\b(?:rather than|instead of)\s+(?:accepting|allowing|using|relying on)\b"
        rf".{{0,60}}\b{_FORBIDDEN_ROUTE_LIMIT_PHRASE}\b",
        rf"\bavoid(?:s|ing)?\s+(?:accepting|allowing|using)?\b"
        rf".{{0,60}}\b{_FORBIDDEN_ROUTE_LIMIT_PHRASE}\b",
        rf"\b(?:avoid|prevent|reject|skip|disallow)\b.{{0,80}}"
        rf"\b{_FORBIDDEN_ROUTE_LIMIT_PHRASE}\b",
        r"\bcandidate routes?\b.{0,40}\bexceeds?\b.{0,40}"
        r"\b(?:route limit|allowed routes|max routes)\b.{0,40}"
        r"\b(?:fail|fails|reject|rejects|skip|skips|disallow|disallows)\b",
    )
    return any(re.search(pattern, text) for pattern in protective_patterns)


def _route_limit_or_feasibility_guard_variant(text: str) -> bool:
    guarded_patterns = (
        r"\b(?:avoid|prevent|reject|skip|guard against|filter out)\b.{0,100}"
        r"\b(?:more routes than|route limit excess|excess routes|route[- ]?cap violating|positive fleet violation|nonzero fleet violation|infeasible(?: current)? states?)\b",
        r"\b(?:avoid|avoids|avoiding|prevent|prevents|preventing|reject|rejects|rejecting|skip|skips|skipping|disallow|disallows|disallowing)\b.{0,100}"
        r"\b(?:accepting|allowing|using)?\b.{0,40}"
        r"\b(?:more routes than|route limit excess|excess routes|route[- ]?cap violating|positive fleet violation|nonzero fleet violation|infeasible(?: current)? states?)\b",
        r"\b(?:rather than|instead of)\s+(?:accepting|allowing|using|relying on)\b.{0,100}"
        r"\b(?:more routes than|route limit excess|excess routes|route[- ]?cap violating|positive fleet violation|nonzero fleet violation|infeasible(?: current)? states?)\b",
        r"\b(?:more routes than|route limit excess|excess routes|route[- ]?cap violating|positive fleet violation|nonzero fleet violation)\b.{0,100}"
        r"\b(?:avoid|prevent|reject|skip|guard|filter|not produce|without producing|without increasing)\b",
        r"\b(?:more routes than|route limit excess|excess routes|route[- ]?cap violating|positive fleet violation|nonzero fleet violation)\b.{0,100}"
        r"\b(?:rejected|skipped|disallowed|prevented|avoided)\b",
        r"\bcandidate routes?\b.{0,40}\bexceeds?\b.{0,40}"
        r"\b(?:route limit|allowed routes|max routes)\b.{0,40}"
        r"\b(?:fail|fails|reject|rejects|skip|skips|disallow|disallows)\b",
        r"\b(?:feasible|feasibility|capacity-compatible|route[- ]?limit[- ]?aware)\b.{0,120}"
        r"\b(?:variant|filter|guard|check|merge|repair|destroy|operator)\b",
    )
    if not any(re.search(pattern, text) for pattern in guarded_patterns):
        return False
    return not _has_current_or_default_forbidden_state_claim(text)


def _has_explicit_positive_route_limit_premise(text: str) -> bool:
    positive_patterns = (
        r"\b(?:positive|nonzero|non zero)\s+fleet violation\b",
        r"\bfleet violation\s*(?:=|:|>)\s*[1-9]",
        r"\b(?:more routes than|route limit excess|excess routes)\b",
        r"\broutes?\b.{0,40}\bexceeds?\b.{0,40}\b(?:route limit|allowed routes|max routes)\b",
        r"\binfeasible(?: current)? states?\b",
        r"\blen\s*\(\s*routes\s*\)\s*>\s*(?:route limit|allowed routes|max routes)",
    )
    for pattern in positive_patterns:
        for match in re.finditer(pattern, text):
            if not _span_is_explicitly_rejected_premise(text, match.start(), match.end()):
                return True
    return False


def _first_unprotected_regex_span(
    text: str,
    patterns: Sequence[str],
    *,
    max_chars: int = 220,
) -> str:
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            if _span_is_explicitly_rejected_premise(text, match.start(), match.end()):
                continue
            return text[match.start() : match.end()].strip()[:max_chars]
    return ""


def _has_current_or_default_forbidden_state_claim(text: str) -> bool:
    for pattern in _CURRENT_FORBIDDEN_STATE_PATTERNS:
        for match in re.finditer(pattern, text):
            if not _span_is_explicitly_rejected_premise(text, match.start(), match.end()):
                return True
    return False


def _span_is_explicitly_rejected_premise(text: str, start: int, end: int) -> bool:
    window_start = max(0, start - 120)
    window_end = min(len(text), end + 120)
    window = text[window_start:window_end]
    phrase = _FORBIDDEN_ROUTE_LIMIT_PHRASE
    rejected_patterns = (
        rf"\b(?:rather than|instead of)\s+"
        rf"(?:accepting|allowing|using|relying on|depending on)\b"
        rf".{{0,80}}\b{phrase}\b",
        rf"\bavoid(?:s|ing)?\s+"
        rf"(?:accepting|allowing|using|relying on)?\b"
        rf".{{0,80}}\b{phrase}\b",
        rf"\b(?:avoid|prevent|reject|skip|disallow|guard against|filter out)\b"
        rf".{{0,100}}\b{phrase}\b",
        rf"\bwithout\s+"
        rf"(?:accepting|allowing|producing|creating|increasing)\b"
        rf".{{0,80}}\b{phrase}\b",
        rf"\b{phrase}\b.{{0,100}}"
        rf"\b(?:rejected|skipped|disallowed|prevented|avoided|filtered out)\b",
        rf"\bno\s+(?:accepted|allowed|produced|created)?\b"
        rf".{{0,60}}\b{phrase}\b",
    )
    return any(re.search(pattern, window) for pattern in rejected_patterns)


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
    "_route_limit_or_fleet_repair_span",
]
