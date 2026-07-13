from __future__ import annotations

from copy import deepcopy

from scion.postrun import PostrunPromptVisibilityAcceptancePort
from scion.postrun.opportunity_visibility import (
    PROBLEM_OPPORTUNITY_VISIBILITY_SCHEMA,
)
from scion.postrun.prompt_visibility_acceptance import (
    PROMPT_CONTEXT_VISIBILITY_SCHEMA,
    PROMPT_SIGNAL_DENSITY_SCHEMA,
    PROMPT_SOURCE_VISIBILITY_SCHEMA,
    prompt_context_visibility_consistency_failures,
)


def test_prompt_visibility_acceptance_emits_legacy_ready_payload() -> None:
    summary, expected = _ready_prompt_inputs()

    check = PostrunPromptVisibilityAcceptancePort().summarize(
        problem_family="cvrp",
        summary=summary,
        expected=expected,
    ).checks[0]

    assert check.name == "prompt_source_visibility_actionability"
    assert check.status == "ok"
    assert check.required is True
    assert check.detail["problem_family"] == "cvrp"
    assert check.detail["failures"] == []
    assert "target_intent_source_visibility_required" not in check.detail


def test_prompt_visibility_acceptance_rejects_drift_and_policy_failures() -> None:
    summary, expected = _ready_prompt_inputs()
    aggregate = summary["aggregate"]
    source = aggregate["source_visibility"]
    density = aggregate["signal_density"]
    aggregate["trace_count"] = 3
    density["total_token_estimate"] = 999
    source["code_protected_source_visible_count"] = 0

    check = PostrunPromptVisibilityAcceptancePort().summarize(
        problem_family="warehouse_delivery",
        summary=summary,
        expected=expected,
    ).checks[0]

    failures = check.detail["failures"]

    assert check.status == "failed"
    assert "code_protected_source_visibility_not_full" in failures
    assert "prompt_context_visibility_trace_count_mismatch" in failures
    assert "prompt_signal_density_total_token_estimate_mismatch" in failures


def test_prompt_visibility_acceptance_can_emit_skipped_payload() -> None:
    check = PostrunPromptVisibilityAcceptancePort().summarize(
        problem_family="other",
        summary={},
        expected={},
        enabled=False,
    ).checks[0]

    assert check.name == "prompt_source_visibility_actionability"
    assert check.status == "skipped"
    assert check.required is False
    assert check.detail == {
        "reason": "not_problem_specific_agentic_summary",
        "problem_family": "other",
    }


def test_prompt_visibility_consistency_detects_opportunity_drift() -> None:
    summary, expected = _ready_prompt_inputs()
    summary["aggregate"]["problem_opportunity_visibility"][
        "section_visible_trace_count"
    ] = 0

    assert "prompt_context_visibility_problem_opportunity_mismatch" in (
        prompt_context_visibility_consistency_failures(
            summary=summary,
            expected=expected,
        )
    )


def _ready_prompt_inputs() -> tuple[dict[str, object], dict[str, object]]:
    source_visibility = {
        "schema_version": PROMPT_SOURCE_VISIBILITY_SCHEMA,
        "report_only": True,
        "decision_features_excluded": True,
        "trace_count": 1,
        "code_trace_count": 1,
        "code_target_source_visible_count": 1,
        "code_target_source_missing_count": 0,
        "code_protected_source_visible_count": 1,
        "code_protected_source_missing_count": 0,
        "code_required_integration_source_visible_count": 1,
        "code_algorithm_file_read_source_visible_count": 1,
        "code_missing_required_source_trace_count": 0,
        "code_missing_required_source_path_counts": {},
        "code_target_source_status_counts": {"visible": 1},
        "code_target_visibility_status_counts": {"visible": 1},
    }
    signal_density = {
        "schema_version": PROMPT_SIGNAL_DENSITY_SCHEMA,
        "report_only": True,
        "decision_features_excluded": True,
        "total_token_estimate": 100,
        "research_signal_tokens": 40,
        "source_code_tokens": 30,
        "cross_branch_tokens": 10,
        "governance_tokens": 20,
        "research_signal_share": 0.4,
        "source_code_share": 0.3,
        "cross_branch_share": 0.1,
        "governance_share": 0.2,
        "research_plus_source_to_governance_ratio": 3.5,
        "interpretation": "source_and_research_visible",
    }
    opportunity_visibility = {
        "schema_version": PROBLEM_OPPORTUNITY_VISIBILITY_SCHEMA,
        "report_only": True,
        "decision_features_excluded": True,
        "trace_count": 1,
        "hypothesis_generation_trace_count": 1,
        "section_present_trace_count": 1,
        "hypothesis_generation_section_present_trace_count": 1,
        "section_visible_trace_count": 1,
        "hypothesis_generation_section_visible_trace_count": 1,
        "full_section_visible_trace_count": 1,
        "not_visible_trace_count": 0,
        "section_status_counts": {"included": 1},
        "visibility_status_counts": {"included": 1},
        "block_family_counts": {"research_signal": 1},
        "context_visibility_counts": {"full": 1},
    }
    aggregate = {
        "prompt_manifest_ref_count": 1,
        "prompt_manifest_loaded_count": 1,
        "trace_count": 1,
        "visibility_digest_count": 1,
        "block_family_trace_count": 1,
        "hypothesis_generation_trace_count": 1,
        "hypothesis_generation_block_family_trace_count": 1,
        "call_kind_counts": {"hypothesis_generation": 1},
        "block_family_totals": {
            "research_signal": {
                "trace_count": 1,
                "char_count": 100,
                "token_estimate": 25,
            }
        },
        "hypothesis_generation_block_family_totals": {
            "research_signal": {
                "trace_count": 1,
                "char_count": 100,
                "token_estimate": 25,
            }
        },
        "source_visibility": source_visibility,
        "signal_density": signal_density,
        "hypothesis_generation_signal_density": dict(signal_density),
        "problem_opportunity_visibility": opportunity_visibility,
    }
    summary = {
        "schema_version": PROMPT_CONTEXT_VISIBILITY_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
        "raw_response_excluded": True,
        "patch_body_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "manifest_report_count": 1,
        "context_report_count": 1,
        "aggregate": aggregate,
        "entries": [
            {
                "report": "prompt_context_visibility.v1.json",
                "path": "/tmp/run/postrun_acceptance/context/report.json",
                "prompt_manifest_ref_count": 1,
                "prompt_manifest_loaded_count": 1,
                "trace_count": 1,
                "visibility_digest_count": 1,
                "block_family_trace_count": 1,
                "hypothesis_generation_trace_count": 1,
                "hypothesis_generation_block_family_trace_count": 1,
                "call_kind_counts": {"hypothesis_generation": 1},
                "block_family_totals": aggregate["block_family_totals"],
                "hypothesis_generation_block_family_totals": (
                    aggregate["hypothesis_generation_block_family_totals"]
                ),
                "source_visibility": source_visibility,
                "problem_opportunity_visibility": opportunity_visibility,
            }
        ],
    }
    return summary, deepcopy(summary)
