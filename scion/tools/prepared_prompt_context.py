"""Shared prepared prompt/context audit helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


RESEARCH_FOCUS_PROJECTION_SUMMARY_SCHEMA = (
    "scion.prepared_research_focus_projection_summary.v1"
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
    return {
        **base,
        "available": bool(projected_dict) and not missing_keys,
        "reason": "ok" if projected_dict and not missing_keys else "missing_projection",
        "manifest_keys": sorted(research_focus),
        "projected_keys": sorted(projected_dict),
        "required_projected_keys": required_keys,
        "missing_projected_keys": missing_keys,
        "projected_field_count": len(projected_dict),
        "manifest_field_count": len(research_focus),
    }


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


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}
