"""Warehouse-owned report-only measurement prompt bridge metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scion.postrun.handoff.prepared_prompt_context import (
    PROBLEM_MEASUREMENT_DIAGNOSTICS_FORBIDDEN_PROMPT_TOKENS,
)
from scion.postrun.handoff.prompt_context_readiness import ProblemPromptBridgeSpec


PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_SUMMARY_SCHEMA = (
    "scion.problem_measurement_diagnostics_prompt_summary.v1"
)
WAREHOUSE_MEASUREMENT_PROMPT_SUMMARY_COMPARE_FIELDS = (
    "problem_family",
    "problem_v1_path",
    "payload_schema_version",
    "prompt_context_key_present",
    "lossless_context_handoff",
    "decision_features_exclusion_present",
    "diagnostic_field_count",
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
    "prompt_renderer": (
        "scion/scion/proposal/engine/hypothesis_prompts.py",
        "problem_measurement_diagnostics",
    ),
}


def warehouse_problem_measurement_diagnostics_prompt_summary(
    *,
    problem_v1_path: Path | str | None,
    problem_family: str,
) -> dict[str, Any]:
    """Report whether warehouse measurement context reaches the direct prompt."""

    family = str(problem_family or "").strip()
    problem_path = Path(problem_v1_path).expanduser() if problem_v1_path else None
    problem_path = (
        problem_path.resolve()
        if problem_path is not None and problem_path.is_file()
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
        system_blocks, user_prompt = _split_hypothesis_context(dict(filtered))
        rendered_prompt = "\n".join(
            str(block.get("text") or "")
            for block in system_blocks
            if isinstance(block, dict)
        )
        rendered_prompt = f"{rendered_prompt}\n{user_prompt}"
    except Exception as exc:  # pragma: no cover - reported as bridge detail.
        return {
            **base,
            "available": False,
            "reason": "prompt_bridge_error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    forbidden_present = [
        token
        for token in PROBLEM_MEASUREMENT_DIAGNOSTICS_FORBIDDEN_PROMPT_TOKENS
        if token in rendered_prompt.lower()
    ]
    problem_owned = payload.get("problem_owned_diagnostics")
    problem_owned = problem_owned if isinstance(problem_owned, dict) else {}
    lossless = filtered.get("problem_measurement_diagnostics") == payload
    key_present = '"problem_measurement_diagnostics"' in rendered_prompt
    available = bool(payload) and lossless and key_present and not forbidden_present
    return {
        **base,
        "available": available,
        "reason": "ok" if available else "missing_prompt_projection",
        "payload_schema_version": str(problem_owned.get("schema_version") or ""),
        "prompt_context_key_present": key_present,
        "lossless_context_handoff": lossless,
        "decision_features_exclusion_present": True,
        "diagnostic_field_count": len(payload),
        "forbidden_prompt_tokens_present": forbidden_present,
    }


def _minimal_hypothesis_context(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "problem_summary": "Warehouse prepared measurement-context audit.",
        "research_surfaces": [
            {
                "name": "order_level",
                "kind": "operator",
                "target_files": ["operators/move_order.py"],
            },
            {
                "name": "vehicle_level",
                "kind": "operator",
                "target_files": ["operators/merge_vehicles.py"],
            },
        ],
        "available_actions": ["modify", "create_new"],
        "targetable_files": [
            "operators/move_order.py",
            "operators/merge_vehicles.py",
        ],
        "champion_operators_code": "class MoveOrder:\n    pass\n",
        "champion_stats": {"source": "prepared_measurement_context_audit"},
        "problem_measurement_diagnostics": payload,
    }


WAREHOUSE_PROMPT_BRIDGE_SPEC = ProblemPromptBridgeSpec(
    problem_family="warehouse_delivery",
    problem_v1_candidates=(
        "scion/problems/warehouse_delivery/problem-v1.yaml",
        "scion/scion/problems/warehouse_delivery/problem-v1.yaml",
    ),
    measurement_signal_name="warehouse_problem_measurement_diagnostics_prompt_bridge",
    measurement_failure_prefix="warehouse_problem_measurement_diagnostics_bridge",
    measurement_source_markers=(
        WAREHOUSE_PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_MARKERS
    ),
    measurement_marker_group=(
        "warehouse_delivery_problem_measurement_diagnostics_source_markers"
    ),
    measurement_bridge_scope="problem-owned measurement context",
    measurement_prompt_summary_schema=(
        PROBLEM_MEASUREMENT_DIAGNOSTICS_PROMPT_SUMMARY_SCHEMA
    ),
    measurement_prompt_summary_builder=(
        warehouse_problem_measurement_diagnostics_prompt_summary
    ),
    measurement_prompt_summary_compare_fields=(
        WAREHOUSE_MEASUREMENT_PROMPT_SUMMARY_COMPARE_FIELDS
    ),
    measurement_prompt_summary_positive_fields=("diagnostic_field_count",),
)
