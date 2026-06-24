"""Typed proposal-only opportunity summaries for problem providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from scion.measurement import MeasurementConsumerView


FORBIDDEN_KEY_FRAGMENTS = (
    "raw_pair",
    "raw_calibration",
    "pair_evidence",
    "validation_case",
    "frozen_case",
    "holdout",
    "prompt_ratio",
    "llm_text",
    "case_gap",
    "bks",
)


@dataclass(frozen=True)
class OpportunityContext:
    """Inputs supplied by problem-owned code to an opportunity provider."""

    measurement: MeasurementConsumerView | None = None
    source_payload: Mapping[str, Any] | None = None
    research_focus: Mapping[str, Any] | None = None
    postrun_reports: tuple[Mapping[str, Any], ...] = ()


class ProblemOpportunityProvider(Protocol):
    """Problem-owned provider for proposal-visible solver opportunity."""

    problem_family: str

    def build_opportunity_summary(
        self,
        context: OpportunityContext | None = None,
    ) -> "ProblemOpportunitySummary":
        """Return a typed opportunity summary."""


@dataclass(frozen=True)
class OpportunityAxis:
    axis_id: str
    metric: str = ""
    status: str = ""
    summary: str = ""
    reason_codes: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return _drop_empty(
            {
                "axis_id": self.axis_id,
                "metric": self.metric,
                "status": self.status,
                "summary": self.summary,
                "reason_codes": list(self.reason_codes),
            }
        )


@dataclass(frozen=True)
class MechanismEvidenceSummary:
    mechanism_family: str
    evidence_status: str = ""
    opportunity_status: str = ""
    effect_status: str = ""
    summary: str = ""
    recommended_action: str = ""
    reason_codes: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return _drop_empty(
            {
                "mechanism_family": self.mechanism_family,
                "evidence_status": self.evidence_status,
                "opportunity_status": self.opportunity_status,
                "effect_status": self.effect_status,
                "summary": self.summary,
                "recommended_action": self.recommended_action,
                "reason_codes": list(self.reason_codes),
            }
        )


@dataclass(frozen=True)
class ProtectedCaseSummary:
    case_id: str
    reason: str = ""
    required_evidence: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return _drop_empty(
            {
                "case_id": self.case_id,
                "reason": self.reason,
                "required_evidence": list(self.required_evidence),
            }
        )


@dataclass(frozen=True)
class AvoidedMechanismSummary:
    mechanism_family: str
    reason: str = ""

    def to_payload(self) -> dict[str, Any]:
        return _drop_empty(
            {
                "mechanism_family": self.mechanism_family,
                "reason": self.reason,
            }
        )


@dataclass(frozen=True)
class ProblemOpportunitySummary:
    problem_family: str
    objective: str
    residual_opportunity: tuple[OpportunityAxis, ...] = ()
    mechanism_evidence: tuple[MechanismEvidenceSummary, ...] = ()
    protected_cases: tuple[ProtectedCaseSummary, ...] = ()
    measurement: MeasurementConsumerView | None = None
    default_avoid: tuple[AvoidedMechanismSummary, ...] = ()
    schema_version: str = "scion.problem_opportunity_summary.v1"
    proposal_visibility_only: bool = True
    decision_features_excluded: bool = True

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "problem_family": self.problem_family,
            "objective": self.objective,
            "residual_opportunity": [
                item.to_payload() for item in self.residual_opportunity
            ],
            "mechanism_evidence": [
                item.to_payload() for item in self.mechanism_evidence
            ],
            "protected_cases": [item.to_payload() for item in self.protected_cases],
            "measurement": (
                self.measurement.to_status_payload()
                if self.measurement is not None
                else None
            ),
            "default_avoid": [item.to_payload() for item in self.default_avoid],
            "proposal_visibility_only": self.proposal_visibility_only,
            "decision_features_excluded": self.decision_features_excluded,
            "decision_input_policy": "excluded_from_decision_features",
        }
        return redact_problem_opportunity_payload(_drop_empty(payload))


def redact_problem_opportunity_payload(value: Any) -> Any:
    """Drop raw or holdout-only fields from a proposal-visible payload."""

    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _forbidden_key(key_text):
                continue
            child = redact_problem_opportunity_payload(item)
            if child not in ("", None, [], {}, ()):
                redacted[key_text] = child
        return redacted
    if isinstance(value, (list, tuple)):
        return [
            child
            for item in value
            for child in [redact_problem_opportunity_payload(item)]
            if child not in ("", None, [], {}, ())
        ]
    return value


def _forbidden_key(key: str) -> bool:
    normalized = key.lower()
    return any(fragment in normalized for fragment in FORBIDDEN_KEY_FRAGMENTS)


def _drop_empty(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in ("", None, [], {}, ())
    }
