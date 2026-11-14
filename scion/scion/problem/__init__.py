"""scion.problem — Problem adapter abstraction layer.

Public API for Scion core to interact with problem-specific implementations.
"""
from .contracts import (
    CheckReport,
    LowerBoundEstimate,
    ProblemAdapter,
    SolverArtifact,
)
from .loader import (
    ProblemAdapterLoadError,
    load_problem_adapter,
    load_problem_spec_v1_from_yaml,
)
from .objectives import (
    MetricComparison,
    ObjectiveComparison,
    compare_lexicographic,
)
from .providers import (
    ProblemProviderError,
    SolverDesignPromptProvider,
    resolve_solver_design_prompt_provider,
)
from .spec import (
    SUPPORTED_RESEARCH_SURFACE_KINDS,
    ObjectiveMetricSpec,
    ProblemAdapterRef,
    ProblemSpecV1,
    ResearchSurfaceAlgorithmSpec,
    ResearchSurfaceBoundsSpec,
    ResearchSurfaceEvidenceSpec,
    ResearchSurfaceInterfaceSpec,
    ResearchSurfaceMechanismTelemetrySpec,
    ResearchSurfaceNoveltySpec,
    ResearchSurfacePromptSpec,
    ResearchSurfaceReturnValueSpec,
    ResearchSurfaceSpec,
    ResearchSurfaceTargetsSpec,
)

__all__ = [
    "SUPPORTED_RESEARCH_SURFACE_KINDS",
    "CheckReport",
    "LowerBoundEstimate",
    "MetricComparison",
    "ObjectiveComparison",
    "ObjectiveMetricSpec",
    "ProblemAdapter",
    "ProblemAdapterLoadError",
    "ProblemAdapterRef",
    "ProblemProviderError",
    "ProblemSpecV1",
    "ResearchSurfaceAlgorithmSpec",
    "ResearchSurfaceBoundsSpec",
    "ResearchSurfaceEvidenceSpec",
    "ResearchSurfaceInterfaceSpec",
    "ResearchSurfaceMechanismTelemetrySpec",
    "ResearchSurfaceNoveltySpec",
    "ResearchSurfacePromptSpec",
    "ResearchSurfaceReturnValueSpec",
    "ResearchSurfaceSpec",
    "ResearchSurfaceTargetsSpec",
    "SolverArtifact",
    "SolverDesignPromptProvider",
    "compare_lexicographic",
    "load_problem_adapter",
    "load_problem_spec_v1_from_yaml",
    "resolve_solver_design_prompt_provider",
]
