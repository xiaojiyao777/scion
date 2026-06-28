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
RESEARCH_SHAPE_PROMPT_SUMMARY_SCHEMA = (
    "scion.prepared_research_shape_prompt_summary.v1"
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


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple)):
        return len(value)
    return 0
