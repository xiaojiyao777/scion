"""Problem-owned postrun summary provider contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class ProblemPostrunReviewContext:
    """Report-only inputs supplied to problem-owned postrun summaries."""

    inventory: Mapping[str, Any]
    protocol_accounting_summary: Mapping[str, Any]
    measurement_effect_summary: Mapping[str, Any]
    runtime_feedback_summary: Mapping[str, Any]
    failure_taxonomy_summary: Mapping[str, Any]
    research_continuity_summary: Mapping[str, Any]
    prompt_context_visibility_summary: Mapping[str, Any] = field(default_factory=dict)
    proposal_trajectory_manifests: Sequence[Mapping[str, Any]] = ()


class ProblemPostrunSummaryProvider(Protocol):
    """Problem-owned builder for legacy-compatible postrun summary payloads."""

    problem_family: str

    def build_summaries(
        self,
        context: ProblemPostrunReviewContext,
    ) -> Mapping[str, Mapping[str, Any]]:
        """Return summary payloads keyed by their legacy analysis-brief field."""
