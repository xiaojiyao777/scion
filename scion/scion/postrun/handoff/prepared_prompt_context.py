"""Shared prepared prompt/context audit helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scion.research_guidance import (
    launch_research_guidance_payload,
    research_guidance_projection_summary,
)


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
    """Summarize typed prepared research guidance rendered-path coverage."""

    return research_guidance_projection_summary(
        manifest_path=manifest_path,
        manifest=manifest,
        schema_version=RESEARCH_FOCUS_PROJECTION_SUMMARY_SCHEMA,
        forbidden_tokens=PROBLEM_MEASUREMENT_DIAGNOSTICS_FORBIDDEN_PROMPT_TOKENS,
    )


def research_focus_prompt_summary(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Summarize typed prepared research guidance that reaches prompts."""

    problem_family = str(manifest.get("problem_family") or "").strip()
    projection = research_focus_projection_summary(
        manifest_path=manifest_path,
        manifest=manifest,
    )
    base = {
        "schema_version": RESEARCH_FOCUS_PROMPT_SUMMARY_SCHEMA,
        "problem_family": problem_family,
        "manifest_path": str(manifest_path),
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
        "contract_present": projection.get("contract_present") is True,
        "legacy_research_focus_present": projection.get(
            "legacy_research_focus_present"
        ) is True,
        "contract_source": str(projection.get("contract_source") or ""),
        "schema_valid": projection.get("schema_valid") is True,
        "contract_schema_version": str(projection.get("contract_schema_version") or ""),
        "visibility_policy": str(projection.get("visibility_policy") or ""),
        "proposal_visibility_only": projection.get("proposal_visibility_only") is True,
        "expected_rendered_paths": list(projection.get("expected_rendered_paths") or []),
        "rendered_paths": list(projection.get("rendered_paths") or []),
        "missing_rendered_paths": list(projection.get("missing_rendered_paths") or []),
        "rendered_path_count": int(projection.get("rendered_path_count") or 0),
    }
    if projection.get("available") is not True:
        return {
            **base,
            "available": False,
            "reason": "projection_unavailable",
            "launch_focus_schema_present": False,
            "launch_focus_taint_present": False,
            "prompt_section_present": False,
            "compact_prompt_value_present": False,
            "launch_research_focus_key_present": False,
            "decision_features_exclusion_present": False,
            "manifest_path_present": False,
            "contract_schema_present": False,
            "guidance_text_digest_present": False,
            "rendered_required_paths": list(base["rendered_paths"]),
            "rendered_required_path_count": int(base["rendered_path_count"]),
            "required_rendered_path_count": len(base["expected_rendered_paths"]),
            "forbidden_prompt_tokens_present": [],
        }

    try:
        from scion.proposal.engine.hypothesis_context_profiles import (
            filter_hypothesis_context_for_prompt,
        )
        from scion.proposal.engine.hypothesis_prompts import (
            _split_hypothesis_context,
        )

        launch_payload = launch_research_guidance_payload(
            manifest_path=manifest_path,
            manifest=manifest,
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
            "launch_focus_schema_present": False,
            "launch_focus_taint_present": False,
            "prompt_section_present": False,
            "compact_prompt_value_present": False,
            "launch_research_focus_key_present": False,
            "decision_features_exclusion_present": False,
            "manifest_path_present": False,
            "contract_schema_present": False,
            "guidance_text_digest_present": False,
            "rendered_required_paths": list(base["rendered_paths"]),
            "rendered_required_path_count": int(base["rendered_path_count"]),
            "required_rendered_path_count": len(base["expected_rendered_paths"]),
            "forbidden_prompt_tokens_present": [],
        }

    rendered_lower = rendered_prompt.lower()
    forbidden_present = [
        token
        for token in PROBLEM_MEASUREMENT_DIAGNOSTICS_FORBIDDEN_PROMPT_TOKENS
        if token in rendered_lower
    ]
    contract_schema_version = base["contract_schema_version"]
    guidance_digest = str(launch_payload.get("guidance_text_sha256") or "")
    summary = {
        **base,
        "launch_focus_schema_present": (
            "scion.launch_research_guidance_prompt.v1" in rendered_prompt
        ),
        "launch_focus_taint_present": (
            "prepared_launch_research_guidance" in rendered_prompt
        ),
        "prompt_section_present": "## Compact Research Signals" in rendered_prompt,
        "compact_prompt_value_present": bool(compact.strip()),
        "launch_research_focus_key_present": "launch_research_focus" in rendered_prompt,
        "decision_features_exclusion_present": (
            "excluded from DecisionFeatures" in rendered_prompt
            or "excluded_from_decision_features" in rendered_prompt
        ),
        "manifest_path_present": str(manifest_path) in rendered_prompt,
        "contract_schema_present": bool(
            contract_schema_version and contract_schema_version in rendered_prompt
        ),
        "guidance_text_digest_present": bool(
            guidance_digest and guidance_digest in rendered_prompt
        ),
        "rendered_required_paths": list(base["rendered_paths"]),
        "rendered_required_path_count": int(base["rendered_path_count"]),
        "required_rendered_path_count": len(base["expected_rendered_paths"]),
        "forbidden_prompt_tokens_present": forbidden_present,
    }
    required_true_fields = [
        "schema_valid",
        "proposal_visibility_only",
        "launch_focus_schema_present",
        "launch_focus_taint_present",
        "prompt_section_present",
        "compact_prompt_value_present",
        "launch_research_focus_key_present",
        "decision_features_exclusion_present",
        "manifest_path_present",
        "contract_schema_present",
        "guidance_text_digest_present",
    ]
    available = (
        not summary["missing_rendered_paths"]
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
                        "id": "prepared_code_constraint_probe",
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
    return {
        "problem_summary": (
            f"Prepared research-guidance audit for {problem_family or 'unknown'}."
        ),
        "research_surfaces": "Research surfaces: solver_design",
        "operator_categories": "solver_design",
        "available_actions": "modify, create_new",
        "targetable_files": "policies/example_algorithm.py",
        "champion_operators_code": "def solve():\n    return incumbent\n",
        "champion_stats": "prepared_guidance_audit",
        "launch_research_focus": launch_research_focus,
    }


def _launch_research_focus_payload(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
    projected_focus: dict[str, Any],
) -> dict[str, Any]:
    del projected_focus
    return launch_research_guidance_payload(
        manifest_path=manifest_path,
        manifest=manifest,
    )


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
