"""Problem-owned compact CVRP search-allocation evidence for proposals."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from scion.problems.cvrp.evidence.search_allocation import (
    build_search_allocation_evidence,
    has_search_allocation_observations,
)


class CvrpProposalMechanismEvidenceProvider:
    """Project screening runtime into proposal-only CVRP diagnostics."""

    def summarize_proposal_mechanism_evidence(
        self,
        *,
        stage: str,
        selected_surface: str | None,
        runtime_pairs: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        if stage != "screening" or selected_surface != "solver_design":
            return {}
        packet = build_search_allocation_evidence(runtime_pairs)
        return packet if has_search_allocation_observations(packet) else {}


__all__ = ["CvrpProposalMechanismEvidenceProvider"]
