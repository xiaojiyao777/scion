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
from scion.problem.providers import (
    ProblemProviderError,
    SolverDesignPromptProvider,
    SolverDesignSmokeProvider,
    resolve_solver_design_prompt_provider,
    resolve_solver_design_smoke_provider,
)
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
    SUPPORTED_RESEARCH_SURFACE_KINDS,
)

__all__ = [
    "CheckReport",
    "LowerBoundEstimate",
    "MetricComparison",
    "ObjectiveComparison",
    "ProblemAdapter",
    "ProblemAdapterLoadError",
    "ProblemAdapterRef",
    "ProblemProviderError",
    "ProblemSpecBridge",
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
    "SUPPORTED_RESEARCH_SURFACE_KINDS",
    "SolverDesignPromptProvider",
    "SolverDesignSmokeProvider",
    "ObjectiveMetricSpec",
    "SolverArtifact",
    "compare_lexicographic",
    "bridge_problem_spec_v1",
    "legacy_problem_spec_from_v1",
    "load_problem_adapter",
    "resolve_solver_design_prompt_provider",
    "resolve_solver_design_smoke_provider",
]
