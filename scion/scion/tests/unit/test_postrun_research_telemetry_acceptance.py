from __future__ import annotations

from copy import deepcopy

from scion.postrun.research_telemetry_acceptance import (
    BRANCH_RESEARCH_STATE_SCHEMA,
    CHAMPION_PROGRESS_SCHEMA,
    FAILURE_TAXONOMY_SCHEMA,
    PROMPT_SIGNAL_DENSITY_SCHEMA,
    RESEARCH_CONTEXT_ACTIONABILITY_SCHEMA,
    PostrunResearchTelemetryAcceptancePort,
)


def test_research_telemetry_acceptance_accepts_current_generic_summaries():
    brief, expected = _telemetry_brief_and_expected()

    payloads = _summarize(brief, expected).to_payloads()

    assert set(payloads) == {
        "research_context_actionability",
        "branch_research_state_actionability",
        "champion_progress_actionability",
        "failure_taxonomy_actionability",
    }
    for check in payloads.values():
        assert check["status"] == "ok"
        assert check["required"] is True
        assert check["detail"]["failures"] == []


def test_research_telemetry_acceptance_reports_projection_drift():
    brief, expected = _telemetry_brief_and_expected()
    brief["research_context_actionability_summary"]["actionability_gaps"].append(
        "unexpected_gap"
    )
    brief["branch_research_state_summary"]["aggregate"]["branch_count"] = 9
    brief["champion_progress_summary"]["champion_version_gain"] = 3
    brief["failure_taxonomy_summary"]["entries"][0][
        "failure_observations_total"
    ] = 7

    payloads = _summarize(brief, expected).to_payloads()

    assert "research_context_actionability_gaps_mismatch" in payloads[
        "research_context_actionability"
    ]["detail"]["failures"]
    assert "branch_research_state_branch_count_mismatch" in payloads[
        "branch_research_state_actionability"
    ]["detail"]["failures"]
    assert "champion_progress_champion_version_gain_mismatch" in payloads[
        "champion_progress_actionability"
    ]["detail"]["failures"]
    assert "failure_taxonomy_entries_mismatch" in payloads[
        "failure_taxonomy_actionability"
    ]["detail"]["failures"]


def test_research_telemetry_acceptance_skips_when_caller_disables_it():
    brief, expected = _telemetry_brief_and_expected()

    payloads = _summarize(brief, expected, enabled=False).to_payloads()

    for check in payloads.values():
        assert check["status"] == "skipped"
        assert check["required"] is False
        assert check["detail"]["reason"] == "not_problem_specific_agentic_summary"


def _summarize(
    brief: dict[str, object],
    expected: dict[str, dict[str, object]],
    *,
    enabled: bool = True,
):
    return PostrunResearchTelemetryAcceptancePort().summarize(
        problem_family="generic_research_problem",
        analysis_brief=brief,
        expected_research_context_actionability=expected[
            "research_context_actionability_summary"
        ],
        expected_branch_research_state=expected["branch_research_state_summary"],
        expected_champion_progress=expected["champion_progress_summary"],
        expected_failure_taxonomy=expected["failure_taxonomy_summary"],
        enabled=enabled,
    )


def _telemetry_brief_and_expected():
    actionability = _research_context_actionability_summary()
    branch = _branch_research_state_summary()
    champion = _champion_progress_summary()
    taxonomy = _failure_taxonomy_summary()
    brief = {
        "prompt_context_visibility_summary": _prompt_context_visibility_summary(),
        "research_continuity_summary": {
            "current_run_evidence": True,
            "available": True,
            "aggregate": {"max_branch_depth": 1},
        },
        "research_context_actionability_summary": deepcopy(actionability),
        "branch_research_state_summary": deepcopy(branch),
        "champion_progress_summary": deepcopy(champion),
        "failure_taxonomy_summary": deepcopy(taxonomy),
    }
    expected = {
        "research_context_actionability_summary": actionability,
        "branch_research_state_summary": branch,
        "champion_progress_summary": champion,
        "failure_taxonomy_summary": taxonomy,
    }
    return brief, expected


def _prompt_context_visibility_summary() -> dict[str, object]:
    return {
        "current_run_evidence": True,
        "available": True,
        "aggregate": {
            "block_family_trace_count": 1,
            "call_kind_counts": {"hypothesis": 1, "reflection": 1},
            "hypothesis_generation_trace_count": 1,
            "hypothesis_generation_block_family_trace_count": 1,
            "signal_density": _signal_density(),
            "hypothesis_generation_signal_density": _signal_density(),
        },
    }


def _signal_density() -> dict[str, object]:
    return {
        "schema_version": PROMPT_SIGNAL_DENSITY_SCHEMA,
        "report_only": True,
        "decision_features_excluded": True,
        "interpretation": "research_signal_visible",
        "total_token_estimate": 10,
        "research_signal_tokens": 4,
        "source_code_tokens": 2,
        "cross_branch_tokens": 1,
        "governance_tokens": 1,
        "research_plus_source_to_governance_ratio": 6.0,
    }


