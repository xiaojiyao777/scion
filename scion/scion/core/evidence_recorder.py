"""Backward-compatible facade for campaign evidence recording.

Implementation lives under :mod:`scion.core.evidence_recording` so the legacy
module path remains stable while the production code is auditable in smaller
modules.
"""
from __future__ import annotations

from scion.core.evidence_recording.artifact_refs import (
    _extract_protocol_runtime_stats,
    _extract_runtime_guard_evidence,
    _in_flight_protocol_snapshot,
    _read_partial_metrics_snapshot,
    _screening_pair_counts,
    _screening_rate_fields,
    _serialize_verification_checks,
)
from scion.core.evidence_recording.common import (
    StateProvider,
    _drop_empty_summary_items,
    _drop_none,
    _optional_int,
    _stage_value,
)
from scion.core.evidence_recording.failure_summary import (
    _contract_not_run_reason,
    _default_final_evidence_closure_refs,
    _failure_category_for_stage,
    _primary_failure_attribution,
    _proposal_session_failure_observation,
    _same_failure_observation,
    _secondary_failure_observations,
)
from scion.core.evidence_recording.recorder import EvidenceRecorder

__all__ = [
    "EvidenceRecorder",
    "StateProvider",
    "_contract_not_run_reason",
    "_default_final_evidence_closure_refs",
    "_drop_empty_summary_items",
    "_drop_none",
    "_extract_protocol_runtime_stats",
    "_extract_runtime_guard_evidence",
    "_failure_category_for_stage",
    "_in_flight_protocol_snapshot",
    "_optional_int",
    "_primary_failure_attribution",
    "_proposal_session_failure_observation",
    "_read_partial_metrics_snapshot",
    "_same_failure_observation",
    "_screening_pair_counts",
    "_screening_rate_fields",
    "_secondary_failure_observations",
    "_serialize_verification_checks",
    "_stage_value",
]
