"""scion.problem — Problem adapter abstraction layer.

Public API for Scion core to interact with problem-specific implementations.
"""
from scion.problem.contracts import (
    CheckReport,
    LowerBoundEstimate,
    ProblemAdapter,
    SolverArtifact,
)
from scion.problem.loader import ProblemAdapterLoadError, load_problem_adapter
from scion.problem.bridge import (
    ProblemSpecBridge,
    bridge_problem_spec_v1,
    legacy_problem_spec_from_v1,
)
from scion.problem.objectives import (
    MetricComparison,
    ObjectiveComparison,
    compare_lexicographic,
)
from scion.problem.spec import (
    ObjectiveMetricSpec,
    ProblemAdapterRef,
    ProblemSpecV1,
    ResearchSurfaceSpec,
)

__all__ = [
    "CheckReport",
    "LowerBoundEstimate",
    "MetricComparison",
    "ObjectiveComparison",
    "ProblemAdapter",
    "ProblemAdapterLoadError",
    "ProblemAdapterRef",
    "ProblemSpecBridge",
    "ProblemSpecV1",
    "ResearchSurfaceSpec",
    "ObjectiveMetricSpec",
    "SolverArtifact",
    "compare_lexicographic",
    "bridge_problem_spec_v1",
    "legacy_problem_spec_from_v1",
    "load_problem_adapter",
]
