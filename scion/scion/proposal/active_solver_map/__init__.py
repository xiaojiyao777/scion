"""Problem-generic active solver map schema and context-tool facade."""

from __future__ import annotations

from scion.proposal.active_solver_map.facade import (
    read_active_solver_map_payload,
    read_algorithm_slice_payload,
    read_operator_registry_payload,
)
from scion.proposal.active_solver_map.models import (
    ActiveSolverEntrypoint,
    ActiveSolverMap,
    AlgorithmSliceReadResult,
    AlgorithmSliceRef,
    EditableFileRef,
    EntrypointCall,
    IntegrationPoint,
    KnownMechanismFact,
    OperatorRef,
    OperatorRegistry,
    OperatorRegistryReadResult,
    ReadReceipt,
    SchedulerIntegration,
    SourcePolicy,
    SourcePolicyReceipt,
    TelemetryField,
    UnavailableReason,
)

__all__ = [
    "ActiveSolverEntrypoint",
    "ActiveSolverMap",
    "AlgorithmSliceReadResult",
    "AlgorithmSliceRef",
    "EditableFileRef",
    "EntrypointCall",
    "IntegrationPoint",
    "KnownMechanismFact",
    "OperatorRef",
    "OperatorRegistry",
    "OperatorRegistryReadResult",
    "ReadReceipt",
    "SchedulerIntegration",
    "SourcePolicy",
    "SourcePolicyReceipt",
    "TelemetryField",
    "UnavailableReason",
    "read_active_solver_map_payload",
    "read_algorithm_slice_payload",
    "read_operator_registry_payload",
]
