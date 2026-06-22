"""Shared prepared prompt/context audit helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


RESEARCH_FOCUS_PROJECTION_SUMMARY_SCHEMA = (
    "scion.prepared_research_focus_projection_summary.v1"
)
RESEARCH_FOCUS_PROMPT_SUMMARY_SCHEMA = (
    "scion.prepared_research_focus_prompt_summary.v1"
)
PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_SUMMARY_SCHEMA = (
    "scion.problem_measurement_diagnostics_prompt_summary.v1"
)
RESEARCH_SHAPE_PROMPT_SUMMARY_SCHEMA = (
    "scion.prepared_research_shape_prompt_summary.v1"
)
ACTIVE_SUBJECT_CODE_CONSTRAINTS_PROMPT_SUMMARY_SCHEMA = (
    "scion.active_subject_code_constraints_prompt_summary.v1"
)
PROBLEM_MEASUREMENT_DIAGNOSTICS_FORBIDDEN_PROMPT_TOKENS = (
    "bks_gap_details",
    "hidden-bks",
    "validation_case_details",
    "frozen_case_details",
    "raw_pair_rows",
    "raw_calibration_pair_rows",
    "prompt_ratios",
    "llm_text",
)


def active_subject_code_constraints_prompt_summary(
    *,
    problem_v1_path: Path | str | None,
    problem_family: str,
    surface: str,
) -> dict[str, Any]:
    """Summarize active subject code constraints that reach code prompts."""

    family = str(problem_family or "").strip()
    surface_name = str(surface or "").strip()
    problem_path = Path(problem_v1_path).expanduser() if problem_v1_path else None
    problem_path = (
        problem_path.resolve()
        if problem_path is not None and problem_path.exists()
        else None
    )
    base = {
        "schema_version": ACTIVE_SUBJECT_CODE_CONSTRAINTS_PROMPT_SUMMARY_SCHEMA,
        "problem_family": family,
        "surface": surface_name,
        "problem_v1_path": str(problem_path) if problem_path else "",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_payload_excluded": True,
    }
    if family not in {"cvrp", "warehouse_delivery"}:
        return {**base, "available": False, "reason": "unsupported_problem_family"}
    if problem_path is None:
        return {**base, "available": False, "reason": "problem_v1_not_found"}

    try:
        from scion.problem.bridge import load_problem_spec_v1_from_yaml
        from scion.problem.loader import load_problem_adapter
        from scion.problem.providers import active_subject_code_constraints_payload
        from scion.proposal.engine.code_prompts import _split_code_context

        spec = load_problem_spec_v1_from_yaml(problem_path)
        adapter = load_problem_adapter(spec)
        payload = active_subject_code_constraints_payload(
            problem_spec=spec,
            adapter=adapter,
            surface=surface_name,
        )
        system_blocks, user_prompt = _split_code_context(
            _minimal_code_constraints_context(
                problem_family=family,
                surface=surface_name,
                payload=payload,
            )
        )
        rendered_prompt = "\n".join(
            str(block.get("text") or "")
            for block in system_blocks
            if isinstance(block, dict)
        )
        rendered_prompt = f"{rendered_prompt}\n{user_prompt}"
    except Exception as exc:  # pragma: no cover - surfaced as readiness detail.
        return {
            **base,
            "available": False,
            "reason": "prompt_bridge_error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    constraints = payload.get("constraints")
    object_model_hints = payload.get("object_model_hints")
    api_contracts = payload.get("api_contracts")
    forbidden_patterns = payload.get("forbidden_patterns")
    constraint_ids = _rendered_constraint_item_counts(rendered_prompt, constraints)
    object_model_hint_ids = _rendered_constraint_item_counts(
        rendered_prompt,
        object_model_hints,
    )
    api_contract_ids = _rendered_constraint_item_counts(rendered_prompt, api_contracts)
    forbidden_pattern_ids = _rendered_constraint_item_counts(
        rendered_prompt,
        forbidden_patterns,
    )
    rendered_lower = rendered_prompt.lower()
    version = str(payload.get("version") or "").strip()
    subject_id = str(payload.get("subject_id") or "").strip()
    summary = {
        **base,
        "payload_version": version,
        "subject_id": subject_id,
        "prompt_section_present": (
            "## Active Subject Code Constraints" in rendered_prompt
        ),
        "compact_prompt_value_present": bool(version and version in rendered_prompt),
        "payload_version_present": bool(version and version in rendered_prompt),
        "subject_id_present": bool(subject_id and subject_id in rendered_prompt),
        "surface_present": bool(surface_name and surface_name in rendered_prompt),
        "decision_features_exclusion_present": (
            "excluded from DecisionFeatures" in rendered_prompt
            or "excluded_from_decision_features" in rendered_prompt
        ),
        "constraint_count": _sequence_count(constraints),
        "constraint_id_rendered_count": constraint_ids["rendered_count"],
        "constraint_ids_all_present": constraint_ids["all_present"],
        "object_model_hint_count": _sequence_count(object_model_hints),
        "object_model_hint_id_rendered_count": object_model_hint_ids[
            "rendered_count"
        ],
        "object_model_hint_ids_all_present": object_model_hint_ids["all_present"],
        "api_contract_count": _sequence_count(api_contracts),
        "api_contract_id_rendered_count": api_contract_ids["rendered_count"],
        "api_contract_ids_all_present": api_contract_ids["all_present"],
        "forbidden_pattern_count": _sequence_count(forbidden_patterns),
        "forbidden_pattern_rendered_count": forbidden_pattern_ids[
            "rendered_count"
        ],
        "forbidden_patterns_all_present": forbidden_pattern_ids["all_present"],
        "large_twoopt_runtime_guard_present": (
            family == "cvrp"
            and "large_instance_two_opt_runtime_guard" in rendered_prompt
        ),
        "unbounded_twoopt_reject_present": (
            family == "cvrp"
            and "UNBOUNDED_TWO_OPT_DEFAULT_REJECT" in rendered_prompt
        ),
        "warehouse_validation_transfer_diagnostics_present": (
            family == "warehouse_delivery"
            and "validation_transfer_diagnostics" in rendered_prompt
        ),
        "warehouse_lexicographic_guard_present": (
            family == "warehouse_delivery"
            and "lexicographic" in rendered_lower
        ),
    }
    required_true_fields = [
        "prompt_section_present",
        "compact_prompt_value_present",
        "payload_version_present",
        "subject_id_present",
        "surface_present",
        "decision_features_exclusion_present",
        "constraint_ids_all_present",
    ]
    if summary["object_model_hint_count"]:
        required_true_fields.append("object_model_hint_ids_all_present")
    if summary["api_contract_count"]:
        required_true_fields.append("api_contract_ids_all_present")
    if summary["forbidden_pattern_count"]:
        required_true_fields.append("forbidden_patterns_all_present")
    if family == "cvrp":
        required_true_fields.extend(
            [
                "large_twoopt_runtime_guard_present",
                "unbounded_twoopt_reject_present",
            ]
        )
    elif family == "warehouse_delivery":
        required_true_fields.extend(
            [
                "warehouse_validation_transfer_diagnostics_present",
                "warehouse_lexicographic_guard_present",
            ]
        )
    available = (
        bool(payload)
        and bool(version)
        and all(summary[field] is True for field in required_true_fields)
    )
    return {
        **summary,
        "available": available,
        "reason": "ok" if available else "missing_code_prompt_projection",
    }


def research_shape_prompt_summary(
    *,
    campaign_summary: dict[str, Any],
    campaign_status: dict[str, Any],
) -> dict[str, Any]:
    """Summarize copied research-shape diagnostics that reach prompts."""

    payload, source = _research_shape_payload_from_campaign(
        campaign_summary=campaign_summary,
        campaign_status=campaign_status,
    )
    if not payload:
        payload = _representative_research_shape_payload()
        source = "representative_static_projection"
    base = {
        "schema_version": RESEARCH_SHAPE_PROMPT_SUMMARY_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
        "payload_source": source,
    }
    try:
        from scion.proposal.engine.hypothesis_context_profiles import (
            filter_hypothesis_context_for_prompt,
        )
        from scion.proposal.engine.hypothesis_prompts import (
            _split_hypothesis_context,
        )

        filtered = filter_hypothesis_context_for_prompt(
            _minimal_research_shape_context(payload)
        )
        compact = str(filtered.get("research_shape_diagnostics") or "")
        system_blocks, user_prompt = _split_hypothesis_context(dict(filtered))
        rendered_prompt = "\n".join(
            str(block.get("text") or "")
            for block in system_blocks
            if isinstance(block, dict)
        )
        rendered_prompt = f"{rendered_prompt}\n{user_prompt}"
    except Exception as exc:  # pragma: no cover - surfaced as readiness detail.
        return {
            **base,
            "available": False,
            "reason": "prompt_bridge_error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    rendered_lower = rendered_prompt.lower()
    forbidden_present = [
        token
        for token in PROBLEM_MEASUREMENT_DIAGNOSTICS_FORBIDDEN_PROMPT_TOKENS
        if token in rendered_lower
    ]
    schema_version = str(payload.get("schema_version") or "")
    summary = {
        **base,
        "payload_schema_version": schema_version,
        "copied_campaign_payload_present": (
            source != "representative_static_projection"
        ),
        "prompt_section_present": "## Compact Research Signals" in rendered_prompt,
        "compact_prompt_value_present": bool(compact.strip()),
        "research_shape_key_present": "research_shape" in rendered_prompt,
        "payload_schema_present": (
            bool(schema_version) and schema_version in rendered_prompt
        ),
        "branch_depth_signal_present": any(
            token in rendered_prompt
            for token in (
                "branch_depth_distribution",
                "current_branch_depth",
                "max_branch_depth",
            )
        ),
        "mechanism_family_signal_present": "mechanism_family" in rendered_prompt,
        "shape_guidance_present": any(
            token in rendered_prompt
            for token in (
                "proposal_guidance",
                "active_research_shape_signal",
                "shape_label",
            )
        ),
        "decision_features_exclusion_present": (
            "excluded from DecisionFeatures" in rendered_prompt
            or "excluded_from_decision_features" in rendered_prompt
        ),
        "forbidden_prompt_tokens_present": forbidden_present,
    }
    required_true_fields = [
        "prompt_section_present",
        "compact_prompt_value_present",
        "research_shape_key_present",
        "payload_schema_present",
        "branch_depth_signal_present",
        "mechanism_family_signal_present",
        "shape_guidance_present",
        "decision_features_exclusion_present",
    ]
    available = (
        bool(payload)
        and not forbidden_present
        and all(summary[field] is True for field in required_true_fields)
    )
    return {
        **summary,
        "available": available,
        "reason": "ok" if available else "missing_prompt_projection",
    }


def research_focus_projection_summary(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Summarize manifest research focus fields that reach launch prompts."""

    research_focus = _mapping_or_empty(manifest.get("research_focus"))
    problem_family = str(manifest.get("problem_family") or "").strip()
    base = {
        "schema_version": RESEARCH_FOCUS_PROJECTION_SUMMARY_SCHEMA,
        "problem_family": problem_family,
        "manifest_path": str(manifest_path),
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
    }
    if not research_focus:
        return {
            **base,
            "available": False,
            "reason": "missing_research_focus",
            "manifest_keys": [],
            "projected_keys": [],
            "required_projected_keys": [],
            "missing_projected_keys": [],
            "projected_paths": [],
            "required_projected_paths": [],
            "missing_projected_paths": [],
            "projected_path_count": 0,
        }
    try:
        from scion.proposal.context_manager.manager import (
            _project_launch_research_focus,
        )

        projected = _project_launch_research_focus(research_focus)
    except Exception as exc:  # pragma: no cover - surfaced as readiness detail.
        return {
            **base,
            "available": False,
            "reason": "projection_error",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "manifest_keys": sorted(research_focus),
            "projected_keys": [],
            "required_projected_keys": [],
            "missing_projected_keys": [],
            "projected_paths": [],
            "required_projected_paths": [],
            "missing_projected_paths": [],
            "projected_path_count": 0,
        }

    projected_dict = projected if isinstance(projected, dict) else {}
    required_keys = _required_research_focus_projection_keys(
        problem_family,
        research_focus,
    )
    missing_keys = [
        key
        for key in required_keys
        if key not in projected_dict or projected_dict.get(key) in ({}, [], "", None)
    ]
    required_paths = _required_research_focus_projection_paths(
        problem_family,
        research_focus,
    )
    projected_paths = _non_empty_leaf_paths(projected_dict)
    missing_paths = [
        path
        for path in required_paths
        if _path_value(projected_dict, path) in ({}, [], "", None)
    ]
    return {
        **base,
        "available": bool(projected_dict) and not missing_keys and not missing_paths,
        "reason": (
            "ok"
            if projected_dict and not missing_keys and not missing_paths
            else "missing_projection"
        ),
        "manifest_keys": sorted(research_focus),
        "projected_keys": sorted(projected_dict),
        "required_projected_keys": required_keys,
        "missing_projected_keys": missing_keys,
        "projected_paths": projected_paths,
        "required_projected_paths": required_paths,
        "missing_projected_paths": missing_paths,
        "projected_path_count": len(projected_paths),
        "projected_field_count": len(projected_dict),
        "manifest_field_count": len(research_focus),
    }


