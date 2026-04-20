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
from scion.problem.objectives import (
    MetricComparison,
    ObjectiveComparison,
    compare_lexicographic,
)
from scion.problem.spec import (
    ObjectiveMetricSpec,
    ProblemAdapterRef,
    ProblemSpecV1,
)

__all__ = [
    "CheckReport",
    "LowerBoundEstimate",
    "MetricComparison",
    "ObjectiveComparison",
    "ProblemAdapter",
    "ProblemAdapterLoadError",
    "ProblemAdapterRef",
    "ProblemSpecV1",
    "ObjectiveMetricSpec",
    "SolverArtifact",
    "compare_lexicographic",
    "load_problem_adapter",
]
