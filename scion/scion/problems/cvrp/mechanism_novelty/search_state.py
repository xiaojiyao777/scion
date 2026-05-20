"""Search-state premise predicates for CVRP mechanism novelty."""

from __future__ import annotations

from scion.problems.cvrp.mechanism_novelty.text import _first_regex_span, _has_any


def _claims_unreachable_feasibility_crossing(text: str) -> bool:
    return bool(_unreachable_feasibility_crossing_span(text))


def _unreachable_feasibility_crossing_span(text: str) -> str:
    if not _has_any(
        text,
        (
            "feasibility crossing",
            "first feasible",
            "infeasible to feasible",
            "infeasible-to-feasible",
            "fleet violation crossing",
            "route cap violation crossing",
        ),
    ):
        return ""
    return _first_regex_span(text, _FEASIBILITY_CROSSING_PATTERNS)


_FEASIBILITY_CROSSING_PATTERNS = (
    r"\b(?:feasibility crossing|first feasible|infeasible to feasible|"
    r"infeasible-to-feasible|fleet violation crossing|route cap violation crossing)"
    r"\b.{0,120}\b(?:reset|restart|trigger|phase|switch|accept|current solution|"
    r"search state)\b",
    r"\b(?:reset|restart|trigger|phase|switch|accept|current solution|search state)"
    r"\b.{0,120}\b(?:feasibility crossing|first feasible|infeasible to feasible|"
    r"infeasible-to-feasible|fleet violation crossing|route cap violation crossing)\b",
)