def research_focus_prompt_summary(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Summarize prepared research focus content that reaches prompts."""

    research_focus = _mapping_or_empty(manifest.get("research_focus"))
    problem_family = str(manifest.get("problem_family") or "").strip()
    base = {
        "schema_version": RESEARCH_FOCUS_PROMPT_SUMMARY_SCHEMA,
        "problem_family": problem_family,
        "manifest_path": str(manifest_path),
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
    }
    if not research_focus:
        return {
            **base,
            "available": False,
            "reason": "missing_research_focus",
            "rendered_required_paths": [],
            "missing_rendered_paths": [],
            "rendered_required_path_count": 0,
        }

    try:
        from scion.proposal.context_manager.manager import (
            _project_launch_research_focus,
        )
        from scion.proposal.engine.hypothesis_context_profiles import (
            filter_hypothesis_context_for_prompt,
        )
        from scion.proposal.engine.hypothesis_prompts import (
            _split_hypothesis_context,
        )

        projected = _project_launch_research_focus(research_focus)
        projected_dict = projected if isinstance(projected, dict) else {}
        launch_payload = _launch_research_focus_payload(
            manifest_path=manifest_path,
            manifest=manifest,
            projected_focus=projected_dict,
        )
        filtered = filter_hypothesis_context_for_prompt(
            _minimal_research_focus_context(
                problem_family=problem_family,
                launch_research_focus=launch_payload,
            )
        )
        compact = str(filtered.get("launch_research_focus") or "")
        system_blocks, user_prompt = _split_hypothesis_context(dict(filtered))
        rendered_prompt = "\n".join(
            str(block.get("text") or "")
            for block in system_blocks
            if isinstance(block, dict)
        )
        rendered_prompt = f"{rendered_prompt}\n{user_prompt}"
    except Exception as exc:  # pragma: no cover - surfaced as readiness detail.
        return {
            **base,
            "available": False,
            "reason": "prompt_bridge_error",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "rendered_required_paths": [],
            "missing_rendered_paths": [],
            "rendered_required_path_count": 0,
        }

    required_paths = _required_research_focus_projection_paths(
        problem_family,
        research_focus,
    )
    rendered_required_paths = [
        path for path in required_paths if _prompt_contains_path(rendered_prompt, path)
    ]
    missing_rendered_paths = [
        path for path in required_paths if path not in rendered_required_paths
    ]
    rendered_lower = rendered_prompt.lower()
    forbidden_present = [
        token
        for token in PROBLEM_MEASUREMENT_DIAGNOSTICS_FORBIDDEN_PROMPT_TOKENS
        if token in rendered_lower
    ]
    required_evidence_counts = _rendered_sequence_item_counts(
        rendered_prompt,
        research_focus.get("required_evidence"),
    )
    default_avoid_counts = _rendered_sequence_item_counts(
        rendered_prompt,
        research_focus.get("default_avoid_directions"),
    )
    measurable_opportunity_counts = _rendered_sequence_item_counts(
        rendered_prompt,
        research_focus.get("measurable_opportunity_classes"),
    )
    large_twoopt = _mapping_or_empty(
        research_focus.get("large_instance_two_opt_constraints")
    )
    large_twoopt_implementation_counts = _rendered_sequence_item_counts(
        rendered_prompt,
        large_twoopt.get("implementation_constraints"),
    )
    large_twoopt_pair_evidence_counts = _rendered_sequence_item_counts(
        rendered_prompt,
        large_twoopt.get("required_pair_evidence"),
    )
    large_twoopt_reject_counts = _rendered_sequence_item_counts(
        rendered_prompt,
        large_twoopt.get("default_reject_directions"),
    )
    case_protection = _mapping_or_empty(
        research_focus.get("case_protection_requirements")
    )
    case_protection_rule_counts = _rendered_sequence_item_counts(
        rendered_prompt,
        case_protection.get("rules"),
    )
    case_protection_evidence_counts = _rendered_sequence_item_counts(
        rendered_prompt,
        case_protection.get("required_evidence"),
    )
    resume_continuity = _mapping_or_empty(
        research_focus.get("resume_continuity_requirements")
    )
    resume_continuity_fallback_counts = _rendered_sequence_item_counts(
        rendered_prompt,
        resume_continuity.get("fallback_sources"),
    )
    resume_continuity_rule_counts = _rendered_sequence_item_counts(
        rendered_prompt,
        resume_continuity.get("rules"),
    )
    resume_continuity_evidence_counts = _rendered_sequence_item_counts(
        rendered_prompt,
        resume_continuity.get("required_evidence"),
    )
    measurement = _mapping_or_empty(
        research_focus.get("measurement_opportunity_diagnostics")
    )
    calibration = _mapping_or_empty(measurement.get("calibration"))
    calibration_source_artifact = _mapping_or_empty(
        calibration.get("source_artifact")
    )
    calibration_run = _mapping_or_empty(calibration.get("calibration_run"))
    calibration_runtime_policy = _mapping_or_empty(
        calibration_run.get("runtime_policy")
    )
    calibration_source_sha256 = str(
        calibration_source_artifact.get("sha256") or ""
    ).strip()
    calibration_run_action = str(
        calibration_run.get("action")
        or calibration.get("calibration_run_action")
        or ""
    ).strip()
    calibration_runtime_policy_name = str(
        calibration_runtime_policy.get("selected_policy") or ""
    ).strip()
    empty_sequence_counts = {
        "item_count": 0,
        "rendered_count": 0,
        "all_present": False,
    }
    warehouse_required_evidence_counts = (
        required_evidence_counts
        if problem_family == "warehouse_delivery"
        else empty_sequence_counts
    )
    warehouse_default_avoid_counts = (
        default_avoid_counts
        if problem_family == "warehouse_delivery"
        else empty_sequence_counts
    )
    cvrp_measurable_opportunity_counts = (
        measurable_opportunity_counts
        if problem_family == "cvrp"
        else empty_sequence_counts
    )
    cvrp_required_evidence_counts = (
        required_evidence_counts
        if problem_family == "cvrp"
        else empty_sequence_counts
    )
    cvrp_large_twoopt_implementation_counts = (
        large_twoopt_implementation_counts
        if problem_family == "cvrp"
        else empty_sequence_counts
    )
    cvrp_large_twoopt_pair_evidence_counts = (
        large_twoopt_pair_evidence_counts
        if problem_family == "cvrp"
        else empty_sequence_counts
    )
    cvrp_large_twoopt_reject_counts = (
        large_twoopt_reject_counts
        if problem_family == "cvrp"
        else empty_sequence_counts
    )
    cvrp_case_protection_rule_counts = (
        case_protection_rule_counts
        if problem_family == "cvrp"
        else empty_sequence_counts
    )
    cvrp_case_protection_evidence_counts = (
        case_protection_evidence_counts
        if problem_family == "cvrp"
        else empty_sequence_counts
    )
    cvrp_resume_continuity_fallback_counts = (
        resume_continuity_fallback_counts
        if problem_family == "cvrp"
        else empty_sequence_counts
    )
    cvrp_resume_continuity_rule_counts = (
        resume_continuity_rule_counts
        if problem_family == "cvrp"
        else empty_sequence_counts
    )
    cvrp_resume_continuity_evidence_counts = (
        resume_continuity_evidence_counts
        if problem_family == "cvrp"
        else empty_sequence_counts
    )
    summary = {
        **base,
        "launch_focus_schema_present": (
            "scion.launch_research_focus_prompt.v1" in rendered_prompt
        ),
        "launch_focus_taint_present": (
            "prepared_launch_research_focus" in rendered_prompt
        ),
        "prompt_section_present": "## Compact Research Signals" in rendered_prompt,
        "compact_prompt_value_present": bool(compact.strip()),
        "launch_research_focus_key_present": "launch_research_focus" in rendered_prompt,
        "decision_features_exclusion_present": (
            "excluded from DecisionFeatures" in rendered_prompt
            or "excluded_from_decision_features" in rendered_prompt
        ),
        "manifest_path_present": str(manifest_path) in rendered_prompt,
        "rendered_required_paths": rendered_required_paths,
        "missing_rendered_paths": missing_rendered_paths,
        "rendered_required_path_count": len(rendered_required_paths),
        "required_rendered_path_count": len(required_paths),
        "forbidden_prompt_tokens_present": forbidden_present,
        "warehouse_v2_followup_present": (
            problem_family == "warehouse_delivery"
            and (
                "champion v2" in rendered_lower
                or "champion-v2" in rendered_lower
            )
        ),
        "warehouse_current_question_present": (
            problem_family == "warehouse_delivery"
            and "current_question" in rendered_prompt
        ),
        "warehouse_required_evidence_present": (
            problem_family == "warehouse_delivery"
            and "required_evidence" in rendered_prompt
        ),
        "warehouse_required_evidence_item_count": warehouse_required_evidence_counts[
            "item_count"
        ],
        "warehouse_required_evidence_rendered_count": warehouse_required_evidence_counts[
            "rendered_count"
        ],
        "warehouse_required_evidence_all_present": warehouse_required_evidence_counts[
            "all_present"
        ],
        "warehouse_avoid_directions_present": (
            problem_family == "warehouse_delivery"
            and "default_avoid_directions" in rendered_prompt
        ),
        "warehouse_default_avoid_direction_item_count": warehouse_default_avoid_counts[
            "item_count"
        ],
        "warehouse_default_avoid_direction_rendered_count": warehouse_default_avoid_counts[
            "rendered_count"
        ],
        "warehouse_default_avoid_direction_all_present": warehouse_default_avoid_counts[
            "all_present"
        ],
        "warehouse_measurement_handoff_present": (
            problem_family == "warehouse_delivery"
            and "measurement_opportunity_diagnostics" in rendered_prompt
            and "runtime_model" in rendered_prompt
        ),
        "warehouse_measurement_calibration_source_artifact_present": (
            problem_family == "warehouse_delivery"
            and bool(calibration_source_sha256)
            and "source_artifact" in rendered_prompt
            and "sha256" in rendered_prompt
            and calibration_source_sha256 in rendered_prompt
        ),
        "warehouse_measurement_calibration_run_present": (
            problem_family == "warehouse_delivery"
            and bool(calibration_run)
            and "calibration_run" in rendered_prompt
            and (
                not calibration_run_action
                or calibration_run_action in rendered_prompt
            )
        ),
        "warehouse_measurement_transfer_risk_present": (
            problem_family == "warehouse_delivery"
            and "transfer_risk" in rendered_prompt
            and "latest_formal_no_gain_pattern" in rendered_prompt
        ),
        "warehouse_measurement_required_diagnostics_present": (
            problem_family == "warehouse_delivery"
            and "required_diagnostics" in rendered_prompt
            and "operator_invocations" in rendered_prompt
            and "cost_delta_sum" in rendered_prompt
        ),
        "warehouse_measurement_followup_opportunity_present": (
            problem_family == "warehouse_delivery"
            and "opportunity_diagnostics" in rendered_prompt
            and "validation_transfer_continuation" in rendered_prompt
        ),
        "warehouse_measurement_plateau_guard_present": (
            problem_family == "warehouse_delivery"
            and "PLATEAU_REQUIRES_PROTOCOL_EVIDENCE" in rendered_prompt
            and "SCREENING_ONLY_NOT_PLATEAU_EVIDENCE" in rendered_prompt
        ),
        "warehouse_measurement_opportunity_diagnostic_count": _sequence_count(
            measurement.get("opportunity_diagnostics")
        )
        if problem_family == "warehouse_delivery"
        else 0,
        "cvrp_case_protection_present": (
            problem_family == "cvrp"
            and "CMT2" in rendered_prompt
            and "CMT4" in rendered_prompt
        ),
        "cvrp_next_required_direction_present": (
            problem_family == "cvrp"
            and "next_required_direction" in rendered_prompt
            and "large_instance_intra_route_two_opt_seed" in rendered_prompt
        ),
        "cvrp_bounded_twoopt_present": (
            problem_family == "cvrp"
            and "large_instance_two_opt_constraints" in rendered_prompt
            and (
                "deadline" in rendered_lower
                or "remaining-time" in rendered_lower
                or "remaining time" in rendered_lower
            )
        ),
        "cvrp_direct_effect_rules_present": (
            problem_family == "cvrp"
            and "route_merge_exception_rule" in rendered_prompt
            and "construction_seed_rule" in rendered_prompt
        ),
        "cvrp_measurement_handoff_present": (
            problem_family == "cvrp"
            and "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA" in rendered_prompt
        ),
        "cvrp_measurement_calibration_source_artifact_present": (
            problem_family == "cvrp"
            and bool(calibration_source_sha256)
            and "source_artifact" in rendered_prompt
            and "sha256" in rendered_prompt
            and calibration_source_sha256 in rendered_prompt
        ),
        "cvrp_measurement_calibration_run_present": (
            problem_family == "cvrp"
            and bool(calibration_run)
            and "calibration_run" in rendered_prompt
        ),
        "cvrp_measurement_calibration_runtime_policy_present": (
            problem_family == "cvrp"
            and bool(calibration_runtime_policy)
            and "runtime_policy" in rendered_prompt
            and (
                not calibration_runtime_policy_name
                or calibration_runtime_policy_name in rendered_prompt
            )
        ),
        "cvrp_required_evidence_present": (
            problem_family == "cvrp"
            and "required_evidence" in rendered_prompt
        ),
        "cvrp_required_evidence_item_count": cvrp_required_evidence_counts[
            "item_count"
        ],
        "cvrp_required_evidence_rendered_count": cvrp_required_evidence_counts[
            "rendered_count"
        ],
        "cvrp_required_evidence_all_present": cvrp_required_evidence_counts[
            "all_present"
        ],
        "cvrp_measurement_screening_headroom_present": (
            problem_family == "cvrp"
            and "screening_headroom" in rendered_prompt
            and "case_count_gap_pct_at_least_3" in rendered_prompt
        ),
        "cvrp_measurement_measurable_opportunities_present": (
            problem_family == "cvrp"
            and "measurement_opportunity_diagnostics" in rendered_prompt
            and "measurable_opportunity_classes" in rendered_prompt
        ),
        "cvrp_measurement_mechanism_ranking_present": (
            problem_family == "cvrp"
            and "mechanism_effect_ranking" in rendered_prompt
            and "highest_current_followup" in rendered_prompt
        ),
        "cvrp_measurement_opportunity_diagnostics_present": (
            problem_family == "cvrp"
            and "opportunity_diagnostics" in rendered_prompt
            and "measurement_power" in rendered_prompt
        ),
        "cvrp_measurement_mechanism_rank_count": _sequence_count(
            measurement.get("mechanism_effect_ranking")
        )
        if problem_family == "cvrp"
        else 0,
        "cvrp_measurement_opportunity_diagnostic_count": _sequence_count(
            measurement.get("opportunity_diagnostics")
        )
        if problem_family == "cvrp"
        else 0,
        "cvrp_measurable_opportunity_class_item_count": (
            cvrp_measurable_opportunity_counts["item_count"]
        ),
        "cvrp_measurable_opportunity_class_rendered_count": (
            cvrp_measurable_opportunity_counts["rendered_count"]
        ),
        "cvrp_measurable_opportunity_class_all_present": (
            cvrp_measurable_opportunity_counts["all_present"]
        ),
        "cvrp_large_twoopt_implementation_constraint_item_count": (
            cvrp_large_twoopt_implementation_counts["item_count"]
        ),
        "cvrp_large_twoopt_implementation_constraint_rendered_count": (
            cvrp_large_twoopt_implementation_counts["rendered_count"]
        ),
        "cvrp_large_twoopt_implementation_constraint_all_present": (
            cvrp_large_twoopt_implementation_counts["all_present"]
        ),
        "cvrp_large_twoopt_required_pair_evidence_item_count": (
            cvrp_large_twoopt_pair_evidence_counts["item_count"]
        ),
        "cvrp_large_twoopt_required_pair_evidence_rendered_count": (
            cvrp_large_twoopt_pair_evidence_counts["rendered_count"]
        ),
        "cvrp_large_twoopt_required_pair_evidence_all_present": (
            cvrp_large_twoopt_pair_evidence_counts["all_present"]
        ),
        "cvrp_large_twoopt_default_reject_direction_item_count": (
            cvrp_large_twoopt_reject_counts["item_count"]
        ),
        "cvrp_large_twoopt_default_reject_direction_rendered_count": (
            cvrp_large_twoopt_reject_counts["rendered_count"]
        ),
        "cvrp_large_twoopt_default_reject_direction_all_present": (
            cvrp_large_twoopt_reject_counts["all_present"]
        ),
        "cvrp_case_protection_rule_item_count": (
            cvrp_case_protection_rule_counts["item_count"]
        ),
        "cvrp_case_protection_rule_rendered_count": (
            cvrp_case_protection_rule_counts["rendered_count"]
        ),
        "cvrp_case_protection_rule_all_present": (
            cvrp_case_protection_rule_counts["all_present"]
        ),
        "cvrp_case_protection_required_evidence_item_count": (
            cvrp_case_protection_evidence_counts["item_count"]
        ),
        "cvrp_case_protection_required_evidence_rendered_count": (
            cvrp_case_protection_evidence_counts["rendered_count"]
        ),
        "cvrp_case_protection_required_evidence_all_present": (
            cvrp_case_protection_evidence_counts["all_present"]
        ),
        "cvrp_resume_continuity_present": (
            problem_family == "cvrp"
            and "resume_continuity_requirements" in rendered_prompt
            and "zero branch cards" in rendered_lower
            and "target-intent" in rendered_lower
            and "copied" in rendered_lower
        ),
        "cvrp_resume_continuity_fallback_source_item_count": (
            cvrp_resume_continuity_fallback_counts["item_count"]
        ),
        "cvrp_resume_continuity_fallback_source_rendered_count": (
            cvrp_resume_continuity_fallback_counts["rendered_count"]
        ),
        "cvrp_resume_continuity_fallback_source_all_present": (
            cvrp_resume_continuity_fallback_counts["all_present"]
        ),
        "cvrp_resume_continuity_rule_item_count": (
            cvrp_resume_continuity_rule_counts["item_count"]
        ),
        "cvrp_resume_continuity_rule_rendered_count": (
            cvrp_resume_continuity_rule_counts["rendered_count"]
        ),
        "cvrp_resume_continuity_rule_all_present": (
            cvrp_resume_continuity_rule_counts["all_present"]
        ),
        "cvrp_resume_continuity_required_evidence_item_count": (
            cvrp_resume_continuity_evidence_counts["item_count"]
        ),
        "cvrp_resume_continuity_required_evidence_rendered_count": (
            cvrp_resume_continuity_evidence_counts["rendered_count"]
        ),
        "cvrp_resume_continuity_required_evidence_all_present": (
            cvrp_resume_continuity_evidence_counts["all_present"]
        ),
    }
    required_true_fields = [
        "launch_focus_schema_present",
        "launch_focus_taint_present",
        "prompt_section_present",
        "compact_prompt_value_present",
        "launch_research_focus_key_present",
        "decision_features_exclusion_present",
        "manifest_path_present",
    ]
    if problem_family == "warehouse_delivery":
        if research_focus.get("accepted_checkpoint") not in ({}, [], "", None):
            required_true_fields.append("warehouse_v2_followup_present")
        if research_focus.get("current_question") not in ({}, [], "", None):
            required_true_fields.append("warehouse_current_question_present")
        if research_focus.get("required_evidence") not in ({}, [], "", None):
            required_true_fields.append("warehouse_required_evidence_present")
            required_true_fields.append("warehouse_required_evidence_all_present")
        if research_focus.get("default_avoid_directions") not in ({}, [], "", None):
            required_true_fields.append("warehouse_avoid_directions_present")
            required_true_fields.append("warehouse_default_avoid_direction_all_present")
        if (
            research_focus.get("measurement_opportunity_diagnostics")
            not in ({}, [], "", None)
        ):
            required_true_fields.append("warehouse_measurement_handoff_present")
            if calibration_source_artifact not in ({}, [], "", None):
                required_true_fields.append(
                    "warehouse_measurement_calibration_source_artifact_present"
                )
            if calibration_run not in ({}, [], "", None):
                required_true_fields.append(
                    "warehouse_measurement_calibration_run_present"
                )
            if measurement.get("transfer_risk") not in ({}, [], "", None):
                required_true_fields.append(
                    "warehouse_measurement_transfer_risk_present"
                )
            if measurement.get("required_diagnostics") not in ({}, [], "", None):
                required_true_fields.append(
                    "warehouse_measurement_required_diagnostics_present"
                )
            if measurement.get("opportunity_diagnostics") not in ({}, [], "", None):
                required_true_fields.append(
                    "warehouse_measurement_followup_opportunity_present"
                )
                required_true_fields.append(
                    "warehouse_measurement_plateau_guard_present"
                )
    elif problem_family == "cvrp":
        if research_focus.get("next_required_direction") not in ({}, [], "", None):
            required_true_fields.append("cvrp_next_required_direction_present")
        if research_focus.get("required_evidence") not in ({}, [], "", None):
            required_true_fields.append("cvrp_required_evidence_present")
            required_true_fields.append("cvrp_required_evidence_all_present")
        if research_focus.get("case_protection_requirements") not in (
            {},
            [],
            "",
            None,
        ):
            required_true_fields.append("cvrp_case_protection_present")
            required_true_fields.append("cvrp_case_protection_rule_all_present")
            required_true_fields.append(
                "cvrp_case_protection_required_evidence_all_present"
            )
        if research_focus.get("large_instance_two_opt_constraints") not in (
            {},
            [],
            "",
            None,
        ):
            required_true_fields.append("cvrp_bounded_twoopt_present")
            required_true_fields.append(
                "cvrp_large_twoopt_implementation_constraint_all_present"
            )
            required_true_fields.append(
                "cvrp_large_twoopt_required_pair_evidence_all_present"
            )
            required_true_fields.append(
                "cvrp_large_twoopt_default_reject_direction_all_present"
            )
        if research_focus.get("measurable_opportunity_classes") not in (
            {},
            [],
            "",
            None,
        ):
            required_true_fields.append(
                "cvrp_measurable_opportunity_class_all_present"
            )
        if (
            research_focus.get("route_merge_exception_rule")
            not in ({}, [], "", None)
            or research_focus.get("construction_seed_rule")
            not in ({}, [], "", None)
        ):
            required_true_fields.append("cvrp_direct_effect_rules_present")
        if research_focus.get("resume_continuity_requirements") not in (
            {},
            [],
            "",
            None,
        ):
            required_true_fields.append("cvrp_resume_continuity_present")
            required_true_fields.append(
                "cvrp_resume_continuity_fallback_source_all_present"
            )
            required_true_fields.append("cvrp_resume_continuity_rule_all_present")
            required_true_fields.append(
                "cvrp_resume_continuity_required_evidence_all_present"
            )
        if (
            research_focus.get("measurement_opportunity_diagnostics")
            not in ({}, [], "", None)
        ):
            required_true_fields.append("cvrp_measurement_handoff_present")
            if calibration_source_artifact not in ({}, [], "", None):
                required_true_fields.append(
                    "cvrp_measurement_calibration_source_artifact_present"
                )
            if calibration_run not in ({}, [], "", None):
                required_true_fields.append(
                    "cvrp_measurement_calibration_run_present"
                )
            if calibration_runtime_policy not in ({}, [], "", None):
                required_true_fields.append(
                    "cvrp_measurement_calibration_runtime_policy_present"
                )
            if measurement.get("screening_headroom") not in ({}, [], "", None):
                required_true_fields.append(
                    "cvrp_measurement_screening_headroom_present"
                )
            if measurement.get("measurable_opportunity_classes") not in (
                {},
                [],
                "",
                None,
            ):
                required_true_fields.append(
                    "cvrp_measurement_measurable_opportunities_present"
                )
            if measurement.get("mechanism_effect_ranking") not in (
                {},
                [],
                "",
                None,
            ):
                required_true_fields.append(
                    "cvrp_measurement_mechanism_ranking_present"
                )
            if measurement.get("opportunity_diagnostics") not in (
                {},
                [],
                "",
                None,
            ):
                required_true_fields.append(
                    "cvrp_measurement_opportunity_diagnostics_present"
                )
    available = (
        bool(projected_dict)
        and not missing_rendered_paths
        and not forbidden_present
        and all(summary[field] is True for field in required_true_fields)
    )
    return {
        **summary,
        "available": available,
        "reason": "ok" if available else "missing_prompt_projection",
    }


def problem_measurement_diagnostics_prompt_summary(
    *,
    problem_v1_path: Path | str | None,
    problem_family: str,
) -> dict[str, Any]:
    """Summarize problem-owned measurement diagnostics that reach prompts."""

    family = str(problem_family or "").strip()
    problem_path = Path(problem_v1_path).expanduser() if problem_v1_path else None
    problem_path = (
        problem_path.resolve()
        if problem_path is not None and problem_path.exists()
        else None
    )
    base = {
        "schema_version": PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_SUMMARY_SCHEMA,
        "problem_family": family,
        "problem_v1_path": str(problem_path) if problem_path else "",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_payload_excluded": True,
        "raw_prompt_excluded": True,
    }
    if family not in {"cvrp", "warehouse_delivery"}:
        return {**base, "available": False, "reason": "unsupported_problem_family"}
    if problem_path is None:
        return {**base, "available": False, "reason": "problem_v1_not_found"}

    try:
        from scion.problem.bridge import (
            legacy_problem_spec_from_v1,
            load_problem_spec_v1_from_yaml,
        )
        from scion.problem.loader import load_problem_adapter
        from scion.proposal.context_manager.manager import (
            _problem_measurement_diagnostics,
        )
        from scion.proposal.engine.hypothesis_context_profiles import (
            filter_hypothesis_context_for_prompt,
        )
        from scion.proposal.engine.hypothesis_prompts import (
            _split_hypothesis_context,
        )

        spec_v1 = load_problem_spec_v1_from_yaml(problem_path)
        legacy = legacy_problem_spec_from_v1(spec_v1)
        adapter = load_problem_adapter(spec_v1)
        payload = _problem_measurement_diagnostics(legacy, adapter=adapter)
        filtered = filter_hypothesis_context_for_prompt(
            _minimal_hypothesis_context(payload)
        )
        compact = str(
            filtered.get("problem_measurement_diagnostics")
            or filtered.get("compact_problem_measurement_diagnostics")
            or ""
        )
        system_blocks, user_prompt = _split_hypothesis_context(dict(filtered))
        rendered_prompt = "\n".join(
            str(block.get("text") or "")
            for block in system_blocks
            if isinstance(block, dict)
        )
        rendered_prompt = f"{rendered_prompt}\n{user_prompt}"
    except Exception as exc:  # pragma: no cover - surfaced as readiness detail.
        return {
            **base,
            "available": False,
            "reason": "prompt_bridge_error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    rendered_lower = rendered_prompt.lower()
    forbidden_present = [
        token
        for token in PROBLEM_MEASUREMENT_DIAGNOSTICS_FORBIDDEN_PROMPT_TOKENS
        if token in rendered_lower
    ]
    adapter_schema = _expected_adapter_diagnostic_schema(family)
    summary = {
        **base,
        "payload_schema_version": str(payload.get("schema_version") or ""),
        "adapter_schema_present": bool(
            adapter_schema and adapter_schema in rendered_prompt
        ),
        "prompt_section_present": "## Problem Measurement Diagnostics" in rendered_prompt,
        "compact_prompt_value_present": bool(compact.strip()),
        "problem_measurement_diagnostics_key_present": bool(
            filtered.get("problem_measurement_diagnostics")
        ),
        "screening_headroom_present": "screening_headroom" in rendered_prompt,
        "measurable_opportunity_classes_present": (
            "measurable_opportunity_classes" in rendered_prompt
        ),
        "mechanism_effect_ranking_present": (
            "mechanism_effect_ranking" in rendered_prompt
        ),
        "highest_current_followup_present": (
            "highest_current_followup" in rendered_prompt
        ),
        "decision_features_exclusion_present": (
            "excluded from DecisionFeatures" in rendered_prompt
            or "excluded_from_decision_features" in rendered_prompt
        ),
        "mechanism_rank_count": _sequence_count(
            payload.get("mechanism_effect_ranking")
        ),
        "opportunity_diagnostic_count": _sequence_count(
            payload.get("opportunity_diagnostics")
        ),
        "warehouse_transfer_risk_present": "transfer_risk" in rendered_prompt,
        "warehouse_required_diagnostics_present": all(
            token in rendered_prompt
            for token in (
                "operator_invocations",
                "split_delta_sum",
                "cost_delta_sum",
            )
        ),
        "warehouse_followup_opportunity_present": (
            "validation_transfer_continuation" in rendered_prompt
        ),
        "warehouse_plateau_guard_present": all(
            token in rendered_prompt
            for token in (
                "WAREHOUSE_V2_FOLLOWUP_CONTINUOUS_RESEARCH",
                "PLATEAU_REQUIRES_PROTOCOL_EVIDENCE",
                "SCREENING_ONLY_NOT_PLATEAU_EVIDENCE",
            )
        ),
        "warehouse_v2_followup_present": (
            "champion-v2 validation-transfer checkpoint" in rendered_prompt
        ),
        "forbidden_prompt_tokens_present": forbidden_present,
    }
    required_true_fields = [
        "adapter_schema_present",
        "prompt_section_present",
        "compact_prompt_value_present",
        "problem_measurement_diagnostics_key_present",
        "measurable_opportunity_classes_present",
        "decision_features_exclusion_present",
    ]
    if family == "cvrp":
        required_true_fields.extend(
            [
                "screening_headroom_present",
                "mechanism_effect_ranking_present",
                "highest_current_followup_present",
            ]
        )
    elif family == "warehouse_delivery":
        required_true_fields.extend(
            [
                "warehouse_transfer_risk_present",
                "warehouse_required_diagnostics_present",
                "warehouse_followup_opportunity_present",
                "warehouse_plateau_guard_present",
                "warehouse_v2_followup_present",
            ]
        )
    available = (
        bool(payload)
        and (
            (family == "cvrp" and summary["mechanism_rank_count"] > 0)
            or (
                family == "warehouse_delivery"
                and summary["opportunity_diagnostic_count"] > 0
            )
        )
        and not forbidden_present
        and all(summary[field] is True for field in required_true_fields)
    )
    return {
        **summary,
        "available": available,
        "reason": "ok" if available else "missing_prompt_projection",
    }


def _minimal_hypothesis_context(payload: dict[str, Any]) -> dict[str, Any]:
    family = str(payload.get("problem_family") or "")
    if family == "warehouse_delivery":
        return {
            "problem_summary": "Warehouse prepared prompt diagnostics audit.",
            "research_surfaces": "Research surfaces: warehouse_operator",
            "operator_categories": "warehouse_operator",
            "available_actions": "modify, create_new",
            "targetable_files": "operators/*.py",
            "champion_operators_code": "class MergeVehicles:\n    pass\n",
            "champion_stats": "champion_v2",
            "problem_measurement_diagnostics": payload,
        }
    return {
        "problem_summary": "CVRP prepared prompt diagnostics audit.",
        "research_surfaces": "Research surfaces: solver_design",
        "operator_categories": "solver_design",
        "available_actions": "modify, create_new",
        "targetable_files": "policies/baseline_algorithm.py",
        "champion_operators_code": "def solve():\n    return best\n",
        "champion_stats": "prepared_prompt_audit",
        "problem_measurement_diagnostics": payload,
    }


def _minimal_code_constraints_context(
    *,
    problem_family: str,
    surface: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    family = str(problem_family or "")
    surface_name = str(surface or "").strip()
    solver_design = surface_name == "solver_design"
    if family == "warehouse_delivery":
        return {
            "problem_summary": "Warehouse prepared code-constraints audit.",
            "problem_object": "Warehouse delivery operator state.",
            "solver_mechanics": "Apply one order-level operator move per call.",
            "research_surface_name": surface_name,
            "research_surface_kind": "operator",
            "operator_interface_spec": "Modify operator modules with feasible moves.",
            "import_whitelist": "typing, math",
            "champion_operators_code": (
                "class MoveOrder:\\n"
                "    validation_transfer_diagnostics = {}\\n"
            ),
            "hypothesis_implementation_brief": {
                "action": "modify",
                "target_file": "operators/move_order.py",
                "hypothesis_text": "Prepared code constraint audit.",
            },
            "target_file": "operators/move_order.py",
            "target_file_code": "class MoveOrder:\\n    pass\\n",
            "editable_patterns": "operators/*.py",
            "frozen_patterns": "tests/**",
            "reference_operators": "operators/move_order.py",
            "active_subject_code_constraints": payload,
        }
    return {
        "problem_summary": "CVRP prepared code-constraints audit.",
        "problem_object": "CVRP solver design context.",
        "solver_mechanics": "ALNS/VNS solver with bounded local search phases.",
        "research_surface_name": surface_name,
        "research_surface_kind": "solver_design" if solver_design else "operator",
        "operator_interface_spec": (
            "Modify the solver-design target while preserving feasibility."
        ),
        "solver_design_api_manifest": (
            "context.make_solution(routes); context.record_phase(name, elapsed_ms); "
            "context.record_iteration(phase, count); context.record_move(...)"
        ),
        "solver_design_branch_current_integration_files": (
            "policies/baseline_algorithm.py"
        ),
        "import_whitelist": "math, time, random",
        "champion_operators_code": "def solve(context):\\n    return context.nearest_neighbor()\\n",
        "hypothesis_implementation_brief": {
            "action": "modify",
            "target_file": "policies/baseline_algorithm.py",
            "hypothesis_text": "Prepared code constraint audit.",
            "mechanism_changes": [
                {
                    "id": "large_instance_intra_route_two_opt_seed",
                    "action": "modify",
                }
            ],
        },
        "target_file": "policies/baseline_algorithm.py",
        "target_file_code": "def solve(context):\\n    return context.nearest_neighbor()\\n",
        "editable_patterns": "policies/*.py",
        "frozen_patterns": "tests/**",
        "reference_operators": "policies/baseline_algorithm.py",
        "active_subject_code_constraints": payload,
    }


def _minimal_research_shape_context(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "problem_summary": "Prepared research-shape prompt audit.",
        "research_surfaces": "Research surfaces: solver_design",
        "operator_categories": "solver_design",
        "available_actions": "modify, create_new",
        "targetable_files": "policies/baseline_algorithm.py",
        "champion_operators_code": "def solve():\n    return best\n",
        "champion_stats": "prepared_research_shape_audit",
        "research_shape_diagnostics": payload,
    }


def _minimal_research_focus_context(
    *,
    problem_family: str,
    launch_research_focus: dict[str, Any],
) -> dict[str, Any]:
    family = str(problem_family or "")
    if family == "warehouse_delivery":
        return {
            "problem_summary": "Warehouse prepared research-focus audit.",
            "research_surfaces": "Research surfaces: warehouse_operator",
            "operator_categories": "warehouse_operator",
            "available_actions": "modify, create_new",
            "targetable_files": "operators/*.py",
            "champion_operators_code": "class MergeVehicles:\n    pass\n",
            "champion_stats": "champion_v2",
            "launch_research_focus": launch_research_focus,
        }
    return {
        "problem_summary": "CVRP prepared research-focus audit.",
        "research_surfaces": "Research surfaces: solver_design",
        "operator_categories": "solver_design",
        "available_actions": "modify, create_new",
        "targetable_files": "policies/baseline_algorithm.py",
        "champion_operators_code": "def solve():\n    return best\n",
        "champion_stats": "prepared_focus_audit",
        "launch_research_focus": launch_research_focus,
    }


def _launch_research_focus_payload(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
    projected_focus: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "scion.launch_research_focus_prompt.v1",
        "taint": "prepared_launch_research_focus",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "decision_input_policy": "excluded_from_decision_features",
        "source": "PREPARED_RUN_MANIFEST",
        "manifest_path": str(manifest_path),
        "problem_family": str(manifest.get("problem_family") or ""),
        "analysis_intent": str(manifest.get("analysis_intent") or ""),
        "acceptance_focus": [
            str(item)
            for item in (manifest.get("acceptance_focus") or [])
            if str(item).strip()
        ],
        "research_focus": projected_focus,
    }


def _research_shape_payload_from_campaign(
    *,
    campaign_summary: dict[str, Any],
    campaign_status: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    for source_name, payload_root in (
        ("copied_campaign_status", campaign_status),
        ("copied_campaign_summary", campaign_summary),
    ):
        payload = _find_research_shape_payload(payload_root)
        if payload:
            return payload, source_name
    return {}, ""


def _find_research_shape_payload(value: Any, *, depth: int = 0) -> dict[str, Any]:
    if depth > 6:
        return {}
    if isinstance(value, dict):
        direct = _mapping_or_empty(value.get("research_shape_diagnostics"))
        if direct:
            return direct
        if _looks_like_research_shape(value):
            return value
        for item in value.values():
            found = _find_research_shape_payload(item, depth=depth + 1)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _find_research_shape_payload(item, depth=depth + 1)
            if found:
                return found
    return {}


def _looks_like_research_shape(value: dict[str, Any]) -> bool:
    schema = str(value.get("schema_version") or "")
    if schema in {
        "campaign_research_shape_diagnostics.v1",
        "proposal_research_shape_prompt_summary.v1",
    }:
        return True
    return (
        "branch_depth_distribution" in value
        and (
            "mechanism_family_breadth" in value
            or "mechanism_family_counts" in value
        )
    )


def _representative_research_shape_payload() -> dict[str, Any]:
    return {
        "schema_version": "proposal_research_shape_prompt_summary.v1",
        "taint": "proposal_research_feedback",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "decision_input_policy": "excluded_from_decision_features",
        "current_branch_id": "prepared-audit-branch",
        "branch_count": 2,
        "active_branch_count": 1,
        "terminal_branch_count": 1,
        "current_branch_depth": 1,
        "max_observed_branch_depth": 2,
        "branch_depth_distribution": {"1": 1, "2": 1},
        "mechanism_family_counts": [
            {"family": "prepared_audit_family", "count": 2}
        ],
        "shape_label": "low_followup_depth",
        "proposal_guidance": [
            "Use branch depth and outcome distribution to choose deepen, "
            "diversify, or repair; do not treat this as promotion evidence."
        ],
    }


def _expected_adapter_diagnostic_schema(problem_family: str) -> str:
    if problem_family == "cvrp":
        return "cvrp_measurement_opportunity_diagnostic.v1"
    if problem_family == "warehouse_delivery":
        return "warehouse_validation_transfer_diagnostic.v1"
    return ""


def _required_research_focus_projection_keys(
    problem_family: str,
    research_focus: dict[str, Any],
) -> list[str]:
    common = [
        key
        for key in (
            "schema_version",
            "scope",
            "next_required_direction",
            "decision_boundary",
            "measurement_opportunity_diagnostics",
            "default_avoid_directions",
            "required_evidence",
            "measurable_opportunity_classes",
        )
        if key in research_focus
    ]
    if problem_family == "cvrp":
        common.extend(
            key
            for key in (
                "large_instance_two_opt_constraints",
                "case_protection_requirements",
                "resume_continuity_requirements",
                "route_merge_exception_rule",
                "construction_seed_rule",
            )
            if key in research_focus
        )
    elif problem_family == "warehouse_delivery":
        common.extend(
            key
            for key in (
                "accepted_checkpoint",
                "current_question",
            )
            if key in research_focus
        )
    return sorted(dict.fromkeys(common))


def _required_research_focus_projection_paths(
    problem_family: str,
    research_focus: dict[str, Any],
) -> list[str]:
    paths: list[str] = [
        key
        for key in _required_research_focus_projection_keys(
            problem_family,
            research_focus,
        )
        if key in research_focus
    ]
    paths.extend(
        _supported_nested_paths(
            "measurement_opportunity_diagnostics",
            research_focus,
            (
                "schema_version",
                "metric",
                "runtime_model",
                "pairing_validity",
                "practical_screen_delta",
                "screening_mde_at_power_80",
                "recommended_min_seeds",
                "opportunity_projection_source",
                "adapter_payload_schema",
                "reason_codes",
                "summary",
                "transfer_risk",
                "required_diagnostics",
                "screening_headroom",
                "measurable_opportunity_classes",
                "mechanism_effect_ranking",
                "opportunity_diagnostics",
                "policy",
                "decision_features_excluded",
                "proposal_visibility_only",
                "calibration",
            ),
        )
    )
    paths.extend(
        _supported_measurement_nested_paths(
            research_focus,
            "calibration",
            (
                "schema",
                "source_artifact",
                "calibration_run",
                "calibration_run_action",
            ),
        )
    )
    if problem_family == "cvrp":
        paths.extend(
            _supported_measurement_nested_paths(
                research_focus,
                "screening_headroom",
                (
                    "scope",
                    "metric",
                    "case_count",
                    "gap_pct_min",
                    "gap_pct_max",
                    "case_count_gap_pct_at_least_3",
                    "case_details_omitted",
                    "planning_use",
                ),
            )
        )
        paths.extend(
            _supported_nested_paths(
                "large_instance_two_opt_constraints",
                research_focus,
                (
                    "schema_version",
                    "scope",
                    "seed_report",
                    "proposal_visibility_only",
                    "decision_features_excluded",
                    "implementation_constraints",
                    "required_pair_evidence",
                    "default_reject_directions",
                ),
            )
        )
        paths.extend(
            _supported_nested_paths(
                "case_protection_requirements",
                research_focus,
                (
                    "schema_version",
                    "scope",
                    "proposal_visibility_only",
                    "decision_features_excluded",
                    "protected_cases",
                    "rules",
                    "required_evidence",
                ),
            )
        )
        paths.extend(
            _supported_nested_paths(
                "resume_continuity_requirements",
                research_focus,
                (
                    "schema_version",
                    "scope",
                    "proposal_visibility_only",
                    "decision_features_excluded",
                    "fallback_sources",
                    "rules",
                    "required_evidence",
                ),
            )
        )
    elif problem_family == "warehouse_delivery":
        paths.extend(
            _supported_measurement_nested_paths(
                research_focus,
                "transfer_risk",
                (
                    "risk_model",
                    "historical_pattern",
                    "latest_field_gate_pattern",
                    "latest_formal_no_gain_pattern",
                    "required_hypothesis_claims",
                ),
            )
        )
        paths.extend(
            _supported_measurement_nested_paths(
                research_focus,
                "required_diagnostics",
                ("activation", "effect"),
            )
        )
    return sorted(dict.fromkeys(paths))


def _supported_measurement_nested_paths(
    research_focus: dict[str, Any],
    child_key: str,
    grandchild_keys: tuple[str, ...],
) -> list[str]:
    measurement = research_focus.get("measurement_opportunity_diagnostics")
    if not isinstance(measurement, dict):
        return []
    value = measurement.get(child_key)
    if not isinstance(value, dict):
        return []
    return [
        f"measurement_opportunity_diagnostics.{child_key}.{grandchild_key}"
        for grandchild_key in grandchild_keys
        if value.get(grandchild_key) not in ({}, [], "", None)
    ]


def _supported_nested_paths(
    parent_key: str,
    research_focus: dict[str, Any],
    child_keys: tuple[str, ...],
) -> list[str]:
    value = research_focus.get(parent_key)
    if not isinstance(value, dict):
        return []
    return [
        f"{parent_key}.{child_key}"
        for child_key in child_keys
        if value.get(child_key) not in ({}, [], "", None)
    ]


def _non_empty_leaf_paths(value: Any, *, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(_non_empty_leaf_paths(child, prefix=child_prefix))
        return sorted(paths)
    if value in ({}, [], "", None):
        return []
    return [prefix] if prefix else []


def _path_value(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _prompt_contains_path(rendered_prompt: str, path: str) -> bool:
    parts = [part for part in path.split(".") if part]
    return bool(parts) and all(part in rendered_prompt for part in parts)


def _rendered_sequence_item_counts(
    rendered_prompt: str,
    value: Any,
) -> dict[str, Any]:
    sequence = value if isinstance(value, (list, tuple)) else []
    items = [str(item).strip() for item in sequence if str(item).strip()]
    rendered_count = sum(1 for item in items if item in rendered_prompt)
    return {
        "item_count": len(items),
        "rendered_count": rendered_count,
        "all_present": rendered_count == len(items),
    }


def _rendered_constraint_item_counts(
    rendered_prompt: str,
    value: Any,
) -> dict[str, Any]:
    sequence = value if isinstance(value, (list, tuple)) else []
    tokens: list[str] = []
    for item in sequence:
        if isinstance(item, dict):
            token = str(item.get("id") or item.get("summary") or "").strip()
            if token:
                tokens.append(token)
        else:
            token = str(item or "").strip()
            if token:
                tokens.append(token)
    rendered_count = sum(1 for token in tokens if token in rendered_prompt)
    return {
        "item_count": len(tokens),
        "rendered_count": rendered_count,
        "all_present": rendered_count == len(tokens),
    }


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple)):
        return len(value)
    return 0
