from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


TOOL_PATH = Path(__file__).parents[2] / "tools" / "postrun_analysis_brief.py"
SPEC = importlib.util.spec_from_file_location("postrun_analysis_brief", TOOL_PATH)
assert SPEC is not None
brief_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(brief_tool)


def test_brief_json_and_markdown_from_inventory_inputs(tmp_path: Path) -> None:
    run_root = tmp_path / "run-a"
    campaign_dir = run_root / "campaign"
    traces_dir = campaign_dir / "llm_traces"
    sessions_dir = campaign_dir / "agentic_sessions"
    traces_dir.mkdir(parents=True)
    sessions_dir.mkdir()

    _write_json(
        run_root / "run_status.json",
        {
            "run_name": "normal-run",
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "requested_rounds": 1,
        },
    )
    (run_root / "run.log").write_text("POSTRUN_REPORT_DIR:/tmp/run\n", encoding="utf-8")
    (run_root / "exit.txt").write_text("WRAPPER_EXIT_STATUS:0\n", encoding="utf-8")
    (run_root / "command.txt").write_text("./run.sh\n", encoding="utf-8")
    (run_root / "launch.env").write_text("SCION_MODEL=gpt-5.5\n", encoding="utf-8")
    (run_root / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    _write_json(
        campaign_dir / "status.json",
        {"effective_rounds_completed": 1, "screened_experiments": 1},
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
            "runtime_budget_diagnostics": [
                {
                    "branch_id": "branch-1",
                    "stage": "screening",
                    "code": "SCREENING_RUNTIME_BUDGET_SATURATION",
                    "severity": "info",
                    "saturation_ratio": 0.99,
                    "threshold_ratio": 0.9,
                    "total_pairs": 32,
                }
            ],
        },
    )
    _write_json(
        sessions_dir / "agentic_session_trace_index.json",
        {
            "sessions": [
                {
                    "session_id": "s-1",
                    "branch_id": "branch-1",
                    "traces": [
                        {"trace_id": "t-hyp", "request_kind": "hypothesis"},
                        {"trace_id": "t-code", "request_kind": "code"},
                        {
                            "trace_id": "t-target",
                            "request_kind": "target_intent",
                            "prompt_manifest_ref": "manifest-1",
                        },
                    ],
                }
            ]
        },
    )
    _write_json(
        sessions_dir / "agentic_session_index.json",
        {"sessions": [{"session_id": "s-1", "branch_id": "branch-1"}]},
    )
    _write_json(
        traces_dir / "20260618T000000_target_intent_branch_1.json",
        {
            "request_kind": "target_intent",
            "ok": True,
            "branch_id": "branch-1",
            "prompt_manifest_ref": "manifest-1",
        },
    )
    _write_json(
        traces_dir / "20260618T000001_hypothesis_branch_1.json",
        {"request_kind": "hypothesis", "ok": True, "branch_id": "branch-1"},
    )
    _write_json(
        traces_dir / "20260618T000002_code_branch_1.json",
        {"request_kind": "code", "ok": True, "branch_id": "branch-1"},
    )
    formal_index = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    formal_index.parent.mkdir(parents=True)
    formal_index.write_text('{"candidate_id":"cand-1"}\n', encoding="utf-8")
    _write_json(
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "normal.research_efficiency.v1.json",
        {
            "effective_budget": {
                "counter": "effective_rounds_completed",
                "requested_rounds": 1,
                "effective_rounds_completed": 1,
                "completed_requested_rounds": True,
                "stopped_reason": "requested_rounds_complete",
                "semantics": "effective rounds, not proposal attempts",
            },
            "attempts": {
                "proposal_attempts_total": 3,
                "proposal_attempts_consumed": 2,
                "verification_consumed_candidates": 1,
                "verification_failure_consumed_candidates": 0,
            },
            "protocol_rows": {
                "effective_protocol_rounds": 1,
                "protocol_metric_results": 2,
                "protocol_evaluated_candidates": 1,
                "stage_counts": {"screening": 2, "validation": 0, "frozen": 0},
                "semantics": "completed protocol metric rows",
            },
            "formal_candidates": {
                "formal_screened_candidates": 1,
                "protocol_evaluated_candidates": 1,
                "semantics": "legacy formal screened counter",
            },
            "formal_candidate_artifacts": {
                "row_count": 1,
                "index_status": "available",
                "index_ref": "artifacts/formal_candidates/index.jsonl",
                "unreadable_rows": 0,
                "semantics": "formal candidate artifact rows",
            },
            "stage_rows": {
                "screening": 2,
                "validation": 0,
                "frozen": 0,
                "fresh_runtime_replay": 0,
            },
            "reconciliation": {
                "formal_candidate_count_reconciliation": {
                    "formal_candidates_index_status": "available"
                },
                "candidate_count_reconciliation": {
                    "candidate_count_status": "matched"
                },
                "accounting_reconciliation": {
                    "accounting_status": "consistent"
                },
            },
            "measurement_readiness": {
                "status": "ready",
                "reason_code": "ok",
                "mde_at_power_80": 9.9,
                "signal_to_noise_tier": "low_power",
            },
            "measurement_readiness_source": "summary_status",
            "protocol_effects_vs_mde": {
                "schema_version": "scion.research_efficiency_effect_vs_mde.v1",
                "report_only": True,
                "decision_features_excluded": True,
                "measurement_readiness_status": "ready",
                "mde_at_power_80": 9.9,
                "mde_source": "measurement_readiness.mde_at_power_80",
                "interpretation": "has_positive_protocol_effect_at_or_above_mde",
                "protocol_row_count": 2,
                "rows_at_or_above_mde": 1,
                "rows_with_ci_high_below_mde": 1,
                "positive_rows": 1,
                "nonpositive_rows": 1,
                "max_effect_to_mde_ratio": 1.212121,
                "by_stage": {
                    "screening": {
                        "protocol_row_count": 2,
                        "rows_at_or_above_mde": 1,
                    }
                },
                "top_rows_by_effect_to_mde": [
                    {
                        "round": 1,
                        "branch_id": "branch-1",
                        "stage": "screening",
                        "decision": "continue_explore",
                        "gate_outcome": "pass",
                        "median_delta": 12.0,
                        "ci_high": 14.0,
                        "win_rate": 0.6,
                        "effect_to_mde_ratio": 1.212121,
                        "positive_effect_at_or_above_mde": True,
                        "ci_high_below_mde": False,
                        "reason_codes": ["SCREENING_SIGNAL"],
                    }
                ],
            },
            "fresh_runtime_replay_drain": {
                "status": "not_selected_no_pending",
                "attempts": 1,
                "executed": 0,
                "skipped": 1,
                "blocked": 0,
                "protocol_results": 0,
                "stopped_reason": "no_fresh_runtime_replay_pending",
                "counts_toward_max_rounds": False,
            },
            "stage_transition_drain": {
                "status": "not_started",
                "attempts": 0,
                "executed": 0,
                "skipped": 0,
                "limit": 0,
                "stopped_reason": "",
                "counts_toward_max_rounds": False,
                "generates_new_hypothesis": False,
            },
            "proposal_quality": {
                "proposal_attempts_total": 3,
                "proposal_attempts_consumed": 2,
                "proposal_quality_blocks": 1,
                "quality_blocks": 1,
                "quality_block_ledger_count": 1,
                "quality_block_reasons": ["schema_missing_effect_path"],
                "semantics": "proposal/schema quality blocks before verification",
            },
            "failure_taxonomy": {
                "code_generation": {
                    "count": 1,
                    "observations": 2,
                    "source_counts": {"campaign_steps": 1, "run_log": 1},
                    "examples": [
                        "agentic_proposal:code_generation_failed old_string_not_found"
                    ],
                    "sources": [{"kind": "campaign_step", "index": 1}],
                },
                "tool_timeout": {
                    "count": 1,
                    "observations": 1,
                    "source_counts": {"run_log": 1},
                    "examples": ["Tool call timeout after 60s"],
                },
                "verification_heavy": {
                    "count": 0,
                    "observations": 0,
                    "source_counts": {},
                    "examples": [],
                },
            },
            "run_status": {
                "run_validity_status": "valid",
                "stopped_reason": "requested_rounds_complete",
                "run_complete": True,
                "run_completeness_status": "complete",
                "wrapper_exit_status": 0,
            },
            "research_continuity": {
                "same_mechanism_followup": {
                    "selected_same_branch_refinement_count": 1,
                    "not_selected_same_branch_refinement_count": 0,
                    "observed_opportunity_count": 1,
                    "selection_rate": 1.0,
                    "interpretation": (
                        "all_observed_same_mechanism_followups_selected"
                    ),
                },
                "branch_lesson_usage": {
                    "requirement_count": 2,
                    "present_count": 2,
                    "satisfied_count": 2,
                    "missing_block_count": 0,
                    "present_not_semantic_count": 0,
                    "satisfaction_rate": 1.0,
                    "present_rate": 1.0,
                    "semantic_gap_count": 0,
                    "semantic_gap_rate": 0.0,
                },
                "weak_positive_transfer": {
                    "accepted_count": 1,
                    "rejected_count": 0,
                    "observed_opportunity_count": 1,
                    "acceptance_rate": 1.0,
                },
                "lesson_action_counts": {
                    "preserved_same_branch": 2,
                },
                "research_shape_summary": {
                    "max_branch_depth": 3,
                    "mechanism_family_count": 2,
                },
            },
        },
    )
    _write_json(
        run_root
        / "postrun_acceptance"
        / "manifests"
        / "normal.proposal_trajectory_manifest.v1.json",
        {
            "counts": {"prompt_manifest_loaded_count": 1},
            "branch_lesson_usage_accounting": {
                "field_counts": {"avoided_lessons": 1}
            },
            "sessions": [
                {
                    "trace_fingerprints": [
                        {
                            "call_kind": "hypothesis",
                            "visibility_ledger_digest": "visibility-ledger-1",
                            "block_family_summary": {
                                "total_chars": 140,
                                "total_token_estimate": 35,
                                "families": {
                                    "research_signal": {
                                        "char_count": 80,
                                        "token_estimate": 20,
                                        "token_share": 0.571429,
                                    },
                                    "governance": {
                                        "char_count": 40,
                                        "token_estimate": 10,
                                        "token_share": 0.285714,
                                    },
                                    "cross_branch_lesson": {
                                        "char_count": 20,
                                        "token_estimate": 5,
                                        "token_share": 0.142857,
                                    },
                                },
                            },
                            "omitted_sections": ["hidden_validation"],
                            "truncated_sections": ["long_feedback"],
                        },
                        {
                            "call_kind": "code",
                            "visibility_ledger_digest": "visibility-ledger-2",
                            "block_family_summary": {
                                "total_chars": 80,
                                "total_token_estimate": 20,
                                "families": {
                                    "source_code": {
                                        "char_count": 60,
                                        "token_estimate": 15,
                                        "token_share": 0.75,
                                    },
                                    "governance": {
                                        "char_count": 20,
                                        "token_estimate": 5,
                                        "token_share": 0.25,
                                    },
                                },
                            },
                        },
                    ]
                }
            ],
        },
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    assert brief["schema_version"] == "scion.postrun_analysis_brief.v1"
    assert brief["report_only"] is True
    assert brief["quality_judgment"] is False
    assert brief["decision_features_excluded"] is True
    assert brief["campaign_state_mutated"] is False
    assert brief["scheduler_state_mutated"] is False
    assert brief["promotion_state_mutated"] is False
    assert brief["lifecycle"]["prepared_only"] is False
    assert brief["branches"]["ids"] == ["branch-1"]
    assert brief["phase4_evidence_coverage"]["requirements"]["target_intent_trace"][
        "available"
    ] is True
    accounting_summary = brief["protocol_accounting_summary"]
    assert accounting_summary["schema_version"] == (
        "scion.postrun_protocol_accounting_summary.v1"
    )
    assert accounting_summary["report_only"] is True
    assert accounting_summary["decision_features_excluded"] is True
    assert accounting_summary["available"] is True
    assert accounting_summary["current_run_evidence"] is True
    assert accounting_summary["accounting_report_count"] == 1
    assert accounting_summary["aggregate"] == {
        "effective_budget": {
            "counter_counts": {"effective_rounds_completed": 1},
            "requested_rounds": 1,
            "effective_rounds_completed": 1,
            "completed_requested_rounds_true": 1,
            "completed_requested_rounds_false": 0,
            "stopped_reason_counts": {"requested_rounds_complete": 1},
        },
        "attempts": {
            "proposal_attempts_total": 3,
            "proposal_attempts_consumed": 2,
            "verification_consumed_candidates": 1,
            "verification_failure_consumed_candidates": 0,
        },
        "protocol_rows": {
            "effective_protocol_rounds": 1,
            "protocol_metric_results": 2,
            "protocol_evaluated_candidates": 1,
            "stage_counts": {"frozen": 0, "screening": 2, "validation": 0},
        },
        "formal_screened_candidates": 1,
        "formal_protocol_evaluated_candidates": 1,
        "formal_candidate_artifacts": {
            "row_count": 1,
            "unreadable_rows": 0,
            "index_status_counts": {"available": 1},
        },
        "stage_rows": {
            "screening": 2,
            "validation": 0,
            "frozen": 0,
            "fresh_runtime_replay": 0,
        },
        "reconciliation_status_counts": {
            "available": 1,
            "consistent": 1,
            "matched": 1,
        },
    }
    accounting_entry = accounting_summary["entries"][0]
    assert accounting_entry["report"] == "normal.research_efficiency.v1.json"
    assert accounting_entry["effective_budget"]["completed_requested_rounds"] is True
    assert accounting_entry["formal_candidate_artifacts"]["index_status"] == (
        "available"
    )
    effect_summary = brief["measurement_effect_summary"]
    assert effect_summary["schema_version"] == (
        "scion.postrun_measurement_effect_summary.v1"
    )
    assert effect_summary["report_only"] is True
    assert effect_summary["decision_features_excluded"] is True
    assert effect_summary["available"] is True
    assert effect_summary["current_run_evidence"] is True
    assert effect_summary["aggregate"] == {
        "measurement_readiness_status_counts": {"ready": 1},
        "interpretation_counts": {
            "has_positive_protocol_effect_at_or_above_mde": 1
        },
        "protocol_row_count": 2,
        "rows_at_or_above_mde": 1,
        "rows_with_ci_high_below_mde": 1,
        "positive_rows": 1,
        "nonpositive_rows": 1,
        "max_effect_to_mde_ratio": 1.212121,
    }
    effect_entry = effect_summary["entries"][0]
    assert effect_entry["measurement_readiness"] == {
        "status": "ready",
        "reason_code": "ok",
        "mde_at_power_80": 9.9,
        "signal_to_noise_tier": "low_power",
    }
    assert effect_entry["protocol_effects_vs_mde"]["mde_at_power_80"] == 9.9
    assert effect_entry["protocol_effects_vs_mde"]["top_rows_by_effect_to_mde"] == [
        {
            "round": 1,
            "branch_id": "branch-1",
            "stage": "screening",
            "decision": "continue_explore",
            "gate_outcome": "pass",
            "median_delta": 12.0,
            "ci_high": 14.0,
            "win_rate": 0.6,
            "effect_to_mde_ratio": 1.212121,
            "positive_effect_at_or_above_mde": True,
            "ci_high_below_mde": False,
            "reason_codes": ["SCREENING_SIGNAL"],
        }
    ]
    runtime_summary = brief["runtime_feedback_summary"]
    assert runtime_summary["schema_version"] == (
        "scion.postrun_runtime_feedback_summary.v1"
    )
    assert runtime_summary["report_only"] is True
    assert runtime_summary["decision_features_excluded"] is True
    assert runtime_summary["available"] is True
    assert runtime_summary["current_run_evidence"] is True
    assert runtime_summary["runtime_report_count"] == 1
    assert runtime_summary["budget_diagnostic_source_count"] == 1
    runtime_aggregate = runtime_summary["aggregate"]
    assert runtime_aggregate["fresh_runtime_replay_drain"] == {
        "status_counts": {"not_selected_no_pending": 1},
        "stopped_reason_counts": {"no_fresh_runtime_replay_pending": 1},
        "attempts": 1,
        "executed": 0,
        "skipped": 1,
        "blocked": 0,
        "protocol_results": 0,
        "counts_toward_max_rounds_true": 0,
        "counts_toward_max_rounds_false": 1,
        "reports_with_unresolved_closures": 0,
    }
    assert runtime_aggregate["stage_transition_drain"] == {
        "status_counts": {"not_started": 1},
        "stopped_reason_counts": {"none": 1},
        "attempts": 0,
        "executed": 0,
        "skipped": 0,
        "counts_toward_max_rounds_true": 0,
        "counts_toward_max_rounds_false": 1,
        "generates_new_hypothesis_true": 0,
        "generates_new_hypothesis_false": 1,
    }
    assert runtime_aggregate["runtime_budget_diagnostics"] == {
        "source_count": 1,
        "diagnostic_count": 1,
        "code_counts": {"SCREENING_RUNTIME_BUDGET_SATURATION": 1},
        "severity_counts": {"info": 1},
        "stage_counts": {"screening": 1},
        "runtime_model_counts": {},
        "top_diagnostics": [
            {
                "branch_id": "branch-1",
                "stage": "screening",
                "code": "SCREENING_RUNTIME_BUDGET_SATURATION",
                "severity": "info",
                "saturation_ratio": 0.99,
                "threshold_ratio": 0.9,
                "total_pairs": 32,
            }
        ],
    }
    failure_summary = brief["failure_taxonomy_summary"]
    assert failure_summary["schema_version"] == (
        "scion.postrun_failure_taxonomy_summary.v1"
    )
    assert failure_summary["report_only"] is True
    assert failure_summary["decision_features_excluded"] is True
    assert failure_summary["raw_logs_excluded"] is True
    assert failure_summary["available"] is True
    assert failure_summary["current_run_evidence"] is True
    assert failure_summary["failure_report_count"] == 1
    failure_aggregate = failure_summary["aggregate"]
    assert failure_aggregate["proposal_quality"] == {
        "proposal_attempts_total": 3,
        "proposal_attempts_consumed": 2,
        "proposal_quality_blocks": 1,
        "quality_blocks": 1,
        "quality_block_ledger_count": 1,
        "reports_with_quality_blocks": 1,
        "quality_block_reason_counts": {"schema_missing_effect_path": 1},
    }
    assert failure_aggregate["failure_count_maxima"] == {
        "code_generation": 1,
        "tool_timeout": 1,
        "verification_heavy": 0,
    }
    assert failure_aggregate["failure_observation_counts"] == {
        "code_generation": 2,
        "tool_timeout": 1,
    }
    assert failure_aggregate["failure_source_counts"] == {
        "campaign_steps": 1,
        "run_log": 2,
    }
    assert failure_aggregate["run_validity_status_counts"] == {"valid": 1}
    assert failure_aggregate["stopped_reason_counts"] == {
        "requested_rounds_complete": 1
    }
    failure_entry = failure_summary["entries"][0]
    assert failure_entry["top_failure_keys"] == ["code_generation", "tool_timeout"]
    assert failure_entry["failure_observations_total"] == 3
    assert failure_entry["top_examples"] == [
        {
            "report": "normal.research_efficiency.v1.json",
            "failure_key": "code_generation",
            "example": "agentic_proposal:code_generation_failed old_string_not_found",
        },
        {
            "report": "normal.research_efficiency.v1.json",
            "failure_key": "tool_timeout",
            "example": "Tool call timeout after 60s",
        },
    ]
    context_summary = brief["prompt_context_visibility_summary"]
    assert context_summary["schema_version"] == (
        "scion.postrun_prompt_context_visibility_summary.v1"
    )
    assert context_summary["report_only"] is True
    assert context_summary["decision_features_excluded"] is True
    assert context_summary["raw_prompt_excluded"] is True
    assert context_summary["raw_response_excluded"] is True
    assert context_summary["patch_body_excluded"] is True
    assert context_summary["available"] is True
    assert context_summary["current_run_evidence"] is True
    aggregate = context_summary["aggregate"]
    assert aggregate["prompt_manifest_loaded_count"] == 1
    assert aggregate["trace_count"] == 2
    assert aggregate["visibility_digest_count"] == 2
    assert aggregate["block_family_trace_count"] == 2
    assert aggregate["omitted_section_trace_count"] == 1
    assert aggregate["truncated_section_trace_count"] == 1
    assert aggregate["call_kind_counts"] == {"code": 1, "hypothesis": 1}
    assert aggregate["block_family_totals"] == {
        "governance": {"char_count": 60, "token_estimate": 15, "trace_count": 2},
        "cross_branch_lesson": {
            "char_count": 20,
            "token_estimate": 5,
            "trace_count": 1,
        },
        "research_signal": {
            "char_count": 80,
            "token_estimate": 20,
            "trace_count": 1,
        },
        "source_code": {"char_count": 60, "token_estimate": 15, "trace_count": 1},
    }
    assert aggregate["signal_density"] == {
        "schema_version": "scion.postrun_prompt_signal_density.v1",
        "report_only": True,
        "decision_features_excluded": True,
        "total_token_estimate": 55,
        "research_signal_tokens": 20,
        "source_code_tokens": 15,
        "cross_branch_tokens": 5,
        "governance_tokens": 15,
        "research_signal_share": 0.363636,
        "source_code_share": 0.272727,
        "cross_branch_share": 0.090909,
        "governance_share": 0.272727,
        "research_plus_source_to_governance_ratio": 2.333333,
        "interpretation": "research_and_source_signal_at_least_governance",
    }
    continuity = brief["research_continuity_summary"]
    assert continuity["schema_version"] == (
        "scion.postrun_research_continuity_summary.v1"
    )
    assert continuity["report_only"] is True
    assert continuity["decision_features_excluded"] is True
    assert continuity["available"] is True
    assert continuity["current_run_evidence"] is True
    assert continuity["report_count"] == 1
    assert continuity["continuity_report_count"] == 1
    continuity_entry = continuity["entries"][0]
    assert continuity_entry["report"] == "normal.research_efficiency.v1.json"
    assert continuity_entry["same_mechanism_followup"]["selection_rate"] == 1.0
    assert continuity_entry["branch_lesson_usage"]["semantic_gap_count"] == 0
    assert continuity_entry["weak_positive_transfer"]["acceptance_rate"] == 1.0
    checklist = {item["name"]: item["present"] for item in brief["artifact_checklist"]}
    assert checklist["outer_command"] is True
    assert checklist["campaign_database"] is False
    assert checklist["prepared_run_manifest_json"] is False
    assert checklist["prepared_handoff"] is False
    assert brief["prepared_run_contract"]["schema_version"] == (
        "scion.prepared_run_contract_inventory.v1"
    )
    assert brief["prepared_run_contract"]["report_only"] is True
    assert brief["prepared_run_contract"]["quality_judgment"] is False
    assert brief["prepared_run_contract"]["decision_features_excluded"] is True
    assert brief["prepared_run_contract"]["contract_complete"] is False
    assert brief["prepared_run_contract"]["acceptance_focus"] == []
    assert "## Minimum Delegated Analysis" in markdown
    assert "## Prepared Run Contract" in markdown
    assert "Acceptance focus" in markdown
    assert "DecisionFeatures" in markdown
    assert "| target_intent_trace | True | 1 | llm_traces or trace_index |" in markdown
    assert "## Protocol Accounting Summary" in markdown
    assert "- Requested/effective rounds: 1 / 1" in markdown
    assert (
        "| normal.research_efficiency.v1.json | 1 | 1 | 2 | "
        "1 | 2/0/0/0 | requested_rounds_complete |"
        in markdown
    )
    assert "## Measurement Effect Summary" in markdown
    assert (
        "| normal.research_efficiency.v1.json | ready | 9.9 | "
        "has_positive_protocol_effect_at_or_above_mde | 2 | 1 | 1 | 1.212121 |"
        in markdown
    )
    assert "## Research Continuity Summary" in markdown
    assert "## Runtime Feedback Summary" in markdown
    assert "- Runtime budget diagnostics: 1" in markdown
    assert (
        "| normal.research_efficiency.v1.json | not_selected_no_pending | "
        "1 | 0 | 1 | 0 | 0 | not_started |"
        in markdown
    )
    assert "## Failure Taxonomy Summary" in markdown
    assert "- Quality block reasons: schema_missing_effect_path=1" in markdown
    assert (
        "| normal.research_efficiency.v1.json | 1 | 3 | "
        "code_generation, tool_timeout | valid | requested_rounds_complete |"
        in markdown
    )
    assert "## Prompt Context Visibility Summary" in markdown
    assert "- Prompt manifests loaded/ref: 1 / 0" in markdown
    assert (
        "- Signal density shares: 0.363636 / 0.272727 / 0.090909 / 0.272727"
        in markdown
    )
    assert "- Research+source/governance ratio: 2.333333" in markdown
    assert "| source_code | 1 | 15 | 60 |" in markdown
    assert (
        "| normal.research_efficiency.v1.json | 1/1 | 2/2 | 0 | 1/1 | 3 | 2 |"
        in markdown
    )
    assert any(
        "research_continuity" in question
        for question in brief["required_questions"]
    )
    assert any(
        "runtime_feedback_summary" in question
        for question in brief["required_questions"]
    )
    assert any(
        "failure_taxonomy_summary" in question
        for question in brief["required_questions"]
    )

    result = subprocess.run(
        [sys.executable, str(TOOL_PATH), str(run_root), "--format", "json"],
        text=True,
        capture_output=True,
        check=True,
    )
    cli_brief = json.loads(result.stdout)
    assert cli_brief["schema_version"] == "scion.postrun_analysis_brief.v1"


def test_brief_marks_prepared_only_root_as_not_launched(tmp_path: Path) -> None:
    run_root = tmp_path / "prepared-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "scion.launcher_prepare.v1",
            "status": "prepared",
            "prepared_only": True,
            "resume_from_campaign": "/tmp/source-campaign",
            "copied_campaign_status_present": True,
            "copied_campaign_summary_present": True,
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "execution": {"rounds": 2},
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "run_status.json",
        {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "effective_rounds_completed": 9,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 9,
            "protocol_evaluated_candidates": 9,
        },
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    assert brief["lifecycle"]["prepared_only"] is True
    assert brief["validity"]["run_validity_status"] == "prepared_only"
    assert brief["validity"]["run_completeness_status"] == "not_started"
    assert brief["counters"]["requested_rounds"] == 2
    assert brief["counters"]["effective_rounds_completed"] == 0
    assert any("PREPARED-ONLY ROOT" in item for item in brief["stop_conditions"])
    assert brief["phase4_evidence_coverage"]["prepared_only"] is True
    assert brief["protocol_accounting_summary"]["current_run_evidence"] is False
    assert brief["protocol_accounting_summary"]["available"] is False
    assert brief["measurement_effect_summary"]["current_run_evidence"] is False
    assert brief["measurement_effect_summary"]["available"] is False
    assert brief["runtime_feedback_summary"]["current_run_evidence"] is False
    assert brief["runtime_feedback_summary"]["available"] is False
    assert brief["failure_taxonomy_summary"]["current_run_evidence"] is False
    assert brief["failure_taxonomy_summary"]["available"] is False
    assert brief["prompt_context_visibility_summary"]["current_run_evidence"] is False
    assert brief["prompt_context_visibility_summary"]["available"] is False
    assert brief["research_continuity_summary"]["current_run_evidence"] is False
    assert brief["research_continuity_summary"]["available"] is False
    assert markdown.startswith("# Prepared Analysis Brief:")
    assert "do not analyze copied campaign artifacts as current-run research evidence" in (
        markdown
    )


def test_brief_stop_conditions_for_invalid_infra_run(tmp_path: Path) -> None:
    run_root = tmp_path / "infra-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_validity_status": "invalid_infra_only",
            "invalid_infra_only": True,
            "requested_rounds": 1,
        },
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    assert any("INVALID INFRA-ONLY RUN" in item for item in brief["stop_conditions"])
    assert any("No effective rounds" in item for item in brief["stop_conditions"])
    assert "INVALID INFRA-ONLY RUN" in markdown
    assert "do not analyze as research behavior" in markdown


