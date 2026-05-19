"""Search-state premise predicates for CVRP mechanism novelty."""

from __future__ import annotations

from scion.problems.cvrp.mechanism_novelty.text import _has_any


def _claims_unreachable_feasibility_crossing(text: str) -> bool:
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
        return False
    return _has_any(
        text,
        (
            "reset",
            "restart",
            "trigger",
            "phase",
            "switch",
            "accept",
            "current solution",
            "search state",
        ),
    )
