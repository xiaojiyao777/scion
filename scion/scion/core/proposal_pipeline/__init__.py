"""Public facade for proposal pipeline orchestration.

The package keeps `from scion.core.proposal_pipeline import ProposalPipeline`
compatible while implementation details live in focused modules.
"""
from __future__ import annotations

from .facade import ProposalPipeline
from .protocols import (
    BranchControllerLike,
    ClassifierLike,
    CreativeLayerLike,
    HypothesisStoreLike,
    ProblemRuntimeLike,
)
__all__ = [
    "BranchControllerLike",
    "ClassifierLike",
    "CreativeLayerLike",
    "HypothesisStoreLike",
    "ProblemRuntimeLike",
    "ProposalPipeline",
]