def test_brief_exposes_resume_snapshot_without_current_run_evidence(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "preflight-failed-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "outer-wrapper.v1",
            "status": "finished",
            "wrapper_exit_status": 64,
            "pre_campaign_completion_preflight": "failed",
            "pre_campaign_completion_preflight_classification": (
                "not_authenticated"
            ),
            "pre_campaign_completion_preflight_login_url_present": True,
        },
    )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "execution": {"rounds": 5},
            "resume_from_campaign": "/tmp/source-campaign",
        },
    )
    _write_json(
        campaign_dir / "run_status.json",
        {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "effective_rounds_completed": 7,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 7,
            "measurement_readiness": {"status": "ready"},
        },
    )
    traces_dir = campaign_dir / "llm_traces"
    traces_dir.mkdir()
    _write_json(
        traces_dir / "20260606T000000_hypothesis_branch_1.json",
        {"request_kind": "hypothesis", "ok": True, "branch_id": "branch-1"},
    )
    _write_json(
        campaign_dir / "agentic_sessions" / "agentic_session_trace_index.json",
        {
            "session_count": 1,
            "trace_count": 1,
            "sessions": [
                {
                    "session_id": "s-1",
                    "branch_id": "branch-1",
                    "traces": [{"trace_id": "t-hyp", "request_kind": "hypothesis"}],
                }
            ],
        },
    )
    _write_db(campaign_dir / "scion.db")

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    assert brief["validity"]["run_validity_status"] == "invalid_infra_only"
    assert brief["counters"]["effective_rounds_completed"] == 0
    assert brief["branches"]["count"] == 0
    assert brief["branches"]["ids"] == []
    assert brief["llm_traces"]["trace_count"] == 0
    assert brief["resume_snapshot"]["present"] is True
    assert brief["protocol_accounting_summary"]["current_run_evidence"] is False
    assert brief["protocol_accounting_summary"]["available"] is False
    assert brief["measurement_effect_summary"]["current_run_evidence"] is False
    assert brief["measurement_effect_summary"]["available"] is False
    assert brief["runtime_feedback_summary"]["current_run_evidence"] is False
    assert brief["runtime_feedback_summary"]["available"] is False
    assert brief["failure_taxonomy_summary"]["current_run_evidence"] is False
    assert brief["failure_taxonomy_summary"]["available"] is False
    assert brief["prompt_context_visibility_summary"]["current_run_evidence"] is False
    assert brief["prompt_context_visibility_summary"]["available"] is False
    assert brief["research_continuity_summary"]["current_run_evidence"] is False
    assert brief["research_continuity_summary"]["available"] is False
    assert brief["resume_snapshot"]["current_run_evidence"] is False
    assert brief["resume_snapshot"]["resume_from_campaign"] == "/tmp/source-campaign"
    assert brief["resume_snapshot"]["branch_count"] == 1
    assert brief["resume_snapshot"]["llm_trace_count"] == 1
    assert brief["resume_snapshot"]["hypothesis_count"] == 2
    assert brief["resume_snapshot"]["events_by_kind"] == {
        "decision": 1,
        "experiment": 2,
    }
    assert "## Resume Snapshot" in markdown
    assert "Copied campaign artifacts are launch input, not current-run evidence" in (
        markdown
    )
    assert "- Current-run evidence: `False`" in markdown
    assert "- Branch count: 0" in markdown
    assert "- LLM trace files: 0" in markdown


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE branches (
                branch_id TEXT PRIMARY KEY,
                state TEXT,
                lineage_id TEXT,
                base_champion_hash TEXT,
                current_code_hash TEXT,
                best_quality_checkpoint_id TEXT,
                last_valid_checkpoint_id TEXT,
                rollback_count INTEGER,
                failure_codes TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE hypotheses (
                hypothesis_id TEXT PRIMARY KEY,
                branch_id TEXT,
                change_locus TEXT,
                action TEXT,
                status TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE experiment_events (
                event_id TEXT PRIMARY KEY,
                branch_id TEXT,
                event_kind TEXT,
                decision TEXT,
                stage TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO branches VALUES (
                'branch-1', 'ready_validate', 'lineage-1', 'basehash',
                'codehash', 'checkpoint-best', 'checkpoint-last', 1,
                '["CONTRACT"]'
            )
            """
        )
        conn.executemany(
            "INSERT INTO hypotheses VALUES (?, ?, ?, ?, ?)",
            [
                ("hyp-1", "branch-1", "solver_design", "modify", "active"),
                ("hyp-2", "branch-1", "solver_design", "create_new", "rejected"),
            ],
        )
        conn.executemany(
            "INSERT INTO experiment_events VALUES (?, ?, ?, ?, ?)",
            [
                ("event-1", "branch-1", "experiment", "continue_explore", "screening"),
                ("event-2", "branch-1", "experiment", "queue_validate", "screening"),
                ("event-3", "branch-1", "decision", None, None),
            ],
        )
