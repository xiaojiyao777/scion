"""Public facade for proposal pipeline orchestration.

The package keeps `from scion.core.proposal_pipeline import ProposalPipeline`
compatible while implementation details live in focused modules.
"""
from __future__ import annotations

from .boundaries import (
    _active_problem_boundary_surfaces_for_runtime,
    _declared_solver_design_surface_names,
)
from .classification import (
    _agentic_detail_is_framework_boundary,
    _agentic_output_is_control_timeout,
    _agentic_output_is_quality_blocked,
    _agentic_primary_secondary_failures,
    _agentic_quality_block_classification,
    _agentic_rejection_constraint,
    _agentic_self_check_failure_detail,
    _bounded_agentic_failure_text,
)
from .facade import ProposalPipeline
from .protocols import (
    AgenticProposalSessionLike,
    BranchControllerLike,
    CircuitBreakerLike,
    ClassifierLike,
    CreativeLayerLike,
    HypothesisStoreLike,
    ProblemRuntimeLike,
)

__all__ = [
    "AgenticProposalSessionLike",
    "BranchControllerLike",
    "CircuitBreakerLike",
    "ClassifierLike",
    "CreativeLayerLike",
    "HypothesisStoreLike",
    "ProblemRuntimeLike",
    "ProposalPipeline",
    "_active_problem_boundary_surfaces_for_runtime",
    "_agentic_detail_is_framework_boundary",
    "_agentic_output_is_control_timeout",
    "_agentic_output_is_quality_blocked",
    "_agentic_primary_secondary_failures",
    "_agentic_quality_block_classification",
    "_agentic_rejection_constraint",
    "_agentic_self_check_failure_detail",
    "_bounded_agentic_failure_text",
    "_declared_solver_design_surface_names",
]
