"""Generic relay from problem opportunities to code-phase commitments."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from scion.opportunity.summary import redact_problem_opportunity_payload


SCHEMA_VERSION = "scion.problem_opportunity_evidence_commitment.v1"
_TEXT_CHARS = 320
_REQUIREMENT_LIMIT = 8
_SEQUENCE_LIMIT = 8


@dataclass(frozen=True)
class OpportunityRequirementCommitment:
    requirement_id: str
    mechanism_family: str = ""
    status: str = ""
    summary: str = ""
    recommended_action: str = ""
    required_observations: tuple[str, ...] = ()
    protected_cases: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return _drop_empty(
            {
                "requirement_id": self.requirement_id,
                "mechanism_family": self.mechanism_family,
                "status": self.status,
                "summary": self.summary,
                "recommended_action": self.recommended_action,
                "required_observations": list(self.required_observations),
                "protected_cases": list(self.protected_cases),
                "reason_codes": list(self.reason_codes),
            }
        )


@dataclass(frozen=True)
class OpportunityEvidenceCommitment:
    problem_family: str
    objective: str
    selected_mechanism_ids: tuple[str, ...]
    requirements: tuple[OpportunityRequirementCommitment, ...]
    source_summary_digest: str
    source_schema_version: str = "scion.problem_opportunity_summary.v1"
    schema_version: str = SCHEMA_VERSION
    proposal_visibility_only: bool = True
    decision_features_excluded: bool = True

    def to_payload(self) -> dict[str, Any]:
        return _drop_empty(
            {
                "schema_version": self.schema_version,
                "problem_family": self.problem_family,
                "objective": self.objective,
                "selected_mechanism_ids": list(self.selected_mechanism_ids),
                "source_schema_version": self.source_schema_version,
                "source_summary_digest": self.source_summary_digest,
                "requirements": [
                    requirement.to_payload() for requirement in self.requirements
                ],
                "proposal_visibility_only": self.proposal_visibility_only,
                "decision_features_excluded": self.decision_features_excluded,
                "decision_input_policy": "excluded_from_decision_features",
            }
        )


def opportunity_evidence_commitment_from_summary(
    opportunity_summary: Mapping[str, Any] | None,
    hypothesis: Any,
) -> dict[str, Any]:
    """Build a proposal-only code-phase commitment for selected requirements.

    Generic core matches only selected mechanism ids to provider-owned
    requirement records. Problem packages remain responsible for the meaning of
    requirement ids, protected cases, and observation names.
    """

    if not isinstance(opportunity_summary, Mapping):
        return {}
    redacted = redact_problem_opportunity_payload(dict(opportunity_summary))
    if not isinstance(redacted, Mapping):
        return {}
    selected_mechanisms = _mechanism_ids_from_hypothesis(hypothesis)
    if not selected_mechanisms:
        return {}
    selected = set(selected_mechanisms)
    requirements: list[OpportunityRequirementCommitment] = []
    for item in _mapping_items(redacted.get("evidence_requirements")):
        family = str(item.get("mechanism_family") or "").strip()
        if family not in selected:
            continue
        requirement_id = str(item.get("requirement_id") or "").strip()
        if not requirement_id:
            continue
        requirements.append(
            OpportunityRequirementCommitment(
                requirement_id=requirement_id,
                mechanism_family=family,
                status=str(item.get("status") or ""),
                summary=str(item.get("summary") or ""),
                recommended_action=str(item.get("recommended_action") or ""),
                required_observations=_string_tuple(item.get("required_observations")),
                protected_cases=_string_tuple(item.get("protected_cases")),
                reason_codes=_string_tuple(item.get("reason_codes")),
            )
        )
    if not requirements:
        return {}
    commitment = OpportunityEvidenceCommitment(
        problem_family=str(redacted.get("problem_family") or ""),
        objective=str(redacted.get("objective") or ""),
        selected_mechanism_ids=selected_mechanisms,
        source_schema_version=str(
            redacted.get("schema_version") or "scion.problem_opportunity_summary.v1"
        ),
        source_summary_digest=_digest(redacted),
        requirements=tuple(requirements[:_REQUIREMENT_LIMIT]),
    )
    return commitment.to_payload()


def compact_opportunity_evidence_commitment(value: Any) -> str:
    """Return bounded code-phase text for a derived opportunity commitment."""

    if not isinstance(value, Mapping):
        return ""
    payload = redact_problem_opportunity_payload(dict(value))
    if not isinstance(payload, Mapping):
        return ""
    projected = _drop_empty(
        {
            "schema_version": str(payload.get("schema_version") or SCHEMA_VERSION),
            "problem_family": _project_scalar(payload.get("problem_family")),
            "objective": _project_scalar(payload.get("objective")),
            "selected_mechanism_ids": _project_sequence(
                payload.get("selected_mechanism_ids")
            ),
            "source_schema_version": _project_scalar(
                payload.get("source_schema_version")
            ),
            "source_summary_digest": _project_scalar(
                payload.get("source_summary_digest")
            ),
            "requirements": _project_requirements(payload.get("requirements")),
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "decision_input_policy": "excluded_from_decision_features",
        }
    )
    if not projected.get("requirements"):
        return ""
    rendered = json.dumps(projected, indent=2, sort_keys=True, default=str)
    return (
        "Problem-owned opportunity evidence selected by the approved "
        "hypothesis. Use this as a code-phase checklist for implementation "
        "and telemetry/evidence planning only; it is proposal context, "
        "excluded from DecisionFeatures, and is not Protocol evidence.\n"
        f"{rendered}"
    )


def _mechanism_ids_from_hypothesis(hypothesis: Any) -> tuple[str, ...]:
    if isinstance(hypothesis, Mapping):
        changes = hypothesis.get("mechanism_changes")
    else:
        changes = getattr(hypothesis, "mechanism_changes", None)
    ids: list[str] = []
    if isinstance(changes, (list, tuple)):
        for change in changes:
            if isinstance(change, Mapping):
                mechanism_id = str(change.get("id") or "").strip()
            else:
                mechanism_id = str(getattr(change, "id", "") or "").strip()
            if mechanism_id and mechanism_id not in ids:
                ids.append(mechanism_id)
    return tuple(ids)


def _project_requirements(value: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in _mapping_items(value):
        projected = _drop_empty(
            {
                "requirement_id": _project_scalar(item.get("requirement_id")),
                "mechanism_family": _project_scalar(item.get("mechanism_family")),
                "status": _project_scalar(item.get("status")),
                "summary": _project_scalar(item.get("summary")),
                "recommended_action": _project_scalar(
                    item.get("recommended_action")
                ),
                "required_observations": _project_sequence(
                    item.get("required_observations")
                ),
                "protected_cases": _project_sequence(item.get("protected_cases")),
                "reason_codes": _project_sequence(item.get("reason_codes")),
            }
        )
        if projected:
            items.append(projected)
    return items[:_REQUIREMENT_LIMIT]


def _mapping_items(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _project_sequence(value: Any) -> list[Any]:
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        return []
    projected = [_project_scalar(item) for item in raw_items[:_SEQUENCE_LIMIT]]
    result = [item for item in projected if item not in ("", None, [], {}, ())]
    if len(raw_items) > _SEQUENCE_LIMIT:
        result.append({"omitted_item_count": len(raw_items) - _SEQUENCE_LIMIT})
    return result


def _project_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return _short_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _short_text(str(value))


def _short_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= _TEXT_CHARS:
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    head = text[:_TEXT_CHARS].rstrip()
    return f"{head} [omitted_chars={len(text) - len(head)} text_digest={digest}]"


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, (list, tuple)):
        raw_values = list(value)
    else:
        return ()
    result: list[str] = []
    for item in raw_values:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _digest(value: Any) -> str:
    rendered = json.dumps(
        redact_problem_opportunity_payload(value),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]


def _drop_empty(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in payload.items()
        if value not in ("", None, [], {}, ())
    }


__all__ = [
    "OpportunityEvidenceCommitment",
    "OpportunityRequirementCommitment",
    "compact_opportunity_evidence_commitment",
    "opportunity_evidence_commitment_from_summary",
]
