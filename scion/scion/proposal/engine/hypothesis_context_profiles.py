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
        "research_shape_diagnostics",
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
_PROMOTED_ADAPTER_DIAGNOSTIC_KEYS = frozenset(
    {
        "measurement_context",
        "screening_headroom",
        "default_avoid_directions",
        "measurable_opportunity_classes",
        "mechanism_effect_ranking",
        "opportunity_diagnostics",
        "policy",
        "taint",
        "proposal_visibility_only",
        "decision_features_excluded",
    }
)


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
            "proposal_visibility_only": True,
            "decision_input_policy": "excluded_from_decision_features",
            "near_duplicate_hints": _mechanism_signal_items(
                payload.get("similarity_hints"),
                accepted_types={"near_duplicate", "saturated_family"},
            ),
            "avoid_hints": _mechanism_signal_items(
                payload.get("avoid_bridge_guidance"),
            ),
            "opportunity_hints": _mechanism_signal_items(
                payload.get("opportunity_gaps"),
            ),
            "lesson_hints": _mechanism_signal_items(
                payload.get("lesson_cards") or payload.get("lessons"),
            ),
            "branch_lessons": _mechanism_signal_items(
                payload.get("branch_lesson_records"),
            ),
            "cluster_hints": _mechanism_signal_items(
                _portfolio_clusters(payload.get("portfolio_steering")),
            ),
            "family_saturation_hints": _mechanism_signal_items(
                payload.get("family_saturation_summary")
                or _portfolio_family_saturation(payload.get("portfolio_steering")),
            ),
            "novelty_pressure": _project_mapping(
                payload.get("novelty_pressure"),
                fields=(
                    "policy",
                    "pressure",
                    "recommended_action",
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


def _mechanism_signal_items(
    value: Any,
    *,
    accepted_types: set[str] | None = None,
    limit: int | None = None,
    enforce_limit: bool = False,
) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        if isinstance(value.get("summaries"), (list, tuple)):
            value = value.get("summaries")
        else:
            value = (value,)
    if not isinstance(value, (list, tuple)):
        return []
    items: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        hint_type = str(raw.get("hint_type") or raw.get("lesson_type") or "")
        if accepted_types is not None and hint_type not in accepted_types:
            continue
        projected = _mechanism_signal_item(raw)
        if projected:
            items.append(projected)
    return items


def _mechanism_signal_item(raw: Mapping[str, Any]) -> dict[str, Any]:
    signature = _compact_signal_signature(
        raw.get("shared_signature")
        or raw.get("signature")
        or raw.get("source_signature")
        or raw
    )
    evidence = _compact_signal_evidence(raw.get("evidence_basis") or raw)
    return _drop_empty(
        {
            "id": _first_present(
                raw,
                ("lesson_id", "cluster_id", "hint_id", "record_id"),
            ),
            "type": _first_present(
                raw,
                (
                    "hint_type",
                    "lesson_type",
                    "lesson_role",
                    "cluster_type",
                    "opportunity_type",
                    "gap_type",
                    "guidance_type",
                    "failure_mode",
                ),
            ),
            "signature": signature,
            "summary": _short_signal_text(
                _first_present(
                    raw,
                    (
                        "summary",
                        "proposal_guidance",
                        "proposal_advisory",
                        "recommended_action",
                        "cluster_signal",
                        "advisory_label",
                    ),
                )
            ),
            "guidance": _short_signal_text(
                _first_present(
                    raw,
                    ("recommended_action", "proposal_guidance", "proposal_advisory"),
                )
            ),
            "signal": _short_signal_text(
                _first_present(raw, ("cluster_signal", "advisory_label")),
            ),
            "role": _short_signal_text(raw.get("lesson_role")),
            "evidence": evidence,
            "maturity": _short_signal_text(
                _first_present(
                    raw,
                    (
                        "maturity",
                        "evidence_strength",
                        "transferability",
                        "confidence",
                        "priority",
                    ),
                ),
            ),
            "branches": _short_sequence(
                raw.get("branch_ids") or raw.get("source_branch_ids")
            ),
        }
    )


def _compact_signal_signature(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    fields = (
        "change_locus",
        "surface",
        "target_file",
        "action",
        "mechanism_family",
        "mechanism_id",
        "intervention_type",
    )
    return _drop_empty(
        {
            field: _short_signal_text(value.get(field))
            for field in fields
            if value.get(field) not in (None, "", [], {}, ())
        }
    )


def _compact_signal_evidence(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    evidence = _drop_empty(
        {
            "count": _first_present(
                value,
                (
                    "evidence_count",
                    "attempt_count",
                    "branch_count",
                    "lesson_count",
                    "signature_count",
                    "cluster_count",
                ),
            ),
            "outcome_patterns": _project_generic_value(
                value.get("outcome_patterns")
            ),
            "activation_statuses": _project_generic_value(
                value.get("activation_statuses")
            ),
            "effect_statuses": _project_generic_value(value.get("effect_statuses")),
            "runtime_evidence_statuses": _project_generic_value(
                value.get("runtime_evidence_statuses")
            ),
            "case_level_counts": _project_generic_value(
                value.get("case_level_counts")
            ),
            "outcome_tier_counts": _project_generic_value(
                value.get("outcome_tier_counts")
            ),
            "lifecycle_counts": _project_generic_value(value.get("lifecycle_counts")),
            "basis": _short_signal_text(value.get("basis")),
        }
    )
    if not evidence:
        source_branches = value.get("source_branch_ids") or value.get("branch_ids")
        if isinstance(source_branches, (list, tuple)):
            evidence["count"] = len(source_branches)
    return evidence


def _portfolio_clusters(value: Any) -> list[Any]:
    if not isinstance(value, Mapping):
        return []
    clusters = value.get("clusters")
    if isinstance(clusters, (list, tuple)):
        return list(clusters)
    return []


def _portfolio_family_saturation(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return {}
    return value.get("family_saturation_summary")


def _first_present(value: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        item = value.get(key)
        if _present(item):
            return item
    return ""


def _short_sequence(
    value: Any,
    *,
    limit: int | None = None,
    enforce_limit: bool = False,
) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        return []
    return [
        _short_signal_text(item)
        for item in value
        if _present(item)
    ]


def _short_signal_text(
    value: Any,
    *,
    max_chars: int | None = None,
    enforce_max_chars: bool = False,
) -> str:
    if isinstance(value, (dict, list, tuple)):
        rendered = json.dumps(_project_generic_value(value), sort_keys=True, default=str)
    else:
        rendered = str(value or "")
    text = re.sub(r"\s+", " ", rendered).strip()
    return text


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
            "measurement_context": _project_mapping(
                payload.get("measurement_context"),
                fields=(
                    "runtime_model",
                    "pairing_validity",
                    "metric",
                    "practical_screen_delta",
                    "practical_validate_delta",
                    "screening_mde_at_power_80",
                    "recommended_min_seeds",
                    "false_pass_rate_at_current_gate",
                    "interpretation",
                ),
            ),
            "screening_headroom": _project_mapping(
                payload.get("screening_headroom"),
                fields=(
                    "scope",
                    "metric",
                    "case_count",
                    "gap_pct_min",
                    "gap_pct_max",
                    "case_count_gap_pct_at_least_3",
                    "case_details_omitted",
                    "planning_use",
                ),
            ),
            "default_avoid_directions": _short_sequence(
                payload.get("default_avoid_directions")
            ),
            "measurable_opportunity_classes": _project_items(
                payload.get("measurable_opportunity_classes"),
                fields=(
                    "mechanism_family",
                    "required_evidence",
                    "seed_report",
                    "confidence",
                    "reason_codes",
                ),
            ),
            "mechanism_effect_ranking": _project_items(
                payload.get("mechanism_effect_ranking"),
                fields=(
                    "rank",
                    "mechanism_family",
                    "evidence_status",
                    "opportunity_status",
                    "effect_status",
                    "objective_effect_status",
                    "summary",
                    "recommended_action",
                    "confidence",
                    "reason_codes",
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
            ),
            "adapter_diagnostics": _project_adapter_diagnostics(
                payload.get("adapter_diagnostics")
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


def _project_items(
    value: Any,
    *,
    fields: tuple[str, ...],
    accepted_types: set[str] | None = None,
    limit: int | None = None,
    enforce_limit: bool = False,
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


def _project_adapter_diagnostics(value: Any) -> Any:
    projected = _project_generic_value(value)
    if not isinstance(projected, Mapping):
        return projected
    return _drop_empty(
        {
            key: child
            for key, child in projected.items()
            if key not in _PROMOTED_ADAPTER_DIAGNOSTIC_KEYS
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
        projected = [_project_generic_value(item) for item in value]
        return [item for item in projected if _present(item)]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _allowed_generic_key(key: str) -> bool:
    lowered = key.lower()
    blocked_fragments = (
        "audit",
        "metadata",
        "session",
        "payload",
        "raw_metrics",
        "raw_pair",
        "pair_rows",
        "pair_evidence",
        "raw_calibration",
        "calibration_pair",
        "bks",
        "holdout",
        "validation",
        "frozen",
        "prompt_ratio",
        "llm_text",
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
