"""Branch-lesson usage requirement handling for explore proposals."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

from scion.core.models import Branch, HypothesisProposal, mechanism_changes

BRANCH_LESSON_USAGE_REQUIREMENT_SCHEMA = "branch_lesson_usage_requirement.v1"
BRANCH_LESSON_RECORD_SCHEMA = "branch_lesson.v1"
BRANCH_LESSON_USAGE_REPORT_PROJECTION_SCHEMA = (
    "branch_lesson_usage_report_projection.v1"
)

_BRANCH_LESSON_USAGE_REQUIRED_MISSING = (
    "agent_quality_blocked:branch_lesson_usage_required_missing"
)
_BRANCH_LESSON_USAGE_METADATA_ONLY = (
    "agent_quality_blocked:branch_lesson_usage_metadata_only"
)
_BRANCH_LESSON_USAGE_LINKAGE_UNRECOGNIZED = (
    "agent_quality_blocked:branch_lesson_usage_linkage_unrecognized"
)
_BRANCH_LESSON_USAGE_SEMANTIC_MISMATCH = (
    "agent_quality_blocked:branch_lesson_usage_semantic_mismatch"
)
_BRANCH_LESSON_REQUIREMENT_RECORD_TYPE = "branch_lesson_usage_requirement"
_BRANCH_LESSON_REQUIREMENT_PREFIX = "branch_lesson_usage_requirement"
_ACTIVE_REQUIRED_FOR = frozenset(
    {
        "clean_fork_new_branch",
        "sibling_nearby_attempt",
        "same_branch_refinement",
    }
)
_STRICT_REQUIRED_FOR = frozenset(
    {
        "clean_fork_new_branch",
        "sibling_nearby_attempt",
    }
)
_HARD_PRE_CODE_REQUIRED_FOR = _STRICT_REQUIRED_FOR
_LESSON_APPLICATION_FIELDS = frozenset(
    {
        "borrowed_lessons",
        "avoided_lessons",
        "contrasted_lessons",
    }
)
_LESSON_REJECTION_FIELDS = frozenset(
    {
        "rejected_lessons",
        "rejected_weak_positive_lessons",
    }
)
_WEAK_POSITIVE_APPLICATION_FIELDS = frozenset(
    {
        "borrowed_lessons",
        "preserved_same_branch_lesson",
    }
)
_CHANGED_DIMENSION_FIELDS = frozenset(
    {
        "changed_dimension",
        "changed_dimension_id",
        "changed_dimension_ids",
        "changed_dimensions",
        "changed_generic_dimension",
        "changed_generic_dimensions",
        "contrast_dimension",
        "contrast_dimension_id",
        "contrast_dimension_ids",
        "contrast_dimensions",
        "delta_dimension",
        "delta_dimensions",
        "dimension_delta",
        "dimension_deltas",
        "generic_dimension_delta",
        "generic_dimension_deltas",
    }
)
_WEAK_POSITIVE_ACTIVATION_FIELDS = frozenset(
    {
        "activation_signal",
        "activation_path",
        "borrowed_activation_path",
        "preserved_activation_path",
        "trigger_path",
    }
)
_WEAK_POSITIVE_EFFECT_FIELDS = frozenset(
    {
        "borrowed_effect_path",
        "effect_path",
        "effect_signal",
        "outcome_path",
        "preserved_effect_path",
    }
)
_WEAK_POSITIVE_RISK_FIELDS = frozenset(
    {
        "borrowed_risk_to_avoid",
        "preserved_risk_to_avoid",
        "risk",
        "risk_to_avoid",
        "risk_to_avoidance",
        "risks_to_avoid",
    }
)
_TARGET_LINKAGE_FIELDS = frozenset(
    {
        "borrowed_target_file",
        "code_target_file",
        "entry_file",
        "file_path",
        "implementation_target_file",
        "implementation_file",
        "implementation_path",
        "preserved_target_file",
        "proposal_target_file",
        "target_file",
        "target_files",
        "target_path",
        "target_paths",
    }
)
_ACTION_LINKAGE_FIELDS = frozenset(
    {
        "action",
        "borrowed_action",
        "change_action",
        "implementation_action",
        "preserved_action",
        "proposal_change_action",
        "proposal_action",
        "target_action",
    }
)
_MECHANISM_LINKAGE_FIELDS = frozenset(
    {
        "borrowed_mechanism",
        "implementation_mechanism",
        "mechanism",
        "mechanism_change",
        "mechanism_change_id",
        "mechanism_change_ids",
        "mechanism_id",
        "mechanism_ids",
        "mechanism_linkage",
        "mechanism_linkage_token",
        "mechanism_name",
        "mechanism_or_change_id",
        "mechanism_or_change_ids",
        "mechanism_or_mechanism_change",
        "mechanism_or_mechanism_change_id",
        "mechanism_or_mechanism_change_ids",
        "mechanism_token",
        "operator_id",
        "operator_name",
        "preserved_mechanism",
        "proposal_mechanism",
        "target_mechanism",
        "target_mechanism_id",
        "target_mechanism_ids",
    }
)
_BROAD_MECHANISM_LINKAGE_FIELDS = frozenset(
    {
        "borrowed_mechanism_family",
        "change_locus",
        "mechanism_family",
        "preserved_mechanism_family",
    }
)
_REJECT_REASON_FIELDS = frozenset(
    {
        "reject_reason",
        "reject_reason_code",
        "reject_reason_codes",
        "rejection_reason",
        "rejection_reason_code",
        "rejection_reason_codes",
        "machine_reject_reason_code",
        "machine_reject_reason_codes",
        "reuse_decision",
    }
)
_ACTION_RATIONALE_FIELDS = frozenset(
    {
        "avoid_reason",
        "avoid_reason_code",
        "avoid_rationale",
        "borrow_reason",
        "borrow_reason_code",
        "borrow_rationale",
        "change_rationale",
        "preserve_reason",
        "preserve_reason_code",
        "preserve_rationale",
        "refine_reason",
        "refine_reason_code",
        "refine_rationale",
    }
)
_PRESERVED_SIGNAL_FIELDS = frozenset(
    {
        "preserved_dimension",
        "preserved_dimensions",
        "preserved_signal",
        "preserved_signal_id",
        "preserved_signal_ids",
        "preserved_target",
        "preserved_targets",
    }
)
_METADATA_FIELD_NAMES = frozenset(
    {
        "audit",
        "audit_metadata",
        "candidate_branch_ids",
        "candidate_lesson_ids",
        "decision_features_excluded",
        "metadata",
        "policy",
        "proposal_guidance_only",
        "proposal_visibility_only",
        "record_digest",
        "record_id",
        "record_type",
        "required",
        "required_for",
        "required_fors",
        "required_output_field",
        "requirement_source",
        "schema",
        "schema_version",
        "source",
        "visibility",
    }
)
_BOILERPLATE = frozenset(
    {
        "avoid",
        "borrow",
        "contrast",
        "different",
        "different approach",
        "false",
        "lesson",
        "lesson usage",
        "n/a",
        "none",
        "preserve",
        "reject",
        "required",
        "same",
        "tbd",
        "true",
        "unknown",
        "yes",
    }
)


def project_branch_lesson_records(
    records: Any,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Return compact prompt-visible branch lesson records."""

    if not isinstance(records, (list, tuple)):
        return []
    projected: list[dict[str, Any]] = []
    for raw in records:
        if not isinstance(raw, Mapping):
            continue
        item = _drop_empty(
            {
                "schema_version": raw.get("schema_version"),
                "lesson_id": _clean_text(raw.get("lesson_id")),
                "source": _clean_text(raw.get("source")),
                "decision_input_policy": _clean_text(raw.get("decision_input_policy")),
                "scope": _clean_text(raw.get("scope")),
                "lesson_role": _clean_text(raw.get("lesson_role")),
                "lesson_type": _clean_text(raw.get("lesson_type")),
                "maturity": _clean_text(raw.get("maturity")),
                "source_branch_ids": _string_list(raw.get("source_branch_ids")),
                "shared_signature": _generic_mapping(raw.get("shared_signature")),
                "evidence_basis": _generic_mapping(raw.get("evidence_basis")),
                "transfer_contract": _generic_mapping(raw.get("transfer_contract")),
                "required_response": _generic_mapping(raw.get("required_response")),
                "reason_codes": _string_list(raw.get("reason_codes")),
            }
        )
        if item:
            projected.append(item)
        if len(projected) >= limit:
            break
    return projected


