"""Problem-owned opportunity summary contracts."""

from scion.opportunity.commitment import (
    MANIFEST_SUMMARY_SCHEMA_VERSION,
    OpportunityEvidenceCommitment,
    OpportunityRequirementCommitment,
    compact_opportunity_evidence_commitment,
    opportunity_evidence_commitment_from_summary,
    opportunity_evidence_commitment_manifest_summary,
)
from scion.opportunity.prompt_projection import compact_problem_opportunity_summary
from scion.opportunity.summary import (
    AvoidedMechanismSummary,
    MechanismEvidenceSummary,
    OpportunityAxis,
    OpportunityContext,
    OpportunityEvidenceRequirement,
    ProblemOpportunityProvider,
    ProblemOpportunitySummary,
    ProtectedCaseSummary,
    redact_problem_opportunity_payload,
)

__all__ = [
    "AvoidedMechanismSummary",
    "compact_opportunity_evidence_commitment",
    "compact_problem_opportunity_summary",
    "MANIFEST_SUMMARY_SCHEMA_VERSION",
    "MechanismEvidenceSummary",
    "OpportunityAxis",
    "OpportunityContext",
    "OpportunityEvidenceCommitment",
    "OpportunityEvidenceRequirement",
    "OpportunityRequirementCommitment",
    "ProblemOpportunityProvider",
    "ProblemOpportunitySummary",
    "ProtectedCaseSummary",
    "opportunity_evidence_commitment_from_summary",
    "opportunity_evidence_commitment_manifest_summary",
    "redact_problem_opportunity_payload",
]
