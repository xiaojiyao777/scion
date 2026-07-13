"""Backward-compatible facade for explore-step execution."""
from __future__ import annotations

from scion.core.explore_step.common import (
    _AGENT_QUALITY_BLOCKED,
    _ALGORITHM_SMOKE_FAILURE,
    _PROPOSAL_ACTIVATION_DIAGNOSTIC,
    _PROPOSAL_PREMISE_CONTRADICTED,
    _VerificationOutcome,
    _agent_quality_failure_detail,
    _is_agent_quality_blocked_detail,
    _is_candidate_scoped_heavy_failure,
    _proposal_failure_hypothesis,
    _proposal_failure_reason,
    _proposal_failure_stage,
    _proposal_session_ref_failure_code,
    _proposal_session_ref_is_agent_quality_blocked,
    _proposal_session_ref_primary_failure,
    _surface_for_hypothesis,
)
from scion.core.explore_step.pipeline import ExploreStepPipeline
from scion.core.explore_step.verification import build_verification_detail

__all__ = [
    "ExploreStepPipeline",
    "build_verification_detail",
    "_AGENT_QUALITY_BLOCKED",
    "_ALGORITHM_SMOKE_FAILURE",
    "_PROPOSAL_ACTIVATION_DIAGNOSTIC",
    "_PROPOSAL_PREMISE_CONTRADICTED",
    "_VerificationOutcome",
    "_agent_quality_failure_detail",
    "_is_agent_quality_blocked_detail",
    "_is_candidate_scoped_heavy_failure",
    "_proposal_failure_hypothesis",
    "_proposal_failure_reason",
    "_proposal_failure_stage",
    "_proposal_session_ref_failure_code",
    "_proposal_session_ref_is_agent_quality_blocked",
    "_proposal_session_ref_primary_failure",
    "_surface_for_hypothesis",
]
