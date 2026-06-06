"""Prompt-visible hypothesis context profiles.

The full hypothesis context remains the ContextManager contract.  This module
projects that context into a smaller tainted prompt context before creative or
agentic hypothesis generation.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Mapping

HypothesisContextProfile = Literal["algorithm", "repair"]

_FULL_CONTEXT_KEYS = frozenset(
    {
        "branch_dossier",
        "branch_dossier_payload",
        "research_log",
        "cross_branch_research_payload",
        "cross_branch_research_audit_records",
        "cross_branch_research_session_metadata",
        "branch_followup_policy_payload",
    }
)

_REPAIR_FEEDBACK_KEYS = frozenset(
    {
        "agentic_prior_quality_blocks",
        "agentic_prior_quality_block_rule",
        "agentic_negative_fact_block",
        "agent_quality_feedback",
        "contract_preview_failure_signature",
        "failure_pattern_warning",
        "runtime_failure_guidance",
    }
)

_REPAIR_TRIGGER_KEYS = frozenset(
    {
        "agentic_prior_quality_blocks",
        "agentic_negative_fact_block",
        "agent_quality_feedback",
        "contract_preview_failure_signature",
        "failure_pattern_warning",
        "runtime_failure_guidance",
    }
)

_COMPACT_LEARNING_SCHEMA = "compact_cross_branch_learning.v1"


def derive_hypothesis_context_profile(
    context: Mapping[str, Any],
) -> HypothesisContextProfile:
    """Return the prompt profile for hypothesis generation."""
    for key in _REPAIR_TRIGGER_KEYS:
        if _present(context.get(key)):
            return "repair"
    branch_hygiene = context.get("branch_hygiene")
    if isinstance(branch_hygiene, Mapping) and (
        branch_hygiene.get("repair_focus_required") is True
        or _present(branch_hygiene.get("repair_focus_reason"))
    ):
        return "repair"
    guidance = str(context.get("branch_hygiene_guidance") or "").lower()
    if "repair" in guidance and (
        "required" in guidance or "constraint" in guidance or "suspect" in guidance
    ):
        return "repair"
    return "algorithm"


def filter_hypothesis_context_for_prompt(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Project ContextManager output into the prompt-visible context."""
    profile = derive_hypothesis_context_profile(context)
    filtered = dict(context)

    for key in _FULL_CONTEXT_KEYS:
        filtered.pop(key, None)

    compact_cross_branch = _compact_cross_branch_research(
        context.get("cross_branch_research_payload")
    )
    if compact_cross_branch:
        filtered["cross_branch_research"] = compact_cross_branch
    else:
        filtered.pop("cross_branch_research", None)

    if profile != "repair":
        for key in _REPAIR_FEEDBACK_KEYS:
            filtered.pop(key, None)

    if not _active_material_difference_requirement(
        context.get("material_difference_requirement")
    ):
        filtered.pop("material_difference_requirement", None)

    return filtered


def _compact_cross_branch_research(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return ""
    compact = _drop_empty(
        {
            "schema_version": _COMPACT_LEARNING_SCHEMA,
            "taint": "proposal_research_feedback",
            "decision_input_policy": "excluded_from_decision_features",
            "near_duplicate_hints": _project_items(
                payload.get("similarity_hints"),
                fields=(
                    "hint_type",
                    "branch_ids",
                    "shared_signature",
                    "outcome_patterns",
                    "recommended_action",
                    "reason_codes",
                    "summary",
                ),
                accepted_types={"near_duplicate", "saturated_family"},
            ),
            "avoid_hints": _project_items(
                payload.get("avoid_bridge_guidance"),
                fields=(
                    "guidance_type",
                    "hint_type",
                    "source",
                    "branch_ids",
                    "signature",
                    "shared_signature",
                    "outcome_patterns",
                    "lesson_type",
                    "failure_mode",
                    "recommended_action",
                    "priority",
                    "proposal_guidance",
                    "confidence",
                    "reason_codes",
                    "summary",
                ),
            ),
            "opportunity_hints": _project_items(
                payload.get("opportunity_gaps"),
                fields=(
                    "hint_type",
                    "opportunity_type",
                    "gap_type",
                    "source",
                    "recommended_action",
                    "priority",
                    "basis",
                    "proposal_guidance",
                    "confidence",
                    "reason_codes",
                    "summary",
                ),
            ),
            "lesson_hints": _project_items(
                payload.get("lesson_cards") or payload.get("lessons"),
                fields=(
                    "scope",
                    "branch_id",
                    "branch_ids",
                    "lesson_type",
                    "failure_mode",
                    "evidence_strength",
                    "transferability",
                    "recommended_action",
                    "affected_stage",
                    "confidence",
                    "reason_codes",
                    "summary",
                ),
            ),
            "portfolio_guidance": _project_generic_value(
                payload.get("portfolio_guidance")
            ),
            "novelty_pressure": _project_mapping(
                payload.get("novelty_pressure"),
                fields=(
                    "policy",
                    "pressure",
                    "recommended_action",
                    "reason_codes",
                    "summary",
                ),
            ),
        }
    )
    if len(compact) <= 3:
        return ""
    rendered = json.dumps(compact, indent=2, sort_keys=True, default=str)
    return (
        "This compact cross-branch learning summary is tainted proposal "
        "feedback for hypothesis planning only. It is excluded from "
        "DecisionFeatures and must not be used as a deterministic decision "
        "input.\n"
        f"{rendered}"
    )


def _project_items(
    value: Any,
    *,
    fields: tuple[str, ...],
    accepted_types: set[str] | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    items: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        hint_type = str(raw.get("hint_type") or raw.get("lesson_type") or "")
        if accepted_types is not None and hint_type not in accepted_types:
            continue
        projected = _project_mapping(raw, fields=fields)
        if projected:
            items.append(projected)
        if len(items) >= limit:
            break
    return items


def _project_mapping(
    value: Any,
    *,
    fields: tuple[str, ...],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return _drop_empty(
        {
            field: _project_generic_value(value.get(field))
            for field in fields
            if field in value
        }
    )


def _project_generic_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _drop_empty(
            {
                str(key): _project_generic_value(child)
                for key, child in value.items()
                if _allowed_generic_key(str(key))
            }
        )
    if isinstance(value, (list, tuple)):
        projected = [_project_generic_value(item) for item in value[:8]]
        return [item for item in projected if _present(item)]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > 500:
            return value[:497] + "..."
        return value
    return str(value)[:500]


def _allowed_generic_key(key: str) -> bool:
    lowered = key.lower()
    blocked_fragments = (
        "audit",
        "metadata",
        "session",
        "payload",
        "raw_metrics",
        "holdout",
        "validation",
        "frozen",
        "material_difference",
    )
    return not any(fragment in lowered for fragment in blocked_fragments)


def _active_material_difference_requirement(value: Any) -> bool:
    if not isinstance(value, Mapping) or value.get("required") is not True:
        return False
    for key, child in value.items():
        if key in {"schema_version", "required"}:
            continue
        if _present(child):
            return True
    return False


def _present(value: Any) -> bool:
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


__all__ = [
    "HypothesisContextProfile",
    "derive_hypothesis_context_profile",
    "filter_hypothesis_context_for_prompt",
]