def branch_lesson_usage_requirement_from_records(
    records: Any,
) -> dict[str, Any]:
    """Derive an active top-level proposal requirement from lesson records."""

    lesson_records = [
        record
        for record in project_branch_lesson_records(records, limit=12)
        if _record_requires_branch_lesson_usage(record)
    ]
    if not lesson_records:
        return {}

    required_fors = sorted(
        {
            _required_for(record)
            for record in lesson_records
            if _required_for(record) in _ACTIVE_REQUIRED_FOR
        }
    )
    candidate_lesson_ids = [
        record["lesson_id"] for record in lesson_records if record.get("lesson_id")
    ][:12]
    candidate_branch_ids = sorted(
        {
            branch_id
            for record in lesson_records
            for branch_id in _string_list(record.get("source_branch_ids"))
        }
    )[:12]
    required_contrast_dimensions = sorted(
        {
            dimension
            for record in lesson_records
            for dimension in _string_list(
                _required_response(record).get("required_contrast_dimensions")
            )
        }
    )[:12]
    lesson_types = sorted(
        {
            _clean_text(record.get("lesson_type"))
            for record in lesson_records
            if _clean_text(record.get("lesson_type"))
        }
    )
    lesson_roles = sorted(
        {
            _clean_text(record.get("lesson_role"))
            for record in lesson_records
            if _clean_text(record.get("lesson_role"))
        }
    )
    candidate_lesson_requirements = [
        _candidate_lesson_requirement(record) for record in lesson_records[:12]
    ]
    requirement_source = _requirement_source(
        required_fors=required_fors,
        lesson_types=lesson_types,
        lesson_roles=lesson_roles,
    )
    body = _drop_empty(
        {
            "schema_version": BRANCH_LESSON_USAGE_REQUIREMENT_SCHEMA,
            "record_type": _BRANCH_LESSON_REQUIREMENT_RECORD_TYPE,
            "requirement_source": requirement_source,
            "required": True,
            "required_for": _primary_required_for(required_fors),
            "required_fors": required_fors,
            "required_output_field": "branch_lesson_usage",
            "candidate_branch_ids": candidate_branch_ids,
            "candidate_lesson_ids": candidate_lesson_ids,
            "candidate_lesson_types": lesson_types,
            "candidate_lesson_roles": lesson_roles,
            "candidate_lesson_requirements": candidate_lesson_requirements,
            "candidate_target_files": _candidate_signature_values(
                lesson_records,
                "target_file",
            ),
            "candidate_actions": _candidate_signature_values(
                lesson_records,
                "action",
            ),
            "candidate_change_loci": _candidate_signature_values(
                lesson_records,
                "change_locus",
            ),
            "candidate_mechanism_families": _candidate_signature_values(
                lesson_records,
                "mechanism_family",
            ),
            "required_contrast_dimensions": required_contrast_dimensions,
            "proposal_visibility_only": True,
            "proposal_guidance_only": True,
            "decision_features_excluded": True,
            "advisory_only": not _pre_code_block_required(required_fors),
            "pre_code_block_required": _pre_code_block_required(required_fors),
            "same_branch_refinement_allowed": (
                "same_branch_refinement" in required_fors
            ),
            "sibling_duplication_allowed": False,
        }
    )
    digest = _stable_digest(body)
    return {
        "record_id": f"{_BRANCH_LESSON_REQUIREMENT_PREFIX}:{digest[:16]}",
        "record_digest": digest,
        **body,
    }


