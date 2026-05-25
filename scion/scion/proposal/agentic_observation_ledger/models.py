"""Models for APS phase-inherited observation ledgers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from scion.proposal.agentic_utils import _drop_empty_dict

LEDGER_SCHEMA_VERSION = "agentic-observation-ledger.v1"

REUSABLE_CONTEXT_TOOLS = frozenset(
    {
        "context.read_active_solver_map",
        "context.read_operator_registry",
        "context.read_algorithm_slice",
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
        "context.read_algorithm_file",
        "context.read_algorithm_symbol",
        "context.read_surface",
    }
)
ACTIVE_SOLVER_METADATA_TOOLS = frozenset(
    {
        "context.read_active_solver_map",
        "context.read_active_solver_design",
        "context.read_solver_call_graph",
        "context.list_algorithm_files",
    }
)


@dataclass(frozen=True)
class AgenticObservationLedger:
    """Compact persistent ledger envelope for phase-reusable observations."""

    session_id: str
    campaign_id: str
    branch_id: str
    observations: tuple[Mapping[str, Any], ...]
    champion_version: int | None = None
    problem_spec_hash: str | None = None
    context_policy_id: str = ""

    def to_payload(self) -> dict[str, Any]:
        from scion.proposal.agentic_observation_ledger.payloads import (
            active_fact_anchor_from_entries,
            read_receipt_from_entry,
        )

        return _drop_empty_dict(
            {
                "schema_version": LEDGER_SCHEMA_VERSION,
                "session_id": self.session_id,
                "campaign_id": self.campaign_id,
                "branch_id": self.branch_id,
                "champion_version": self.champion_version,
                "problem_spec_hash": self.problem_spec_hash,
                "context_policy_id": self.context_policy_id,
                "observation_count": len(self.observations),
                "observations": [dict(item) for item in self.observations],
                "read_receipts": [
                    read_receipt_from_entry(item) for item in self.observations
                ],
                "active_fact_anchor": active_fact_anchor_from_entries(
                    self.observations
                ),
            }
        )


__all__ = [
    "ACTIVE_SOLVER_METADATA_TOOLS",
    "AgenticObservationLedger",
    "LEDGER_SCHEMA_VERSION",
    "REUSABLE_CONTEXT_TOOLS",
]
