"""Prompt-visible hypothesis context profiles.

The full hypothesis context remains the ContextManager contract.  This module
projects that context into a smaller tainted prompt context before creative or
agentic hypothesis generation.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Mapping

from scion.proposal.context_ablation import normalize_proposal_context_ablation

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

_MINIMAL_RESEARCH_CONTEXT_KEYS = frozenset(
    {
        "active_hyp_summary",
        "blacklist_summary",
        "branch_dossier",
        "branch_dossier_payload",
        "branch_direction",
        "branch_followup_policy",
        "branch_followup_policy_payload",
        "branch_lesson_records",
        "branch_lesson_usage_requirement",
        "champion_baselines",
        "cross_branch_research",
        "cross_branch_research_payload",
        "cross_branch_research_audit_records",
        "cross_branch_research_session_metadata",
        "experiment_history",
        "exploration_coverage",
        "objective_opportunity_profile",
        "objective_guidance",
        "research_log",
        "runtime_feedback",
        "saturation_signal",
        "search_control_guidance",
        "search_memory",
        "sibling_summary",
        "strategy_guidance",
        "weight_opt_feedback",
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
_PROFILE_METADATA_SCHEMA = "hypothesis_context_profile.v1"
_COMPACT_MEASUREMENT_DIAGNOSTICS_KEY = "compact_problem_measurement_diagnostics"
_OPPORTUNITY_STATUS_RE = re.compile(r"\s+opportunity_status=\S+")


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
    ablation = normalize_proposal_context_ablation(
        context.get("proposal_context_ablation")
    )
    filtered = dict(context)
    filtered["proposal_context_ablation"] = ablation
    filtered["context_profile"] = profile
    filtered["context_profile_metadata"] = {
        "schema_version": _PROFILE_METADATA_SCHEMA,
        "profile": profile,
        "proposal_context_ablation": ablation,
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
    }

    for key in _FULL_CONTEXT_KEYS:
        filtered.pop(key, None)

    if ablation == "minimal-research-context":
        for key in _MINIMAL_RESEARCH_CONTEXT_KEYS:
            filtered.pop(key, None)
    else:
        compact_cross_branch = _compact_cross_branch_research(
            context.get("cross_branch_research_payload")
        )
        if compact_cross_branch:
            filtered["cross_branch_research"] = compact_cross_branch
        else:
            filtered.pop("cross_branch_research", None)

    measurement_governance = _normalize_measurement_governance_mode(
        context.get("measurement_governance")
    )
    compact_measurement_diagnostics_mode = (
        ablation == "compact-measurement-diagnostics"
    )
    hide_measurement_diagnostics = (
        measurement_governance == "record_only"
        or ablation == "no-measurement-diagnostics"
    )
    compact_measurement = (
        ""
        if hide_measurement_diagnostics
        else _compact_problem_measurement_diagnostics(
            context.get("problem_measurement_diagnostics")
        )
    )
    measurement_visibility = "absent"
    if hide_measurement_diagnostics:
        filtered.pop("problem_measurement_diagnostics", None)
        filtered.pop(_COMPACT_MEASUREMENT_DIAGNOSTICS_KEY, None)
        measurement_visibility = "suppressed"
    elif compact_measurement and compact_measurement_diagnostics_mode:
        filtered[_COMPACT_MEASUREMENT_DIAGNOSTICS_KEY] = compact_measurement
        filtered.pop("problem_measurement_diagnostics", None)
        measurement_visibility = "compact"
    elif compact_measurement:
        filtered["problem_measurement_diagnostics"] = compact_measurement
        filtered.pop(_COMPACT_MEASUREMENT_DIAGNOSTICS_KEY, None)
        measurement_visibility = "full"
    else:
        filtered.pop("problem_measurement_diagnostics", None)
        filtered.pop(_COMPACT_MEASUREMENT_DIAGNOSTICS_KEY, None)

    metadata = filtered["context_profile_metadata"]
    metadata["measurement_diagnostics_visibility"] = measurement_visibility
    metadata["measurement_diagnostics_prompt_key"] = (
        _COMPACT_MEASUREMENT_DIAGNOSTICS_KEY
        if measurement_visibility == "compact"
        else (
            "problem_measurement_diagnostics"
            if measurement_visibility == "full"
            else ""
        )
    )
    metadata["measurement_diagnostics_standalone_section"] = (
        measurement_visibility == "full"
    )

    if (
        hide_measurement_diagnostics or compact_measurement_diagnostics_mode
    ) and "experiment_history" in filtered:
        filtered["experiment_history"] = _strip_opportunity_diagnostics_from_text(
            filtered.get("experiment_history")
        )

    if profile != "repair":
        for key in _REPAIR_FEEDBACK_KEYS:
            filtered.pop(key, None)

    if not _active_material_difference_requirement(
        context.get("material_difference_requirement")
    ):
        filtered.pop("material_difference_requirement", None)

    if (
        ablation != "minimal-research-context"
        and not _active_branch_lesson_usage_requirement(
            context.get("branch_lesson_usage_requirement")
        )
    ):
        filtered.pop("branch_lesson_usage_requirement", None)

    return filtered


def _normalize_measurement_governance_mode(value: Any | None) -> str:
    text = "on" if value is None else str(value).strip().lower().replace("-", "_")
    if text in {"on", "record_only"}:
        return text
    return "on"


def _strip_opportunity_diagnostics_from_text(value: Any) -> str:
    lines: list[str] = []
    for line in str(value or "").splitlines():
        if "opportunity_diagnostics:" in line:
            continue
        lines.append(_OPPORTUNITY_STATUS_RE.sub("", line))
    return "\n".join(lines).strip()


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
            "branch_lessons": _project_items(
                payload.get("branch_lesson_records"),
                fields=(
                    "lesson_id",
                    "source",
                    "decision_input_policy",
                    "scope",
                    "lesson_role",
                    "lesson_type",
                    "maturity",
                    "source_branch_ids",
                    "shared_signature",
                    "evidence_basis",
                    "required_response",
                    "reason_codes",
                ),
                limit=8,
            ),
            "portfolio_guidance": _project_generic_value(
                payload.get("portfolio_guidance")
            ),
            "portfolio_steering": _compact_portfolio_steering(
                payload.get("portfolio_steering")
            ),
            "family_saturation_summary": _compact_family_saturation_summary(
                payload.get("family_saturation_summary")
                or _project_mapping(
                    payload.get("portfolio_steering"),
                    fields=("family_saturation_summary",),
                ).get("family_saturation_summary")
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


def _compact_problem_measurement_diagnostics(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return ""
    compact = _drop_empty(
        {
            "schema_version": (
                payload.get("schema_version")
                or "problem_measurement_proposal_diagnostic.v1"
            ),
            "taint": (
                payload.get("taint") or "problem_owned_proposal_diagnostic"
            ),
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "decision_input_policy": "excluded_from_decision_features",
            "runtime_model": _project_generic_value(payload.get("runtime_model")),
            "pairing_validity": _project_generic_value(
                payload.get("pairing_validity")
            ),
            "effect_scale": _project_mapping(
                payload.get("effect_scale"),
                fields=(
                    "metric",
                    "unit",
                    "practical_delta_screen",
                    "practical_delta_validate",
                    "mde_at_power_80",
                    "recommended_min_seeds",
                    "false_pass_rate_at_current_gate",
                ),
            ),
            "calibration": _project_mapping(
                payload.get("calibration") or payload.get("calibration_summary"),
                fields=(
                    "calibration_ref",
                    "calibration_max_age_days",
                    "artifact_ref",
                    "mde_at_power_80",
                    "recommended_min_seeds",
                    "false_pass_rate_at_current_gate",
                    "selected_surface",
                    "runtime_policy",
                ),
            ),
            "measurement_readiness": _project_mapping(
                payload.get("measurement_readiness"),
                fields=(
                    "status",
                    "reason_code",
                    "calibration_age_days",
                    "calibration_max_age_days",
                    "n_pairs",
                    "mde_at_power_80",
                    "noise_band_p90_abs",
                    "effect_to_mde_ratio",
                    "signal_to_noise_tier",
                    "decision_features_excluded",
                    "calibration_ref",
                ),
            ),
            "noise_floor": _project_mapping(
                payload.get("noise_floor") or payload.get("noise_summary"),
                fields=(
                    "mde_at_power_80",
                    "recommended_min_seeds",
                    "false_pass_rate_at_current_gate",
                    "pairing_validity",
                    "runtime_model",
                ),
            ),
            "opportunity_diagnostics": _project_items(
                payload.get("opportunity_diagnostics")
                or payload.get("opportunity_hints"),
                fields=(
                    "diagnostic_type",
                    "surface",
                    "mechanism_family",
                    "metric",
                    "summary",
                    "recommended_action",
                    "confidence",
                    "reason_codes",
                ),
                limit=6,
            ),
            "policy": _project_generic_value(payload.get("policy")),
        }
    )
    if len(compact) <= 4:
        return ""
    rendered = json.dumps(compact, indent=2, sort_keys=True, default=str)
    return (
        "Problem-owned measurement/noise/opportunity diagnostics for proposal "
        "planning only. These are tainted status diagnostics, excluded from "
        "DecisionFeatures, and must not be treated as promotion evidence. "
        "Validation/frozen per-case detail, raw calibration rows, BKS/gap "
        "details, LLM text, prompt ratios, and raw cross-branch lessons are "
        "intentionally omitted.\n"
        f"{rendered}"
    )


def _compact_portfolio_steering(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return _drop_empty(
        {
            "schema_version": "compact_portfolio_steering.v1",
            "source_schema_version": value.get("schema_version"),
            "taint": "proposal_research_feedback",
            "proposal_visibility_only": value.get("proposal_visibility_only"),
            "decision_features_excluded": value.get("decision_features_excluded"),
            "summary": _project_mapping(
                value.get("summary"),
                fields=(
                    "signature_count",
                    "branch_count",
                    "cluster_count",
                    "no_effect_lesson_count",
                    "outcome_patterns",
                ),
            ),
            "top_no_effect_lessons": _project_items(
                value.get("no_effect_lessons"),
                fields=(
                    "lesson_type",
                    "source_cluster_id",
                    "branch_ids",
                    "evidence_basis",
                    "required_contrast_dimensions",
                    "recommended_action",
                    "same_branch_refinement_allowed",
                    "sibling_duplication_allowed",
                    "reason_codes",
                ),
                accepted_types={"no_effect_plateau"},
                limit=4,
            ),
            "avoid_clusters": _project_items(
                _avoid_portfolio_clusters(value.get("clusters")),
                fields=(
                    "cluster_id",
                    "cluster_type",
                    "branch_ids",
                    "branch_count",
                    "shared_signature",
                    "outcome_patterns",
                    "activation_statuses",
                    "effect_statuses",
                    "runtime_evidence_statuses",
                    "cluster_signal",
                    "recommended_action",
                ),
                limit=4,
            ),
            "opportunity_gaps": _project_items(
                value.get("opportunity_gaps"),
                fields=(
                    "gap_type",
                    "recommended_action",
                    "priority",
                    "basis",
                    "reason_codes",
                    "confidence",
                ),
                limit=4,
            ),
            "family_saturation_summary": _compact_family_saturation_summary(
                value.get("family_saturation_summary")
            ),
        }
    )


def _compact_family_saturation_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return _drop_empty(
        {
            "schema_version": value.get("schema_version"),
            "visibility_marker": value.get("visibility_marker"),
            "proposal_visibility_only": value.get("proposal_visibility_only"),
            "advisory_only": value.get("advisory_only"),
            "decision_features_excluded": value.get("decision_features_excluded"),
            "decision_input_policy": value.get("decision_input_policy"),
            "grouping_keys": _project_generic_value(value.get("grouping_keys")),
            "saturated_family_count": value.get("saturated_family_count"),
            "summaries": _project_items(
                value.get("summaries"),
                fields=(
                    "mechanism_family",
                    "intervention_type",
                    "surface",
                    "attempt_count",
                    "branch_count",
                    "outcome_tier_counts",
                    "case_level_counts",
                    "lifecycle_counts",
                    "advisory_label",
                    "proposal_advisory",
                    "reason_codes",
                ),
                limit=6,
            ),
        }
    )


def _avoid_portfolio_clusters(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    clusters: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        if raw.get("cluster_signal") in {
            "no_effect_plateau",
            "non_positive_cluster",
            "activation_gap",
        } or raw.get("recommended_action") in {"avoid", "diversify", "bridge"}:
            clusters.append(dict(raw))
    return clusters


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


def _active_branch_lesson_usage_requirement(value: Any) -> bool:
    if not isinstance(value, Mapping) or value.get("required") is not True:
        return False
    if value.get("schema_version") != "branch_lesson_usage_requirement.v1":
        return False
    for key, child in value.items():
        if key in {"schema_version", "required"}:
            continue
        if _present(child):
            return True
    return False


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


__all__ = [
    "HypothesisContextProfile",
    "derive_hypothesis_context_profile",
    "filter_hypothesis_context_for_prompt",
]
