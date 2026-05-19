"""Problem-owned provider access for solver-design smoke."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from scion.problem.providers import resolve_solver_design_smoke_provider

if TYPE_CHECKING:
    from scion.proposal.tools import ProposalToolContext
else:
    ProposalToolContext = Any


def _solver_design_smoke_provider(context: ProposalToolContext) -> Any | None:
    return resolve_solver_design_smoke_provider(
        problem_spec=getattr(context, "problem_spec", None),
        adapter=getattr(context, "adapter", None),
    )
