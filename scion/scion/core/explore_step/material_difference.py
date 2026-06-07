"""Material-difference requirement handling for explore proposals."""
from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import Branch, HypothesisProposal

_MATERIAL_DIFFERENCE_REQUIRED_MISSING = (
    "agent_quality_blocked:material_difference_required_missing"
)
_MATERIAL_DIFFERENCE_SIGNAL_FIELDS = frozenset(
    {
        "changed_dimension",
        "changed_dimensions",
        "dimension_delta",
        "dimension_deltas",
        "evidence_delta",
        "evidence_deltas",
        "evidence_status_delta",
        "evidence_status_deltas",
        "failure_signature_delta",
        "failure_signature_deltas",
        "intervention_type_delta",
        "intervention_type_deltas",
        "mechanism_family_delta",
        "mechanism_family_deltas",
        "signature",
        "signature_digest",
        "signature_digests",
        "surface_delta",
        "surface_deltas",
        "weak_signal_delta",
        "weak_signal_deltas",
    }
)
_MATERIAL_DIFFERENCE_METADATA_FIELD_NAMES = frozenset(
    {
        "audit",
        "audit_metadata",
        "candidate_source",
        "decision_features_excluded",
        "llm_trace_excluded",
        "metadata",
        "policy",
        "proposal_visibility_only",
        "record_digest",
        "record_id",
        "record_type",
        "required",
        "required_for",
        "required_metadata_key",
        "required_output_contract",
        "required_output_field",
        "requirement_source",
        "schema",
        "schema_version",
        "source",
        "visibility",
        "visibility_ledger",
        "visibility_status",
    }
)
_MATERIAL_DIFFERENCE_BOILERPLATE = frozenset(
    {
        "different",
        "different approach",
        "false",
        "material difference",
        "materially different",
        "new mechanism",
        "no change",
        "novel",
        "novel approach",
        "required",
        "same",
        "true",
        "unique",
        "unchanged",
        "not the same",
        "tbd",
        "unknown",
        "yes",
        "n/a",
        "none",
    }
)


def material_difference_requirement_metadata(
    branch: Branch,
    *,
    session_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return generic metadata indicating whether material_difference is required."""

    sources: tuple[tuple[str, Any], ...] = (
        (
            "branch.branch_evidence_summary",
            getattr(branch, "branch_evidence_summary", None),
        ),
        (
            "branch.last_branch_lifecycle_policy_block",
            getattr(branch, "last_branch_lifecycle_policy_block", None),
        ),
        ("proposal_session_ref", session_ref),
    )
    for source, payload in sources:
        requirement = _find_material_difference_requirement(payload)
        if requirement:
            return {"required": True, "source": source, **requirement}
    return {"required": False}


def material_difference_pre_code_block_reason(
    hypothesis: HypothesisProposal,
    branch: Branch,
    *,
    session_ref: Mapping[str, Any] | None = None,
) -> str | None:
    """Return a proposal-quality block reason before code generation, if any."""

    metadata = material_difference_requirement_metadata(branch, session_ref=session_ref)
    if not metadata.get("required"):
        return None
    if _material_difference_record_present(
        getattr(hypothesis, "material_difference", None)
    ):
        return None
    required_for = str(metadata.get("required_for") or "unspecified").strip()
    source = str(metadata.get("source") or "metadata").strip()
    return (
        f"{_MATERIAL_DIFFERENCE_REQUIRED_MISSING}: structured "
        "material_difference is required before code generation "
        f"(source={source}, required_for={required_for}). Regenerate the "
        "hypothesis with a compact material_difference record containing "
        "structural anchors such as `changed_dimensions`, "
        "`signature_digest`, or `evidence_status_delta`. Generic "
        "placeholders such as 'different approach' or 'new mechanism', and "
        "descriptive-only fields such as `differs_from` or `effect_path`, do "
        "not satisfy the requirement. Do not use raw cross-branch text, LLM "
        "rationale, trace, prompt, transcript, or repeated hypothesis prose."
    )


def _find_material_difference_requirement(
    payload: Any,
    *,
    depth: int = 0,
) -> dict[str, Any]:
    if depth > 5 or payload in (None, "", [], {}, ()):
        return {}
    if isinstance(payload, Mapping):
        requirements = (
            payload.get("material_difference_requirements")
            or payload.get("material_difference_requirement")
        )
        required_for = (
            payload.get("material_difference_required_for")
            or _material_requirement_required_for(requirements)
        )
        explicit_required = payload.get("material_difference_required") is True
        if (
            explicit_required
            or _nonempty_material_requirement(requirements)
            or required_for
        ):
            return {
                key: value
                for key, value in {
                    "required_for": required_for or "unspecified",
                    "requirements": requirements,
                }.items()
                if value not in (None, "", [], {}, ())
            }
        for value in payload.values():
            found = _find_material_difference_requirement(value, depth=depth + 1)
            if found:
                return found
    if isinstance(payload, (list, tuple)):
        for item in payload:
            found = _find_material_difference_requirement(item, depth=depth + 1)
            if found:
                return found
    return {}


def _nonempty_material_requirement(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, (list, tuple)):
        return any(_nonempty_material_requirement(item) for item in value)
    return bool(value)


def _material_requirement_required_for(value: Any) -> str:
    if isinstance(value, Mapping):
        text = str(value.get("required_for") or "").strip()
        if text:
            return text
    if isinstance(value, (list, tuple)):
        for item in value:
            text = _material_requirement_required_for(item)
            if text:
                return text
    return ""


def _material_difference_record_present(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return _material_difference_specific_signal_present(value)


def _material_difference_specific_signal_present(
    value: Any,
    *,
    depth: int = 0,
    signal_context: bool = False,
) -> bool:
    if depth > 4:
        return False
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = _material_difference_key(raw_key)
            if key in _MATERIAL_DIFFERENCE_SIGNAL_FIELDS:
                if _material_difference_specific_signal_present(
                    item,
                    depth=depth + 1,
                    signal_context=True,
                ):
                    return True
                continue
            if signal_context and not _material_difference_metadata_key(key):
                if _material_difference_specific_signal_present(
                    item,
                    depth=depth + 1,
                    signal_context=True,
                ):
                    return True
            elif not signal_context:
                if _material_difference_specific_signal_present(
                    item,
                    depth=depth + 1,
                    signal_context=False,
                ):
                    return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(
            _material_difference_specific_signal_present(
                item,
                depth=depth + 1,
                signal_context=signal_context,
            )
            for item in value
        )
    if isinstance(value, str):
        text = " ".join(value.strip().lower().split())
        return bool(
            signal_context
            and text
            and text not in _MATERIAL_DIFFERENCE_BOILERPLATE
        )
    return False


def _material_difference_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _material_difference_metadata_key(key: str) -> bool:
    if key in _MATERIAL_DIFFERENCE_METADATA_FIELD_NAMES:
        return True
    return key.endswith("_source") or key.endswith("_policy")
