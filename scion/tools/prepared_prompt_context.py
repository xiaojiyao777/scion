"""Shared prepared prompt/context audit helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


RESEARCH_FOCUS_PROJECTION_SUMMARY_SCHEMA = (
    "scion.prepared_research_focus_projection_summary.v1"
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


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple)):
        return len(value)
    return 0
