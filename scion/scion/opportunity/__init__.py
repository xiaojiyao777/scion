"""Problem-owned opportunity summary contracts."""

from scion.opportunity.summary import (
    AvoidedMechanismSummary,
    MechanismEvidenceSummary,
    OpportunityAxis,
    OpportunityContext,
    ProblemOpportunityProvider,
    ProblemOpportunitySummary,
    ProtectedCaseSummary,
    redact_problem_opportunity_payload,
)
from scion.opportunity.prompt_projection import compact_problem_opportunity_summary

__all__ = [
    "AvoidedMechanismSummary",
    "compact_problem_opportunity_summary",
    "MechanismEvidenceSummary",
    "OpportunityAxis",
    "OpportunityContext",
    "ProblemOpportunityProvider",
    "ProblemOpportunitySummary",
    "ProtectedCaseSummary",
    "redact_problem_opportunity_payload",
]
