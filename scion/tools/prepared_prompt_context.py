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
        "warehouse_avoid_directions_present": (
            problem_family == "warehouse_delivery"
            and "default_avoid_directions" in rendered_prompt
        ),
        "warehouse_measurement_handoff_present": (
            problem_family == "warehouse_delivery"
            and "measurement_opportunity_diagnostics" in rendered_prompt
            and "runtime_model" in rendered_prompt
        ),
        "cvrp_case_protection_present": (
            problem_family == "cvrp"
            and "CMT2" in rendered_prompt
            and "CMT4" in rendered_prompt
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
        if research_focus.get("default_avoid_directions") not in ({}, [], "", None):
            required_true_fields.append("warehouse_avoid_directions_present")
        if (
            research_focus.get("measurement_opportunity_diagnostics")
            not in ({}, [], "", None)
        ):
            required_true_fields.append("warehouse_measurement_handoff_present")
    elif problem_family == "cvrp":
        if research_focus.get("case_protection_requirements") not in (
            {},
            [],
            "",
            None,
        ):
            required_true_fields.append("cvrp_case_protection_present")
        if research_focus.get("large_instance_two_opt_constraints") not in (
            {},
            [],
            "",
            None,
        ):
            required_true_fields.append("cvrp_bounded_twoopt_present")
        if (
            research_focus.get("route_merge_exception_rule")
            not in ({}, [], "", None)
            or research_focus.get("construction_seed_rule")
            not in ({}, [], "", None)
        ):
            required_true_fields.append("cvrp_direct_effect_rules_present")
        if (
            research_focus.get("measurement_opportunity_diagnostics")
            not in ({}, [], "", None)
        ):
            required_true_fields.append("cvrp_measurement_handoff_present")
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
                "reason_codes",
                "summary",
                "decision_features_excluded",
                "proposal_visibility_only",
            ),
        )
    )
    if problem_family == "cvrp":
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
    return sorted(dict.fromkeys(paths))


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


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple)):
        return len(value)
    return 0
