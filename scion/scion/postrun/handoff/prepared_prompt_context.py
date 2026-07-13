"""Typed prepared context projection used by direct-only readiness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scion.research_guidance import research_guidance_projection_summary


RESEARCH_FOCUS_PROJECTION_SUMMARY_SCHEMA = (
    "scion.prepared_research_focus_projection_summary.v1"
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
    """Summarize typed prepared research-guidance path coverage."""

    return research_guidance_projection_summary(
        manifest_path=manifest_path,
        manifest=manifest,
        schema_version=RESEARCH_FOCUS_PROJECTION_SUMMARY_SCHEMA,
        forbidden_tokens=PROBLEM_MEASUREMENT_DIAGNOSTICS_FORBIDDEN_PROMPT_TOKENS,
    )
