"""Warehouse-owned prepared prompt bridge metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scion.postrun.handoff.prepared_prompt_context import (
    PROBLEM_MEASUREMENT_DIAGNOSTICS_FORBIDDEN_PROMPT_TOKENS,
)
from scion.postrun.handoff.prompt_context_readiness import ProblemPromptBridgeSpec


ACTIVE_SUBJECT_CODE_CONSTRAINTS_PROMPT_SUMMARY_SCHEMA = (
    "scion.active_subject_code_constraints_prompt_summary.v1"
)
PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_SUMMARY_SCHEMA = (
    "scion.problem_measurement_diagnostics_prompt_summary.v1"
)
WAREHOUSE_ACTIVE_SUBJECT_PROMPT_SUMMARY_COMPARE_FIELDS = (
    "problem_family",
    "surface",
    "problem_v1_path",
    "payload_version",
    "subject_id",
    "prompt_section_present",
    "compact_prompt_value_present",
    "payload_version_present",
    "subject_id_present",
    "surface_present",
    "decision_features_exclusion_present",
    "constraint_count",
    "constraint_id_rendered_count",
    "constraint_ids_all_present",
    "object_model_hint_count",
    "object_model_hint_id_rendered_count",
    "object_model_hint_ids_all_present",
    "api_contract_count",
    "api_contract_id_rendered_count",
    "api_contract_ids_all_present",
    "forbidden_pattern_count",
    "forbidden_pattern_rendered_count",
    "forbidden_patterns_all_present",
    "warehouse_validation_transfer_diagnostics_present",
    "warehouse_lexicographic_guard_present",
)
WAREHOUSE_MEASUREMENT_PROMPT_SUMMARY_COMPARE_FIELDS = (
    "problem_family",
    "problem_v1_path",
    "payload_schema_version",
    "adapter_schema_present",
    "prompt_section_present",
    "compact_prompt_value_present",
    "problem_measurement_diagnostics_key_present",
    "measurable_opportunity_classes_present",
    "decision_features_exclusion_present",
    "opportunity_diagnostic_count",
    "warehouse_transfer_risk_present",
    "warehouse_required_diagnostics_present",
    "warehouse_followup_opportunity_present",
    "warehouse_plateau_guard_present",
    "warehouse_v2_followup_present",
)
WAREHOUSE_PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_MARKERS = {
    "adapter_hook": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "def render_problem_measurement_diagnostics",
    ),
    "context_payload": (
        "scion/scion/proposal/context_manager/manager.py",
        "problem_measurement_diagnostics",
    ),
    "profile_projection": (
        "scion/scion/proposal/engine/hypothesis_context_profiles.py",
        "adapter_diagnostics",
    ),
    "prompt_renderer": (
        "scion/scion/proposal/engine/hypothesis_prompts.py",
        "Problem Measurement Diagnostics",
    ),
}
WAREHOUSE_ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS = {
    "provider_hook": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "def active_subject_code_constraints",
    ),
    "diagnostics_contract": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "self.validation_transfer_diagnostics",
    ),
    "bounded_scan_guard": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "unbounded full vehicle-pair scans",
    ),
    "lexicographic_guard": (
        "scion/scion/problems/warehouse_delivery/adapter.py",
        "lexicographic",
    ),
}


def warehouse_active_subject_code_constraints_prompt_summary(
    *,
    problem_v1_path: Path | str | None,
    problem_family: str,
    surface: str,
) -> dict[str, Any]:
    """Summarize warehouse active-subject constraints that reach code prompts."""

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
    if family != "warehouse_delivery":
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
        "warehouse_validation_transfer_diagnostics_present": (
            "validation_transfer_diagnostics" in rendered_prompt
        ),
        "warehouse_lexicographic_guard_present": "lexicographic" in rendered_lower,
    }
    required_true_fields = [
        "prompt_section_present",
        "compact_prompt_value_present",
        "payload_version_present",
        "subject_id_present",
        "surface_present",
        "decision_features_exclusion_present",
        "constraint_ids_all_present",
        "warehouse_validation_transfer_diagnostics_present",
        "warehouse_lexicographic_guard_present",
    ]
    if summary["object_model_hint_count"]:
        required_true_fields.append("object_model_hint_ids_all_present")
    if summary["api_contract_count"]:
        required_true_fields.append("api_contract_ids_all_present")
    if summary["forbidden_pattern_count"]:
        required_true_fields.append("forbidden_patterns_all_present")
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


def warehouse_problem_measurement_diagnostics_prompt_summary(
    *,
    problem_v1_path: Path | str | None,
    problem_family: str,
) -> dict[str, Any]:
    """Summarize warehouse measurement diagnostics that reach hypothesis prompts."""

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
    if family != "warehouse_delivery":
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
    summary = {
        **base,
        "payload_schema_version": str(payload.get("schema_version") or ""),
        "adapter_schema_present": (
            "warehouse_validation_transfer_diagnostic.v1" in rendered_prompt
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
        "warehouse_transfer_risk_present",
        "warehouse_required_diagnostics_present",
        "warehouse_followup_opportunity_present",
        "warehouse_plateau_guard_present",
        "warehouse_v2_followup_present",
    ]
    available = (
        bool(payload)
        and summary["opportunity_diagnostic_count"] > 0
        and not forbidden_present
        and all(summary[field] is True for field in required_true_fields)
    )
    return {
        **summary,
        "available": available,
        "reason": "ok" if available else "missing_prompt_projection",
    }


def _minimal_hypothesis_context(payload: dict[str, Any]) -> dict[str, Any]:
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


def _minimal_code_constraints_context(
    *,
    surface: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    surface_name = str(surface or "").strip()
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


def _sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple)):
        return len(value)
    return 0


WAREHOUSE_PROMPT_BRIDGE_SPEC = ProblemPromptBridgeSpec(
    problem_family="warehouse_delivery",
    problem_v1_candidates=(
        "scion/problems/warehouse_delivery/problem-v1.yaml",
        "scion/scion/problems/warehouse_delivery/problem-v1.yaml",
    ),
    measurement_signal_name="warehouse_problem_measurement_diagnostics_prompt_bridge",
    measurement_failure_prefix="warehouse_problem_measurement_diagnostics_bridge",
    measurement_source_markers=WAREHOUSE_PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_MARKERS,
    measurement_marker_group=(
        "warehouse_delivery_problem_measurement_diagnostics_source_markers"
    ),
    measurement_bridge_scope="validation-transfer follow-up diagnostics",
    measurement_prompt_summary_schema=(
        PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_SUMMARY_SCHEMA
    ),
    measurement_prompt_summary_builder=(
        warehouse_problem_measurement_diagnostics_prompt_summary
    ),
    measurement_prompt_summary_compare_fields=(
        WAREHOUSE_MEASUREMENT_PROMPT_SUMMARY_COMPARE_FIELDS
    ),
    measurement_prompt_summary_positive_fields=("opportunity_diagnostic_count",),
    active_subject_signal_name=(
        "warehouse_active_subject_code_constraints_prompt_bridge"
    ),
    active_subject_failure_prefix="warehouse_active_subject_code_constraints_bridge",
    active_subject_surface="order_level",
    active_subject_provider_markers=WAREHOUSE_ACTIVE_SUBJECT_CODE_CONSTRAINT_MARKERS,
    active_subject_marker_group=(
        "warehouse_active_subject_code_constraint_source_markers"
    ),
    active_subject_prompt_summary_schema=(
        ACTIVE_SUBJECT_CODE_CONSTRAINTS_PROMPT_SUMMARY_SCHEMA
    ),
    active_subject_prompt_summary_builder=(
        warehouse_active_subject_code_constraints_prompt_summary
    ),
    active_subject_prompt_summary_compare_fields=(
        WAREHOUSE_ACTIVE_SUBJECT_PROMPT_SUMMARY_COMPARE_FIELDS
    ),
    active_subject_prompt_summary_positive_checks=(
        ("constraint_count", "empty"),
        ("constraint_id_rendered_count", "not_rendered"),
    ),
)