def branch_lesson_usage_requirement_metadata(
    branch: Branch,
    *,
    session_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return generic metadata indicating whether branch_lesson_usage is required."""

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
        requirement = _find_branch_lesson_usage_requirement(payload)
        if requirement:
            return {"required": True, "source": source, **requirement}
    return {"required": False}


def branch_lesson_usage_pre_code_block_reason(
    hypothesis: HypothesisProposal,
    branch: Branch,
    *,
    session_ref: Mapping[str, Any] | None = None,
) -> str | None:
    """Return a proposal-quality block reason before code generation, if any."""

    metadata = branch_lesson_usage_requirement_metadata(
        branch,
        session_ref=session_ref,
    )
    if not metadata.get("required"):
        return None
    if not _metadata_pre_code_block_required(metadata):
        return None
    diagnostic = branch_lesson_usage_requirement_diagnostic(
        getattr(hypothesis, "branch_lesson_usage", None),
        metadata=metadata,
        hypothesis=hypothesis,
    )
    if diagnostic == "satisfied":
        return None
    required_for = ",".join(_metadata_required_fors(metadata)) or "unspecified"
    source = _clean_text(metadata.get("source")) or "metadata"
    reason_prefix = _BRANCH_LESSON_USAGE_REASON_PREFIXES.get(
        diagnostic,
        _BRANCH_LESSON_USAGE_SEMANTIC_MISMATCH,
    )
    guidance = _BRANCH_LESSON_USAGE_REASON_GUIDANCE.get(
        diagnostic,
        "The branch_lesson_usage object is present but does not satisfy the "
        "semantic requirement.",
    )
    repair_hint = _repair_skeleton_hint(
        branch_lesson_usage_repair_skeleton(
            getattr(hypothesis, "branch_lesson_usage", None),
            metadata=metadata,
            hypothesis=hypothesis,
        )
    )
    return (
        f"{reason_prefix}: {guidance} structured "
        "branch_lesson_usage is required before code generation "
        f"(source={source}, required_for={required_for}). Regenerate the "
        "hypothesis with compact lesson ids and generic dimensions. Clean "
        "fork proposals must include at least one `contrasted_lessons` entry "
        "or `rejected_lessons` entry "
        "with target_file/action/mechanism linkage plus changed generic "
        "dimensions. Sibling-nearby strict requirements use the same "
        "semantic rule; non-actionable sibling records remain report-only. "
        "Weak-positive "
        "transfer must borrow/preserve the lesson "
        "with activation/effect path and target linkage, or emit "
        "`rejected_weak_positive_lessons` with a machine-readable reject "
        "reason and the same linkage. Same-branch weak-positive "
        "refinement may satisfy the requirement with "
        "`preserved_same_branch_lesson`. Mechanism linkage should use a "
        "specific `mechanism` or `mechanism_change_id`; `mechanism_id`, "
        "`mechanism_ids`, and `target_mechanism_id` are accepted aliases. "
        "Do not satisfy the mechanism field with only a broad family token. "
        "Do not use raw lesson text, LLM "
        "rationale, trace, prompt, transcript, or repeated hypothesis prose. "
        f"{repair_hint}"
    )


def branch_lesson_usage_requirement_satisfied(
    value: Any,
    *,
    metadata: Mapping[str, Any] | None = None,
    hypothesis: HypothesisProposal | None = None,
    allow_machine_reject: bool = True,
) -> bool:
    """Return whether a normalized hypothesis usage object satisfies metadata."""

    return (
        branch_lesson_usage_requirement_diagnostic(
            value,
            metadata=metadata,
            hypothesis=hypothesis,
            allow_machine_reject=allow_machine_reject,
        )
        == "satisfied"
    )


def branch_lesson_usage_requirement_diagnostic(
    value: Any,
    *,
    metadata: Mapping[str, Any] | None = None,
    hypothesis: HypothesisProposal | None = None,
    allow_machine_reject: bool = True,
) -> str:
    """Return a stable reason code for branch-lesson usage requirement status."""

    if not isinstance(value, Mapping) or not value:
        return "missing"
    if not _specific_signal_present(value):
        return "metadata_only"
    required_fors = _metadata_required_fors(metadata or {})
    same_branch_only = bool(required_fors) and set(required_fors) <= {
        "same_branch_refinement"
    }
    metadata = metadata or {}
    semantic_linkage = _proposal_linkage_diagnostic(
        value,
        metadata=metadata,
        hypothesis=hypothesis,
    )
    semantic_linkage_present = semantic_linkage == "satisfied"
    if (
        same_branch_only
        and _same_branch_preserve_refine_present(
            value,
            metadata=metadata,
            hypothesis=hypothesis,
        )
    ):
        return "satisfied"
    if _weak_positive_transfer_required(metadata):
        satisfies_weak_positive = (
            _weak_positive_transfer_application_present(
                value,
                metadata=metadata,
                hypothesis=hypothesis,
            )
        ) or (
            allow_machine_reject
            and _weak_positive_reject_reason_present(
                value,
                metadata=metadata,
                hypothesis=hypothesis,
            )
        )
        if satisfies_weak_positive:
            return "satisfied"
        return "semantic_mismatch"
    if set(required_fors) & _STRICT_REQUIRED_FOR:
        if _strict_clean_fork_lesson_usage_present(
            value,
            metadata=metadata,
            hypothesis=hypothesis,
            allow_machine_reject=allow_machine_reject,
        ):
            return "satisfied"
        if _strict_clean_fork_lesson_attempt_present(
            value,
            metadata=metadata,
        ):
            return (
                "linkage_unrecognized"
                if semantic_linkage == "linkage_unrecognized"
                else "semantic_mismatch"
            )
        return "semantic_mismatch"
    if _same_branch_preserve_refine_present(
        value,
        metadata=metadata,
        hypothesis=hypothesis,
    ):
        return "satisfied"
    satisfies_default = (
        _action_linked_application_present(
            value,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        and _changed_dimensions_present(value)
    )
    if satisfies_default and semantic_linkage_present:
        return "satisfied"
    if satisfies_default:
        return semantic_linkage
    return "semantic_mismatch"


def branch_lesson_usage_missing_block_prefix() -> str:
    """Return the stable proposal-quality block prefix."""

    return _BRANCH_LESSON_USAGE_REQUIRED_MISSING


def branch_lesson_usage_reason_prefixes() -> Mapping[str, str]:
    """Return stable proposal-quality branch-lesson usage reason prefixes."""

    return dict(_BRANCH_LESSON_USAGE_REASON_PREFIXES)


def branch_lesson_usage_repair_skeleton(
    value: Any,
    *,
    metadata: Mapping[str, Any] | None = None,
    hypothesis: HypothesisProposal | None = None,
    allow_machine_reject: bool = True,
) -> dict[str, Any]:
    """Return deterministic canonical fields for repairing lesson usage.

    The skeleton is proposal/audit guidance only. It projects compact ids,
    target/action/mechanism linkage, generic dimensions, and machine-readable
    reason-code fields; raw lesson text and rationale-like fields are omitted.
    """

    metadata = metadata or {}
    diagnostic = branch_lesson_usage_requirement_diagnostic(
        value,
        metadata=metadata,
        hypothesis=hypothesis,
        allow_machine_reject=allow_machine_reject,
    )
    normalized = _normalized_usage_projection(
        value if isinstance(value, Mapping) else {}
    )
    expected = _expected_linkage_projection(metadata, hypothesis)
    missing = _repair_missing_fields(normalized, expected, diagnostic)
    corrected = _corrected_fields_projection(normalized, expected)
    return _drop_empty(
        {
            "schema_version": "branch_lesson_usage_repair_skeleton.v1",
            "proposal_visibility_only": True,
            "proposal_guidance_only": True,
            "decision_features_excluded": True,
            "diagnostic": diagnostic,
            "expected_linkage": expected,
            "corrected_fields": corrected,
            "missing_fields": missing,
            "normalized_usage": normalized,
        }
    )


_BRANCH_LESSON_USAGE_REASON_PREFIXES = {
    "missing": _BRANCH_LESSON_USAGE_REQUIRED_MISSING,
    "metadata_only": _BRANCH_LESSON_USAGE_METADATA_ONLY,
    "linkage_unrecognized": _BRANCH_LESSON_USAGE_LINKAGE_UNRECOGNIZED,
    "semantic_mismatch": _BRANCH_LESSON_USAGE_SEMANTIC_MISMATCH,
}
_BRANCH_LESSON_USAGE_REASON_GUIDANCE = {
    "missing": "No usable branch_lesson_usage object was emitted.",
    "metadata_only": (
        "branch_lesson_usage contains only metadata or boilerplate, not an "
        "applied lesson."
    ),
    "linkage_unrecognized": (
        "branch_lesson_usage names a lesson and contrast dimensions, but the "
        "target/action/mechanism linkage is missing or uses unrecognized "
        "field names."
    ),
    "semantic_mismatch": (
        "branch_lesson_usage is present, but it does not match the required "
        "lesson ids, item-level changed dimensions or machine reject reason, "
        "or concrete target/action/mechanism linkage."
    ),
}


def _repair_skeleton_hint(skeleton: Mapping[str, Any]) -> str:
    corrected = skeleton.get("corrected_fields")
    missing = skeleton.get("missing_fields")
    parts: list[str] = []
    if isinstance(corrected, Mapping) and corrected:
        rendered = ",".join(
            f"{key}={value}"
            for key, value in corrected.items()
            if value not in (None, "", [], {}, ())
        )
        if rendered:
            parts.append(f"corrected_fields:{rendered}")
    if isinstance(missing, (list, tuple)) and missing:
        parts.append("missing_fields:" + ",".join(str(item) for item in missing))
    if not parts:
        return ""
    return (
        "Repair skeleton branch_lesson_usage_repair_skeleton.v1 suggests "
        + "; ".join(parts)
        + "."
    )


def branch_lesson_usage_report_projection(value: Any) -> dict[str, Any]:
    """Return a compact report-only projection of branch_lesson_usage.

    The projection intentionally excludes the normalized usage payload itself.
    Reports get stable counts and a digest for trajectory analysis without
    exposing raw proposal text or making branch lessons available to Decision.
    """

    if not isinstance(value, Mapping):
        return {}
    normalized = _normalized_usage_projection(value)
    raw_present = _specific_signal_present(value)
    if not normalized and not raw_present:
        return {}
    field_counts = _branch_lesson_usage_projection_field_counts(normalized)
    digest_source = normalized or _generic_mapping(value)
    return _drop_empty(
        {
            "schema_version": BRANCH_LESSON_USAGE_REPORT_PROJECTION_SCHEMA,
            "present": True,
            "semantic_projection_present": bool(normalized),
            "unrecognized_usage_present": raw_present and not bool(normalized),
            "projection_digest": (
                _stable_digest(digest_source)[:16] if digest_source else ""
            ),
            "field_counts": field_counts,
            "item_count": sum(field_counts.values()),
            "clean_fork_diversity_claim_present": bool(
                normalized.get("clean_fork_diversity_claim")
            ),
            "report_only": True,
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
        }
    )


def _branch_lesson_usage_projection_field_counts(
    normalized: Mapping[str, Any],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field in (
        "borrowed_lessons",
        "avoided_lessons",
        "contrasted_lessons",
        "preserved_same_branch_lesson",
        "rejected_lessons",
        "rejected_weak_positive_lessons",
    ):
        count = _projection_item_count(normalized.get(field))
        if count:
            counts[field] = count
    return counts


def _projection_item_count(value: Any) -> int:
    if isinstance(value, Mapping):
        return 1 if _present(value) else 0
    if not isinstance(value, (list, tuple)):
        return 0
    return sum(1 for item in value if isinstance(item, Mapping) and _present(item))


def _normalized_usage_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for field in (
        "borrowed_lessons",
        "avoided_lessons",
        "contrasted_lessons",
        "preserved_same_branch_lesson",
        "rejected_lessons",
        "rejected_weak_positive_lessons",
    ):
        items = [
            item
            for item in (
                _normalized_lesson_item(raw)
                for raw in _lesson_item_mappings(value.get(field))
            )
            if item
        ]
        if not items:
            continue
        projected[field] = (
            items[0] if field == "preserved_same_branch_lesson" else items
        )
    claim = _normalized_signal_record(value.get("clean_fork_diversity_claim"))
    if claim:
        projected["clean_fork_diversity_claim"] = claim
    return projected


def _normalized_lesson_item(item: Mapping[str, Any]) -> dict[str, Any]:
    aliases = _recognized_aliases(item)
    return _drop_empty(
        {
            "lesson_id": _lesson_id_from_item(item),
            "lesson_type": _first_present(
                item,
                (
                    "lesson_type",
                    "source_lesson_type",
                    "borrowed_lesson_type",
                    "preserved_lesson_type",
                ),
            ),
            "lesson_role": _first_present(
                item,
                ("lesson_role", "usage_role", "reuse_role"),
            ),
            "source_branch_ids": _string_list(item.get("source_branch_ids")),
            "target_file": _first_field_value(item, _TARGET_LINKAGE_FIELDS),
            "action": _first_field_value(item, _ACTION_LINKAGE_FIELDS),
            "mechanism": _first_field_value(item, _MECHANISM_LINKAGE_FIELDS),
            "mechanism_family": _first_field_value(
                item,
                _BROAD_MECHANISM_LINKAGE_FIELDS,
            ),
            "changed_dimensions": sorted(
                _field_values(item, _CHANGED_DIMENSION_FIELDS)
            ),
            "activation_path": _first_field_value(
                item,
                _WEAK_POSITIVE_ACTIVATION_FIELDS,
            ),
            "effect_path": _first_field_value(item, _WEAK_POSITIVE_EFFECT_FIELDS),
            "risk_to_avoid": _first_field_value(item, _WEAK_POSITIVE_RISK_FIELDS),
            "reject_reason_code": _first_machine_reason_code(item),
            "recognized_aliases": aliases,
        }
    )


def _normalized_signal_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return _drop_empty(
        {
            "changed_dimensions": sorted(
                _field_values(value, _CHANGED_DIMENSION_FIELDS)
            ),
            "sibling_duplication_allowed": value.get("sibling_duplication_allowed"),
        }
    )


def _expected_linkage_projection(
    metadata: Mapping[str, Any],
    hypothesis: HypothesisProposal | None,
) -> dict[str, Any]:
    target = _path_token(getattr(hypothesis, "target_file", None))
    if not target:
        targets = _string_list(metadata.get("candidate_target_files"))
        target = _path_token(targets[0]) if targets else ""
    action = _token(getattr(hypothesis, "action", None))
    if not action:
        actions = _string_list(metadata.get("candidate_actions"))
        action = _token(actions[0]) if actions else ""
    mechanisms = sorted(_hypothesis_mechanism_tokens(hypothesis)) if hypothesis else []
    if not mechanisms:
        mechanisms = sorted(
            {
                _token(value)
                for value in _string_list(metadata.get("candidate_mechanism_families"))
                if _token(value)
            }
        )
    return _drop_empty(
        {
            "target_file": target,
            "action": action,
            "mechanisms": mechanisms,
            "candidate_lesson_ids": sorted(_metadata_candidate_lesson_ids(metadata)),
        }
    )


def _corrected_fields_projection(
    normalized: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    first_item = _first_normalized_item(normalized)
    mechanisms = expected.get("mechanisms")
    mechanism = ""
    if isinstance(mechanisms, (list, tuple)) and mechanisms:
        mechanism = str(mechanisms[0])
    return _drop_empty(
        {
            "target_file": (
                expected.get("target_file")
                or (first_item.get("target_file") if first_item else "")
            ),
            "action": (
                expected.get("action")
                or (first_item.get("action") if first_item else "")
            ),
            "mechanism": (
                mechanism
                or (first_item.get("mechanism") if first_item else "")
                or (first_item.get("mechanism_family") if first_item else "")
            ),
        }
    )


def _repair_missing_fields(
    normalized: Mapping[str, Any],
    expected: Mapping[str, Any],
    diagnostic: str,
) -> list[str]:
    if diagnostic == "satisfied":
        return []
    first_item = _first_normalized_item(normalized)
    if not first_item:
        return ["branch_lesson_usage"]
    missing: list[str] = []
    if expected.get("candidate_lesson_ids") and not first_item.get("lesson_id"):
        missing.append("lesson_id")
    for field in ("target_file", "action"):
        if not first_item.get(field):
            missing.append(field)
    if not (first_item.get("mechanism") or first_item.get("mechanism_family")):
        missing.append("mechanism")
    if diagnostic == "semantic_mismatch" and not first_item.get("changed_dimensions"):
        missing.append("changed_dimensions")
    if diagnostic == "linkage_unrecognized":
        missing.append("recognized_linkage_fields")
    return list(dict.fromkeys(missing))


def _first_normalized_item(normalized: Mapping[str, Any]) -> Mapping[str, Any]:
    for field in (
        "contrasted_lessons",
        "borrowed_lessons",
        "avoided_lessons",
        "preserved_same_branch_lesson",
        "rejected_lessons",
        "rejected_weak_positive_lessons",
    ):
        value = normalized.get(field)
        if isinstance(value, Mapping):
            return value
        if isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, Mapping):
                    return item
    return {}


def _lesson_id_from_item(item: Mapping[str, Any]) -> str:
    return _first_present(
        item,
        (
            "lesson_id",
            "source_lesson_id",
            "branch_lesson_id",
            "borrowed_lesson_id",
            "candidate_lesson_id",
            "preserved_lesson_id",
            "referenced_lesson_id",
        ),
    )


def _first_present(item: Mapping[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        text = _clean_text(item.get(key))
        if text:
            return text
    return ""


def _first_field_value(value: Any, field_names: frozenset[str]) -> str:
    values = sorted(_field_values(value, field_names))
    return values[0] if values else ""


def _first_machine_reason_code(item: Mapping[str, Any]) -> str:
    for raw_key, value in item.items():
        key = _key(raw_key)
        if key not in _REJECT_REASON_FIELDS:
            continue
        for candidate in sorted(_scalar_values(value)):
            text = _clean_text(candidate)
            if not _specific_signal_present(text):
                continue
            if (
                key.endswith("_code")
                or key.endswith("_codes")
                or "_" in text
                or "-" in text
            ):
                return text
    return ""


def _recognized_aliases(item: Mapping[str, Any]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for raw_key in item:
        key = _key(raw_key)
        canonical = _canonical_alias_field(key)
        if canonical and key != canonical:
            aliases[str(raw_key)] = canonical
    return aliases


def _canonical_alias_field(key: str) -> str:
    if key in _TARGET_LINKAGE_FIELDS:
        return "target_file"
    if key in _ACTION_LINKAGE_FIELDS:
        return "action"
    if key in _MECHANISM_LINKAGE_FIELDS:
        return "mechanism"
    if key in _BROAD_MECHANISM_LINKAGE_FIELDS:
        return "mechanism_family"
    if key in _CHANGED_DIMENSION_FIELDS:
        return "changed_dimensions"
    if key in _WEAK_POSITIVE_ACTIVATION_FIELDS:
        return "activation_path"
    if key in _WEAK_POSITIVE_EFFECT_FIELDS:
        return "effect_path"
    if key in _WEAK_POSITIVE_RISK_FIELDS:
        return "risk_to_avoid"
    if key in _REJECT_REASON_FIELDS:
        return "reject_reason_code"
    return ""


def _find_branch_lesson_usage_requirement(
    payload: Any,
    *,
    depth: int = 0,
) -> dict[str, Any]:
    if depth > 5 or payload in (None, "", [], {}, ()):
        return {}
    if isinstance(payload, Mapping):
        direct = payload.get("branch_lesson_usage_requirement")
        if isinstance(direct, Mapping) and _active_requirement(direct):
            return dict(direct)
        if _active_requirement(payload):
            return dict(payload)

        for key in ("branch_lesson_records", "branch_lessons"):
            requirement = branch_lesson_usage_requirement_from_records(payload.get(key))
            if requirement:
                return requirement
        nested_payload = payload.get("cross_branch_research_payload")
        if isinstance(nested_payload, Mapping):
            requirement = branch_lesson_usage_requirement_from_records(
                nested_payload.get("branch_lesson_records")
            )
            if requirement:
                return requirement

        for value in payload.values():
            found = _find_branch_lesson_usage_requirement(
                value,
                depth=depth + 1,
            )
            if found:
                return found
    if isinstance(payload, (list, tuple)):
        requirement = branch_lesson_usage_requirement_from_records(payload)
        if requirement:
            return requirement
        for item in payload:
            found = _find_branch_lesson_usage_requirement(item, depth=depth + 1)
            if found:
                return found
    return {}


def _record_requires_branch_lesson_usage(record: Mapping[str, Any]) -> bool:
    if record.get("schema_version") != BRANCH_LESSON_RECORD_SCHEMA:
        return False
    response = _required_response(record)
    if response.get("required_output_field") != "branch_lesson_usage":
        return False
    return (
        _required_for(record) in _ACTIVE_REQUIRED_FOR
        and _actionable_lesson_record(record)
    )


def _actionable_lesson_record(record: Mapping[str, Any]) -> bool:
    if not _clean_text(record.get("lesson_id")):
        return False
    if not _clean_text(record.get("lesson_type")):
        return False
    if not _clean_text(record.get("lesson_role")):
        return False
    if _specific_signal_present(record.get("shared_signature")):
        return True
    if _specific_signal_present(record.get("transfer_contract")):
        return True
    return _actionable_evidence_basis(record.get("evidence_basis"))


def _actionable_evidence_basis(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    for item in value.values():
        if isinstance(item, Mapping):
            if _actionable_status_counts(item):
                return True
            if _actionable_evidence_basis(item):
                return True
            continue
        if isinstance(item, (list, tuple, set)):
            if any(_actionable_evidence_basis(child) for child in item):
                return True
            continue
        text = _token(item) if isinstance(item, str) else ""
        if text and text not in {"unknown", "active"}:
            return True
    return False


def _actionable_status_counts(value: Mapping[str, Any]) -> bool:
    for raw_key, raw_count in value.items():
        key = _token(raw_key)
        if key in {"unknown", "active"}:
            continue
        try:
            count = float(raw_count)
        except (TypeError, ValueError):
            count = 1.0 if _specific_signal_present(raw_count) else 0.0
        if count > 0:
            return True
    return False


def _required_response(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("required_response")
    return value if isinstance(value, Mapping) else {}


def _candidate_lesson_requirement(record: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(
        {
            "lesson_id": _clean_text(record.get("lesson_id")),
            "lesson_role": _clean_text(record.get("lesson_role")),
            "lesson_type": _clean_text(record.get("lesson_type")),
            "required_for": _required_for(record),
            "shared_signature": _generic_mapping(record.get("shared_signature")),
            "required_response": _generic_mapping(record.get("required_response")),
            "transfer_contract": _generic_mapping(record.get("transfer_contract")),
        }
    )


def _candidate_signature_values(
    records: Iterable[Mapping[str, Any]],
    field_name: str,
) -> list[str]:
    values = {
        _clean_text(record.get("shared_signature", {}).get(field_name))
        for record in records
        if isinstance(record.get("shared_signature"), Mapping)
    }
    return sorted(value for value in values if value)[:12]


def _required_for(record: Mapping[str, Any]) -> str:
    return _clean_text(_required_response(record).get("required_for"))


def _active_requirement(value: Mapping[str, Any]) -> bool:
    if value.get("schema_version") != BRANCH_LESSON_USAGE_REQUIREMENT_SCHEMA:
        return False
    if value.get("required") is False:
        return False
    if value.get("required") is True:
        return True
    return bool(
        _clean_text(value.get("record_id"))
        or _clean_text(value.get("required_for"))
        or _string_list(value.get("required_fors"))
    )


def _primary_required_for(required_fors: Iterable[str]) -> str:
    values = set(required_fors)
    for candidate in (
        "clean_fork_new_branch",
        "sibling_nearby_attempt",
        "same_branch_refinement",
    ):
        if candidate in values:
            return candidate
    return "sibling_nearby_attempt"


def _requirement_source(
    *,
    required_fors: Iterable[str],
    lesson_types: Iterable[str],
    lesson_roles: Iterable[str],
) -> str:
    required_for_set = set(required_fors)
    lesson_type_set = set(lesson_types)
    lesson_role_set = set(lesson_roles)
    if (
        "weak_positive" in lesson_type_set
        and required_for_set & _STRICT_REQUIRED_FOR
        and "borrow" in lesson_role_set
    ):
        return "weak_positive_transfer"
    if "clean_fork_new_branch" in required_for_set:
        return "clean_fork_diversity_pressure"
    if "sibling_nearby_attempt" in required_for_set:
        return "sibling_nearby_pressure"
    if "same_branch_refinement" in required_for_set:
        return "same_branch_refinement"
    return "branch_lesson_pressure"


def _weak_positive_transfer_required(metadata: Mapping[str, Any]) -> bool:
    if _clean_text(metadata.get("requirement_source")) == "weak_positive_transfer":
        return True
    return (
        "weak_positive" in set(_string_list(metadata.get("candidate_lesson_types")))
        and bool(set(_metadata_required_fors(metadata)) & _STRICT_REQUIRED_FOR)
        and "borrow" in set(_string_list(metadata.get("candidate_lesson_roles")))
    )


def _metadata_required_fors(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    values = _string_list(metadata.get("required_fors"))
    single = _clean_text(metadata.get("required_for"))
    if single:
        values.append(single)
    return tuple(item for item in dict.fromkeys(values) if item in _ACTIVE_REQUIRED_FOR)


def _metadata_pre_code_block_required(metadata: Mapping[str, Any]) -> bool:
    if metadata.get("pre_code_block_required") is False:
        return False
    if metadata.get("advisory_only") is True:
        return False
    return _pre_code_block_required(_metadata_required_fors(metadata))


def _pre_code_block_required(required_fors: Iterable[str]) -> bool:
    return bool(set(required_fors) & _HARD_PRE_CODE_REQUIRED_FOR)


def _metadata_candidate_lesson_ids(
    metadata: Mapping[str, Any],
    *,
    lesson_types: set[str] | None = None,
    lesson_roles: set[str] | None = None,
) -> set[str]:
    raw_requirements = metadata.get("candidate_lesson_requirements")
    if isinstance(raw_requirements, (list, tuple)):
        values = set()
        for item in raw_requirements:
            if not isinstance(item, Mapping):
                continue
            lesson_type = _clean_text(item.get("lesson_type"))
            lesson_role = _clean_text(item.get("lesson_role"))
            if lesson_types and lesson_type not in lesson_types:
                continue
            if lesson_roles and lesson_role not in lesson_roles:
                continue
            lesson_id = _clean_text(item.get("lesson_id"))
            if lesson_id:
                values.add(lesson_id)
        if values:
            return values
    if lesson_types or lesson_roles:
        metadata_types = set(_string_list(metadata.get("candidate_lesson_types")))
        metadata_roles = set(_string_list(metadata.get("candidate_lesson_roles")))
        if lesson_types and metadata_types and not (lesson_types & metadata_types):
            return set()
        if lesson_roles and metadata_roles and not (lesson_roles & metadata_roles):
            return set()
    return set(_string_list(metadata.get("candidate_lesson_ids")))


def _proposal_linkage_present(
    value: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    hypothesis: HypothesisProposal | None,
) -> bool:
    return (
        _proposal_linkage_diagnostic(
            value,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        == "satisfied"
    )


def _proposal_linkage_diagnostic(
    value: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    hypothesis: HypothesisProposal | None,
) -> str:
    if hypothesis is None:
        target_present = _field_signal_present(value, _TARGET_LINKAGE_FIELDS)
        action_present = _field_signal_present(value, _ACTION_LINKAGE_FIELDS)
        mechanism_present = _field_signal_present(value, _MECHANISM_LINKAGE_FIELDS)
        broad_mechanism_present = _field_signal_present(
            value,
            _BROAD_MECHANISM_LINKAGE_FIELDS,
        )
        if target_present and action_present and (
            mechanism_present or broad_mechanism_present
        ):
            return "satisfied"
        if target_present or action_present or _mechanism_linkage_attempt_present(value):
            return "linkage_unrecognized"
        return "semantic_mismatch"

    expected_target = _path_token(getattr(hypothesis, "target_file", None))
    expected_action = _token(getattr(hypothesis, "action", None))
    expected_mechanisms = _hypothesis_mechanism_tokens(hypothesis)

    target_values = _field_values(value, _TARGET_LINKAGE_FIELDS)
    action_values = _field_values(value, _ACTION_LINKAGE_FIELDS)
    mechanism_values = _field_values(value, _MECHANISM_LINKAGE_FIELDS)
    broad_mechanism_values = _field_values(value, _BROAD_MECHANISM_LINKAGE_FIELDS)

    target_ok = _values_correspond_to_expected_path(
        target_values,
        expected_target,
        metadata,
    )
    action_ok = _values_correspond_to_expected_token(action_values, expected_action)
    mechanism_ok = _values_correspond_to_any_token(
        mechanism_values,
        expected_mechanisms,
    )
    broad_mechanism_ok = _broad_mechanism_values_correspond(
        broad_mechanism_values,
        metadata,
        expected_mechanisms,
    )
    if target_ok and action_ok and (mechanism_ok or broad_mechanism_ok):
        return "satisfied"
    if (
        (
            not target_values
            or not action_values
            or (not mechanism_values and not broad_mechanism_values)
        )
        and _linkage_attempt_present(value)
    ):
        return "linkage_unrecognized"
    return "semantic_mismatch"


def _hypothesis_mechanism_tokens(hypothesis: HypothesisProposal) -> set[str]:
    values = set()
    for change in mechanism_changes(hypothesis):
        values.add(_token(change.id))
    if not values:
        values.add(_token(getattr(hypothesis, "change_locus", None)))
    return {value for value in values if value}


def _values_correspond_to_expected_path(
    values: set[str],
    expected: str,
    metadata: Mapping[str, Any],
) -> bool:
    if not values:
        return False
    if not expected:
        return any(_specific_signal_present(value) for value in values)
    normalized_values = {_path_token(value) for value in values if value}
    if expected in normalized_values:
        return True
    if any(_paths_compatible(value, expected) for value in normalized_values):
        return True
    candidate_targets = {
        _path_token(value)
        for value in _string_list(metadata.get("candidate_target_files"))
    }
    return bool(candidate_targets and normalized_values & candidate_targets)


def _values_correspond_to_expected_token(values: set[str], expected: str) -> bool:
    if not values:
        return False
    if not expected:
        return any(_specific_signal_present(value) for value in values)
    normalized_values = {_token(value) for value in values if value}
    return any(_tokens_compatible(value, expected) for value in normalized_values)


def _values_correspond_to_any_token(
    values: set[str],
    expected: set[str],
) -> bool:
    if not values:
        return False
    normalized_values = {_token(value) for value in values if value}
    expected_values = {_token(value) for value in expected if value}
    if expected_values and normalized_values & expected_values:
        return True
    if expected_values and any(
        _tokens_compatible(value, expected_value)
        for value in normalized_values
        for expected_value in expected_values
    ):
        return True
    if expected_values:
        return False
    return any(_specific_signal_present(value) for value in values)


def _broad_mechanism_values_correspond(
    values: set[str],
    metadata: Mapping[str, Any],
    expected_mechanisms: set[str],
) -> bool:
    if not values:
        return False
    normalized_values = {_token(value) for value in values if value}
    candidate_families = {
        _token(value)
        for value in _string_list(metadata.get("candidate_mechanism_families"))
    }
    if candidate_families and normalized_values & candidate_families:
        return True
    if candidate_families and any(
        _tokens_compatible(value, family)
        for value in normalized_values
        for family in candidate_families
    ):
        return True
    expected_values = {_token(value) for value in expected_mechanisms if value}
    if expected_values and normalized_values & expected_values:
        return True
    if expected_values and any(
        _tokens_compatible(value, expected)
        for value in normalized_values
        for expected in expected_values
    ):
        return True
    return any(_specific_signal_present(value) for value in values)


def _linkage_attempt_present(value: Any) -> bool:
    return (
        _field_signal_present(value, _TARGET_LINKAGE_FIELDS)
        or _field_signal_present(value, _ACTION_LINKAGE_FIELDS)
        or _mechanism_linkage_attempt_present(value)
    )


def _mechanism_linkage_attempt_present(value: Any, *, depth: int = 0) -> bool:
    if depth > 5:
        return False
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = _key(raw_key)
            if _metadata_key(key):
                continue
            if key in _MECHANISM_LINKAGE_FIELDS | _BROAD_MECHANISM_LINKAGE_FIELDS:
                if _specific_signal_present(item):
                    return True
                continue
            if "mechanism" in key and _specific_signal_present(item):
                return True
            if _mechanism_linkage_attempt_present(item, depth=depth + 1):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(
            _mechanism_linkage_attempt_present(item, depth=depth + 1)
            for item in value
        )
    return False


def _field_values(
    value: Any,
    field_names: frozenset[str],
    *,
    depth: int = 0,
) -> set[str]:
    if depth > 5:
        return set()
    if isinstance(value, Mapping):
        values: set[str] = set()
        for raw_key, item in value.items():
            key = _key(raw_key)
            if key in field_names:
                values.update(_scalar_values(item))
                continue
            if not _metadata_key(key):
                values.update(_field_values(item, field_names, depth=depth + 1))
        return values
    if isinstance(value, (list, tuple, set)):
        values: set[str] = set()
        for item in value:
            values.update(_field_values(item, field_names, depth=depth + 1))
        return values
    return set()


def _scalar_values(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        values: set[str] = set()
        for item in value.values():
            values.update(_scalar_values(item))
        return values
    if isinstance(value, (list, tuple, set)):
        values: set[str] = set()
        for item in value:
            values.update(_scalar_values(item))
        return values
    text = _clean_text(value)
    return {text} if text else set()


def _action_linked_application_present(
    value: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    hypothesis: HypothesisProposal | None,
) -> bool:
    return any(
        _lesson_items_with_action_linkage_present(
            value.get(field),
            metadata=metadata,
            hypothesis=hypothesis,
            require_action_rationale=field in {"borrowed_lessons", "avoided_lessons"},
        )
        for field in _LESSON_APPLICATION_FIELDS
    )


def _lesson_items_with_action_linkage_present(
    value: Any,
    *,
    metadata: Mapping[str, Any],
    hypothesis: HypothesisProposal | None,
    lesson_types: set[str] | None = None,
    lesson_roles: set[str] | None = None,
    require_changed_dimensions: bool = False,
    require_action_rationale: bool = False,
) -> bool:
    return any(
        _lesson_item_semantic(
            item,
            metadata=metadata,
            lesson_types=lesson_types,
            lesson_roles=lesson_roles,
        )
        and _lesson_item_action_linkage_present(
            item,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        and (
            not require_changed_dimensions
            or _changed_dimensions_present(item)
        )
        and (
            not require_action_rationale
            or _field_signal_present(item, _ACTION_RATIONALE_FIELDS)
        )
        for item in _lesson_item_mappings(value)
    )


def _lesson_item_mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _lesson_items_present(
    value: Any,
    *,
    metadata: Mapping[str, Any] | None = None,
    lesson_types: set[str] | None = None,
    lesson_roles: set[str] | None = None,
) -> bool:
    if isinstance(value, Mapping):
        return _lesson_item_semantic(
            value,
            metadata=metadata or {},
            lesson_types=lesson_types,
            lesson_roles=lesson_roles,
        )
    if not isinstance(value, (list, tuple)):
        return False
    return any(
        isinstance(item, Mapping)
        and _lesson_item_semantic(
            item,
            metadata=metadata or {},
            lesson_types=lesson_types,
            lesson_roles=lesson_roles,
        )
        for item in value
    )


def _same_branch_preserve_refine_present(
    value: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    hypothesis: HypothesisProposal | None,
) -> bool:
    return any(
        _lesson_item_semantic(
            item,
            metadata=metadata,
            lesson_roles={"preserve"},
        )
        and _lesson_item_action_linkage_present(
            item,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        and _field_signal_present(item, _PRESERVED_SIGNAL_FIELDS)
        and _changed_dimensions_present(item)
        for item in _lesson_item_mappings(value.get("preserved_same_branch_lesson"))
    )


def _strict_clean_fork_lesson_usage_present(
    value: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    hypothesis: HypothesisProposal | None,
    allow_machine_reject: bool,
) -> bool:
    contrasted = _lesson_items_with_action_linkage_present(
        value.get("contrasted_lessons"),
        metadata=metadata,
        hypothesis=hypothesis,
        require_changed_dimensions=True,
    )
    rejected = allow_machine_reject and _lesson_items_with_machine_reject_present(
        value.get("rejected_lessons"),
        metadata=metadata,
        hypothesis=hypothesis,
    )
    return contrasted or rejected


def _strict_clean_fork_lesson_attempt_present(
    value: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
) -> bool:
    return any(
        _lesson_items_present(
            value.get(field),
            metadata=metadata,
        )
        for field in _LESSON_APPLICATION_FIELDS | {"rejected_lessons"}
    )


def _weak_positive_transfer_application_present(
    value: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    hypothesis: HypothesisProposal | None,
) -> bool:
    return (
        any(
            _lesson_items_with_action_linkage_present(
                value.get(field),
                metadata=metadata,
                hypothesis=hypothesis,
                lesson_types={"weak_positive"},
                lesson_roles={"borrow", "preserve"},
            )
            for field in _WEAK_POSITIVE_APPLICATION_FIELDS
        )
        and _weak_positive_activation_effect_path_present(value)
        and (
            _risk_to_avoid_present(value)
            or (
                _lesson_items_present(
                    value.get("contrasted_lessons"),
                    metadata=metadata,
                )
                and _changed_dimensions_present(value)
            )
        )
    )


def _weak_positive_reject_reason_present(
    value: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    hypothesis: HypothesisProposal | None,
) -> bool:
    return any(
        _lesson_items_with_machine_reject_present(
            value.get(field),
            metadata=metadata,
            hypothesis=hypothesis,
            lesson_types={"weak_positive"},
        )
        for field in _LESSON_REJECTION_FIELDS
    )


def _lesson_items_with_machine_reject_present(
    value: Any,
    *,
    metadata: Mapping[str, Any],
    hypothesis: HypothesisProposal | None,
    lesson_types: set[str] | None = None,
) -> bool:
    return any(
        _lesson_item_semantic(
            item,
            metadata=metadata,
            lesson_types=lesson_types,
        )
        and _lesson_item_action_linkage_present(
            item,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        and _machine_readable_reject_reason_present(item)
        for item in _lesson_item_mappings(value)
    )


def _lesson_item_action_linkage_present(
    item: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    hypothesis: HypothesisProposal | None,
) -> bool:
    return (
        _proposal_linkage_diagnostic(
            item,
            metadata=metadata,
            hypothesis=hypothesis,
        )
        == "satisfied"
    )


def _machine_readable_reject_reason_present(item: Mapping[str, Any]) -> bool:
    for raw_key, value in item.items():
        key = _key(raw_key)
        if key not in _REJECT_REASON_FIELDS:
            continue
        values = _scalar_values(value)
        if key.endswith("_code") or key.endswith("_codes"):
            if any(_specific_signal_present(candidate) for candidate in values):
                return True
            continue
        for candidate in values:
            text = _clean_text(candidate)
            if not _specific_signal_present(text):
                continue
            if "_" in text or "-" in text:
                return True
    return False


def _lesson_item_semantic(
    item: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any],
    lesson_types: set[str] | None = None,
    lesson_roles: set[str] | None = None,
) -> bool:
    if not _specific_signal_present(item):
        return False
    if lesson_types:
        lesson_type = _clean_text(
            item.get("lesson_type")
            or item.get("source_lesson_type")
            or item.get("borrowed_lesson_type")
            or item.get("preserved_lesson_type")
        )
        if lesson_type and lesson_type not in lesson_types:
            return False
    if lesson_roles:
        role = _clean_text(
            item.get("lesson_role") or item.get("usage_role") or item.get("reuse_role")
        )
        if role and role not in lesson_roles:
            return False
    candidate_ids = _metadata_candidate_lesson_ids(
        metadata,
        lesson_types=lesson_types,
        lesson_roles=lesson_roles,
    )
    if not candidate_ids:
        return True
    lesson_id = _lesson_id_from_item(item)
    return lesson_id in candidate_ids


def _changed_dimensions_present(value: Any, *, depth: int = 0) -> bool:
    if depth > 5:
        return False
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = _key(raw_key)
            if key in _CHANGED_DIMENSION_FIELDS:
                if _specific_signal_present(item):
                    return True
                continue
            if not _metadata_key(key) and _changed_dimensions_present(
                item,
                depth=depth + 1,
            ):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_changed_dimensions_present(item, depth=depth + 1) for item in value)
    return False


def _weak_positive_activation_effect_path_present(value: Mapping[str, Any]) -> bool:
    return _field_signal_present(
        value,
        _WEAK_POSITIVE_ACTIVATION_FIELDS,
    ) and _field_signal_present(value, _WEAK_POSITIVE_EFFECT_FIELDS)


def _risk_to_avoid_present(value: Mapping[str, Any]) -> bool:
    return _field_signal_present(value, _WEAK_POSITIVE_RISK_FIELDS)


def _field_signal_present(
    value: Any,
    field_names: frozenset[str],
    *,
    depth: int = 0,
) -> bool:
    if depth > 5:
        return False
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = _key(raw_key)
            if key in field_names and _specific_signal_present(item):
                return True
            if not _metadata_key(key) and _field_signal_present(
                item,
                field_names,
                depth=depth + 1,
            ):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(
            _field_signal_present(item, field_names, depth=depth + 1) for item in value
        )
    return False


def _specific_signal_present(value: Any, *, depth: int = 0) -> bool:
    if depth > 4:
        return False
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = _key(raw_key)
            if _metadata_key(key):
                continue
            if _specific_signal_present(item, depth=depth + 1):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_specific_signal_present(item, depth=depth + 1) for item in value)
    if isinstance(value, str):
        text = " ".join(value.strip().lower().split())
        return bool(text and text not in _BOILERPLATE)
    return value not in (None, "", [], {}, ())


def _generic_mapping(value: Any, *, depth: int = 0) -> dict[str, Any]:
    if depth > 4 or not isinstance(value, Mapping):
        return {}
    return _drop_empty(
        {
            str(key): _generic_value(child, depth=depth + 1)
            for key, child in value.items()
            if _allowed_generic_key(str(key))
        }
    )


def _generic_value(value: Any, *, depth: int = 0) -> Any:
    if isinstance(value, Mapping):
        return _generic_mapping(value, depth=depth)
    if isinstance(value, (list, tuple)):
        projected = [_generic_value(item, depth=depth + 1) for item in value[:8]]
        return [item for item in projected if _present(item)]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str):
            return _clean_text(value)[:200]
        return value
    return _clean_text(value)[:200]


def _allowed_generic_key(key: str) -> bool:
    lowered = key.lower()
    blocked_fragments = (
        "audit",
        "metadata",
        "session",
        "payload",
        "raw",
        "trace",
        "prompt",
        "transcript",
        "rationale",
    )
    return not any(fragment in lowered for fragment in blocked_fragments)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _token(value: Any) -> str:
    return _clean_text(value).lower().replace("-", "_").replace(" ", "_")


def _path_token(value: Any) -> str:
    return _clean_text(value).replace("\\", "/").strip().lower()


def _tokens_compatible(left: str, right: str) -> bool:
    left = _token(left)
    right = _token(right)
    if not left or not right:
        return False
    if left == right:
        return True
    if left.startswith(f"{right}_") or right.startswith(f"{left}_"):
        return True
    left_parts = [part for part in left.split("_") if part]
    right_parts = [part for part in right.split("_") if part]
    if not left_parts or not right_parts:
        return False
    short, long = (
        (left_parts, right_parts)
        if len(left_parts) <= len(right_parts)
        else (right_parts, left_parts)
    )
    for start in range(0, len(long) - len(short) + 1):
        if long[start : start + len(short)] == short:
            return True
    return False


def _paths_compatible(value: str, expected: str) -> bool:
    value = _path_token(value)
    expected = _path_token(expected)
    if not value or not expected:
        return False
    if value == expected:
        return True
    if value.endswith(f"/{expected}") or expected.endswith(f"/{value}"):
        return True
    value_name = value.rsplit("/", 1)[-1]
    expected_name = expected.rsplit("/", 1)[-1]
    return bool(value_name and value_name == expected_name)


def _key(value: Any) -> str:
    return str(value or "").strip().lower()


def _metadata_key(key: str) -> bool:
    if key in _METADATA_FIELD_NAMES:
        return True
    return key.endswith("_source") or key.endswith("_policy")


def _stable_digest(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _present(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_present(child) for child in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_present(item) for item in value)
    return bool(value)


def _drop_empty(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: child for key, child in value.items() if _present(child)}
