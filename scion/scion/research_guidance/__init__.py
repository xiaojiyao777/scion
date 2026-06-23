"""Problem-neutral research guidance contract surface."""

from scion.research_guidance.rendering import (
    RenderedResearchGuidance,
    render_research_guidance_contract,
)
from scion.research_guidance.schema import (
    AvoidRule,
    ContinuityRequirement,
    EvidenceRequirement,
    GuidanceBlock,
    GuidanceContext,
    GuidanceVisibility,
    MeasurementGuidanceSummary,
    ProblemResearchGuidanceProvider,
    RequiredMechanism,
    ResearchGuidanceContract,
    ResearchGuidanceValidationError,
    collect_research_guidance_errors,
    expected_research_guidance_rendered_paths,
    validate_research_guidance_contract,
    validate_research_guidance_rendered_paths,
)

__all__ = [
    "AvoidRule",
    "ContinuityRequirement",
    "EvidenceRequirement",
    "GuidanceBlock",
    "GuidanceContext",
    "GuidanceVisibility",
    "MeasurementGuidanceSummary",
    "ProblemResearchGuidanceProvider",
    "RenderedResearchGuidance",
    "RequiredMechanism",
    "ResearchGuidanceContract",
    "ResearchGuidanceValidationError",
    "collect_research_guidance_errors",
    "expected_research_guidance_rendered_paths",
    "render_research_guidance_contract",
    "validate_research_guidance_contract",
    "validate_research_guidance_rendered_paths",
]