def _research_context_actionability_summary() -> dict[str, object]:
    indicators = {
        "schema_version": "scion.research_context_actionability_indicators.v1",
        "research_continuity_max_branch_depth": 1,
        "same_mechanism_selected": 0,
        "same_mechanism_observed": 0,
        "same_mechanism_missed": 0,
        "branch_lessons_satisfied": 0,
        "branch_lessons_required": 0,
        "branch_lesson_semantic_gap_count": 0,
        "branch_lesson_semantic_failure_count": 0,
        "branch_lesson_semantic_failure_counts": {},
        "branch_lesson_semantic_block_count": 0,
        "branch_lesson_semantic_block_counts": {},
        "weak_positive_accepted": 0,
        "weak_positive_observed": 0,
        "weak_positive_missed": 0,
        "research_signal_tokens": 4,
        "source_code_tokens": 2,
        "cross_branch_tokens": 1,
        "governance_tokens": 1,
        "omitted_section_trace_count": 0,
        "truncated_section_trace_count": 0,
        "hypothesis_generation_trace_count": 1,
        "hypothesis_generation_block_family_trace_count": 1,
        "hypothesis_generation_research_signal_tokens": 4,
        "hypothesis_generation_source_code_tokens": 2,
        "hypothesis_generation_cross_branch_tokens": 1,
        "hypothesis_generation_governance_tokens": 1,
        "research_plus_source_to_governance_ratio": 6.0,
        "hypothesis_generation_research_plus_source_to_governance_ratio": 6.0,
    }
    return {
        "schema_version": RESEARCH_CONTEXT_ACTIONABILITY_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "prompt_context_available": True,
        "research_continuity_available": True,
        "guidance_status": "research_context_actionability_evidence_available",
        "actionability_gaps": [],
        "recommendations": [],
        "indicators": indicators,
    }


def _branch_research_state_summary() -> dict[str, object]:
    aggregate = {
        "branch_count": 1,
        "lineage_count": 1,
        "branch_state_counts": {"active": 1},
        "branches_with_hypotheses": 1,
        "branches_with_events": 1,
        "branches_with_sessions": 1,
        "branches_with_traces": 1,
        "rollback_count_total": 0,
        "branches_with_rollback": 0,
        "failure_code_counts": {},
        "hypothesis_count": 1,
        "hypotheses_by_status": {"open": 1},
        "hypotheses_by_action": {"test": 1},
        "hypotheses_by_change_locus": {"core": 1},
        "events_by_kind": {"experiment": 1},
        "events_by_decision": {"continue": 1},
        "events_by_stage": {"analysis": 1},
    }
    return {
        "schema_version": BRANCH_RESEARCH_STATE_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "raw_prompts_excluded": True,
        "raw_responses_excluded": True,
        "patch_body_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "aggregate": aggregate,
        "top_branches": [{"branch_id": "branch-a", "hypothesis_count": 1}],
    }


def _champion_progress_summary() -> dict[str, object]:
    return {
        "schema_version": CHAMPION_PROGRESS_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "current_run_evidence": True,
        "available": True,
        "interpretation": "champion_version_gain_observed",
        "champion_table_present": True,
        "latest_promotion_experiment_id": "experiment-a",
        "latest_promotion_dossier_ref": "dossier-a",
        "starting_champion_version": 1,
        "current_champion_version": 2,
        "champion_version_gain": 1,
        "champion_count": 2,
        "max_weight_revision": 0,
        "promotion_experiment_count": 1,
        "promotion_dossier_count": 1,
        "promoted_at_count": 1,
        "promoted_hypothesis_count": 1,
        "promotion_decision_count": 1,
        "champion_versions": [1, 2],
    }


def _failure_taxonomy_summary() -> dict[str, object]:
    proposal_quality = {
        "proposal_attempts_total": 1,
        "proposal_attempts_consumed": 1,
        "proposal_quality_blocks": 0,
        "quality_blocks": 0,
        "quality_block_ledger_count": 0,
        "reports_with_quality_blocks": 0,
        "quality_block_reason_counts": {},
    }
    top_examples = [
        {"report": "report-a.json", "failure_key": "timeout", "example": "case-a"}
    ]
    entry = {
        "report": "report-a.json",
        "path": "/tmp/run/postrun/report-a.json",
        "proposal_quality": {**proposal_quality, "quality_block_reasons": []},
        "failure_taxonomy": {"timeout": {"observations": 1}},
        "failure_observations_total": 1,
        "top_failure_keys": ["timeout"],
        "top_examples": top_examples,
        "run_status": {
            "run_validity_status": "valid",
            "stopped_reason": "",
            "run_complete": True,
            "run_completeness_status": "complete",
            "wrapper_exit_status": 0,
            "campaign_exit_status": 0,
        },
    }
    return {
        "schema_version": FAILURE_TAXONOMY_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_logs_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "report_count": 1,
        "failure_report_count": 1,
        "aggregate": {
            "failure_count_maxima": {"timeout": 1},
            "failure_observation_counts": {"timeout": 1},
            "failure_source_counts": {"report": 1},
            "run_validity_status_counts": {"valid": 1},
            "stopped_reason_counts": {},
            "proposal_quality": proposal_quality,
            "top_examples": top_examples,
        },
        "entries": [entry],
    }
