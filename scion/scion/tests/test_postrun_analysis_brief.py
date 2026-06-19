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
                "mechanism_family_effect_summary": {
                    "schema_version": "scion.mechanism_family_effect_summary.v1",
                    "report_only": True,
                    "decision_features_excluded": True,
                    "mapping_status": "available",
                    "mapped_row_count": 2,
                    "unmapped_row_count": 0,
                    "mechanism_family_count": 1,
                    "by_family": {
                        "regret_insertion": {
                            "protocol_row_count": 2,
                            "rows_with_median_delta": 2,
                            "positive_rows": 1,
                            "nonpositive_rows": 1,
                            "rows_at_or_above_mde": 1,
                            "rows_below_mde": 1,
                            "rows_with_ci_high_below_mde": 1,
                            "max_median_delta": 12.0,
                            "max_effect_to_mde_ratio": 1.212121,
                        }
                    },
                },
                "top_rows_by_effect_to_mde": [
                    {
                        "round": 1,
                        "branch_id": "branch-1",
                        "mechanism_family": "regret_insertion",
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
                    "requirement_count": 3,
                    "present_count": 3,
                    "satisfied_count": 2,
                    "missing_block_count": 0,
                    "present_not_semantic_count": 1,
                    "metadata_only_count": 0,
                    "metadata_only_block_count": 0,
                    "linkage_unrecognized_count": 0,
                    "linkage_unrecognized_block_count": 0,
                    "semantic_mismatch_count": 1,
                    "semantic_mismatch_block_count": 1,
                    "semantic_failure_counts": {"semantic_mismatch": 1},
                    "semantic_block_counts": {"semantic_mismatch": 1},
                    "satisfaction_rate": 0.666667,
                    "present_rate": 1.0,
                    "semantic_gap_count": 1,
                    "semantic_gap_rate": 0.333333,
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
                    "mean_branch_depth": 2.0,
                    "branch_depth_distribution": {"1": 1, "3": 1},
                    "active_shape": "deep_focused",
                    "active_branch_count": 1,
                    "active_mechanism_family_count": 1,
                    "mechanism_family_count": 2,
                },
            },
            "research_shape": {
                "schema_version": "campaign_research_shape_diagnostics.v1",
                "decision_features_excluded": True,
                "branch_depth_distribution": {"1": 1, "3": 1},
                "branch_depth_by_branch": {"branch-1": 3},
                "max_branch_depth": 3,
                "mean_branch_depth": 2.0,
                "active_research_shape_signal": {
                    "active_branch_count": 1,
                    "active_branch_ids": ["branch-1"],
                    "active_mechanism_family_count": 1,
                    "active_mechanism_families": ["regret_insertion"],
                    "shape": "deep_focused",
                },
                "mechanism_family_breadth": {
                    "family_count": 2,
                    "families": {
                        "regret_insertion": 3,
                        "route_merge": 1,
                    },
                },
                "branch_mechanism_family_map": {
                    "branch-1": {
                        "primary_family": "regret_insertion",
                        "families": {"regret_insertion": 3},
                        "sources": {"step_history": 3},
                    }
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
                            "source_visibility_summary": {
                                "schema_version": (
                                    "scion.prompt_source_visibility_fingerprint.v1"
                                ),
                                "hypothesis_target_source_visibility": {
                                    "schema_version": (
                                        "hypothesis-target-source-visibility-ledger.v1"
                                    ),
                                    "target_source_required": True,
                                    "visibility_status": (
                                        "full_dedicated_source_visible"
                                    ),
                                    "preflight_section_status": "included",
                                    "owner_source_visible": True,
                                },
                            },
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
                            "source_visibility_summary": {
                                "schema_version": (
                                    "scion.prompt_source_visibility_fingerprint.v1"
                                ),
                                "code_phase_guarantees": {
                                    "schema_version": (
                                        "code-phase-source-visibility-guarantees.v1"
                                    ),
                                    "target_source_visible": True,
                                    "required_integration_source_visible": True,
                                    "algorithm_file_read_source_visible": True,
                                    "protected_source_visible": True,
                                    "target_file_create_mode": False,
                                    "required_integration_source_count": 1,
                                    "algorithm_file_read_source_count": 1,
                                    "missing_required_source_paths": [],
                                },
                                "code_file_visibility": {
                                    "schema_version": "code-file-visibility-ledger.v1",
                                    "target_source_status": "current_branch_source",
                                    "target_source_provenance": "branch_workspace",
                                    "target_prompt_visibility_status": (
                                        "full_current_source_visible"
                                    ),
                                    "target_full_content_visible": True,
                                    "integration_file_count": 1,
                                    "integration_files_full_content_visible_count": 1,
                                    "algorithm_file_read_count": 1,
                                    "algorithm_file_reads_full_content_visible_count": 1,
                                },
                                "active_subject_code_constraints_visibility": {
                                    "schema_version": (
                                        "active-subject-code-constraints-visibility.v1"
                                    ),
                                    "required": True,
                                    "section_present": True,
                                    "section_status": "included",
                                    "section_visible": True,
                                    "full_section_visible": True,
                                    "payload_digest": "constraint-digest-1",
                                    "constraint_count": 3,
                                    "object_model_hint_count": 1,
                                    "api_contract_count": 1,
                                    "forbidden_pattern_count": 1,
                                    "missing_reason": "",
                                },
                            },
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
    _write_db(campaign_dir / "scion.db")

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
    branch_state = brief["branch_research_state_summary"]
    assert branch_state["schema_version"] == (
        "scion.postrun_branch_research_state_summary.v1"
    )
    assert branch_state["report_only"] is True
    assert branch_state["decision_features_excluded"] is True
    assert branch_state["raw_prompts_excluded"] is True
    assert branch_state["raw_responses_excluded"] is True
    assert branch_state["patch_body_excluded"] is True
    assert branch_state["available"] is True
    assert branch_state["current_run_evidence"] is True
    assert branch_state["aggregate"] == {
        "branch_count": 1,
        "lineage_count": 1,
        "branch_state_counts": {"ready_validate": 1},
        "branches_with_hypotheses": 1,
        "branches_with_events": 1,
        "branches_with_sessions": 1,
        "branches_with_traces": 1,
        "rollback_count_total": 1,
        "branches_with_rollback": 1,
        "failure_code_counts": {"CONTRACT": 1},
        "hypothesis_count": 2,
        "hypotheses_by_status": {"active": 1, "rejected": 1},
        "hypotheses_by_action": {"create_new": 1, "modify": 1},
        "hypotheses_by_change_locus": {"solver_design": 2},
        "events_by_kind": {"decision": 1, "experiment": 2},
        "events_by_decision": {"continue_explore": 1, "queue_validate": 1},
        "events_by_stage": {"screening": 2},
    }
    assert branch_state["top_branches"] == [
        {
            "branch_id": "branch-1",
            "state": "ready_validate",
            "lineage_id": "lineage-1",
            "hypothesis_count": 2,
            "event_count": 3,
            "session_count": 1,
            "trace_count": 3,
            "rollback_count": 1,
            "failure_codes": ["CONTRACT"],
        }
    ]
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
        "mechanism_family_mapped_row_count": 2,
        "mechanism_family_unmapped_row_count": 0,
        "mechanism_family_effects": {
            "regret_insertion": {
                "protocol_row_count": 2,
                "rows_with_median_delta": 2,
                "positive_rows": 1,
                "nonpositive_rows": 1,
                "rows_at_or_above_mde": 1,
                "rows_below_mde": 1,
                "rows_with_ci_high_below_mde": 1,
                "max_median_delta": 12.0,
                "max_effect_to_mde_ratio": 1.212121,
            }
        },
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
            "mechanism_family": "regret_insertion",
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
    assert aggregate["source_visibility"] == {
        "schema_version": "scion.postrun_prompt_source_visibility_summary.v1",
        "report_only": True,
        "decision_features_excluded": True,
        "trace_count": 2,
        "code_trace_count": 1,
        "code_target_source_visible_count": 1,
        "code_target_source_missing_count": 0,
        "code_protected_source_visible_count": 1,
        "code_protected_source_missing_count": 0,
        "code_required_integration_source_visible_count": 1,
        "code_algorithm_file_read_source_visible_count": 1,
        "code_missing_required_source_trace_count": 0,
        "code_missing_required_source_path_counts": {},
        "code_target_source_status_counts": {"current_branch_source": 1},
        "code_target_visibility_status_counts": {
            "full_current_source_visible": 1
        },
        "hypothesis_target_source_trace_count": 1,
        "hypothesis_target_source_required_count": 1,
        "hypothesis_target_source_visible_count": 1,
        "hypothesis_target_source_not_visible_count": 0,
        "hypothesis_target_visibility_status_counts": {
            "full_dedicated_source_visible": 1
        },
        "active_subject_code_constraints_trace_count": 1,
        "active_subject_code_constraints_required_count": 1,
        "active_subject_code_constraints_full_visible_count": 1,
        "active_subject_code_constraints_partial_visible_count": 0,
        "active_subject_code_constraints_not_full_visible_count": 0,
        "active_subject_code_constraints_not_required_count": 0,
        "active_subject_code_constraints_constraint_count_total": 3,
        "active_subject_code_constraints_forbidden_pattern_count_total": 1,
        "active_subject_code_constraints_status_counts": {"included": 1},
        "active_subject_code_constraints_missing_reason_counts": {"none": 1},
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
    assert continuity_entry["branch_lesson_usage"]["semantic_gap_count"] == 1
    assert continuity_entry["branch_lesson_usage"]["semantic_failure_counts"] == {
        "semantic_mismatch": 1
    }
    assert continuity_entry["weak_positive_transfer"]["acceptance_rate"] == 1.0
    assert continuity["aggregate"] == {
        "max_branch_depth": 3,
        "mean_branch_depth_max": 2.0,
        "branch_depth_distribution": {"1": 1, "3": 1},
        "active_shape_counts": {"deep_focused": 1},
        "active_branch_count_max": 1,
        "active_mechanism_family_count_max": 1,
        "mechanism_family_count_max": 2,
        "mechanism_family_counts": {
            "regret_insertion": 3,
            "route_merge": 1,
        },
        "branch_lesson_semantic_failure_counts": {"semantic_mismatch": 1},
        "branch_lesson_semantic_block_counts": {"semantic_mismatch": 1},
        "lesson_action_counts": {
            "preserved_same_branch": 2,
        },
    }
    actionability = brief["research_context_actionability_summary"]
    assert actionability == {
        "schema_version": (
            "scion.postrun_research_context_actionability_summary.v1"
        ),
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "prompt_context_available": True,
        "research_continuity_available": True,
        "guidance_status": "context_actionability_review_required",
        "indicators": {
            "schema_version": "scion.research_context_actionability_indicators.v1",
            "same_mechanism_selected": 1,
            "same_mechanism_observed": 1,
            "same_mechanism_missed": 0,
            "branch_lessons_satisfied": 2,
            "branch_lessons_required": 3,
            "branch_lesson_semantic_gap_count": 1,
            "branch_lesson_semantic_failure_count": 1,
            "branch_lesson_semantic_failure_counts": {
                "semantic_mismatch": 1,
            },
            "branch_lesson_semantic_block_count": 1,
            "branch_lesson_semantic_block_counts": {
                "semantic_mismatch": 1,
            },
            "weak_positive_accepted": 1,
            "weak_positive_observed": 1,
            "weak_positive_missed": 0,
            "research_signal_tokens": 20,
            "source_code_tokens": 15,
            "cross_branch_tokens": 5,
            "governance_tokens": 15,
            "research_plus_source_to_governance_ratio": 2.333333,
            "omitted_section_trace_count": 1,
            "truncated_section_trace_count": 1,
        },
        "actionability_gaps": [
            "branch_lesson_semantic_gap_despite_cross_branch_prompt_signal",
            "research_signal_sections_omitted_or_truncated_during_semantic_gap",
        ],
        "recommendations": [
            "inspect branch_lesson_usage records for semantic mismatch causes",
            "inspect omitted_sections and truncated_sections in prompt manifests",
            "inspect lesson ids, changed dimensions, and borrow/contrast/reject semantics",
        ],
    }
    checklist = {item["name"]: item["present"] for item in brief["artifact_checklist"]}
    assert checklist["outer_command"] is True
    assert checklist["campaign_database"] is True
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
    assert "## Branch Research State Summary" in markdown
    assert "- Branches / lineages: 1 / 1" in markdown
    assert "- Branch states: ready_validate=1" in markdown
    assert (
        "| branch-1 | ready_validate | lineage-1 | 2 | 3 | 1 | 3 | 1 | CONTRACT |"
        in markdown
    )
    assert "## Protocol Accounting Summary" in markdown
    assert "- Requested/effective rounds: 1 / 1" in markdown
    assert (
        "| normal.research_efficiency.v1.json | 1 | 1 | 2 | "
        "1 | 2/0/0/0 | requested_rounds_complete |"
        in markdown
    )
    assert "## Measurement Effect Summary" in markdown
    assert "- Mechanism-family mapped/unmapped rows: 2 / 0" in markdown
    assert "| regret_insertion | 2 | 1 | 1 | 1 | 1 | 1.212121 |" in markdown
    assert (
        "| normal.research_efficiency.v1.json | ready | 9.9 | "
        "has_positive_protocol_effect_at_or_above_mde | 2 | 1 | 1 | 1.212121 |"
        in markdown
    )
    assert "## Research Continuity Summary" in markdown
    assert "- Branch depth distribution: 1=1, 3=1" in markdown
    assert "- Active shapes: deep_focused=1" in markdown
    assert "- Mechanism family observations: regret_insertion=3, route_merge=1" in markdown
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
    assert "- Code source visibility traces: 1" in markdown
    assert (
        "- Hypothesis target source traces/required/visible/not-visible: "
        "1 / 1 / 1 / 0"
        in markdown
    )
    assert (
        "- Active subject code constraints traces/required/full-visible/not-full-visible: "
        "1 / 1 / 1 / 0"
        in markdown
    )
    assert (
        "- Signal density shares: 0.363636 / 0.272727 / 0.090909 / 0.272727"
        in markdown
    )
    assert "- Research+source/governance ratio: 2.333333" in markdown
    assert "| source_code | 1 | 15 | 60 |" in markdown
    assert (
        "| normal.research_efficiency.v1.json | 1/1 | 2/3 | 1 | 1/1 | "
        "3 | 1=1, 3=1 | deep_focused | 2 |"
        in markdown
    )
    assert "- Branch lesson semantic failures: semantic_mismatch=1" in markdown
    assert "- Branch lesson semantic blocks: semantic_mismatch=1" in markdown
    assert "- Branch lesson actions: preserved_same_branch=2" in markdown
    assert "## Research Context Actionability Summary" in markdown
    assert "- Guidance status: context_actionability_review_required" in markdown
    assert "- Continuity selected/observed same-mechanism follow-up: 1 / 1" in markdown
    assert "- Branch lessons satisfied/required/semantic gap: 2 / 3 / 1" in markdown
    assert "- Branch lesson semantic failure mix: semantic_mismatch=1" in markdown
    assert "- Branch lesson semantic block mix: semantic_mismatch=1" in markdown
    assert (
        "- Prompt research/source/cross-branch/governance tokens: 20 / 15 / 5 / 15"
        in markdown
    )
    assert (
        "branch_lesson_semantic_gap_despite_cross_branch_prompt_signal"
        in markdown
    )
    assert any(
        "research_continuity" in question
        for question in brief["required_questions"]
    )
    assert any(
        "research_context_actionability_summary" in question
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


def test_research_context_actionability_projects_branch_lesson_reason_mix() -> None:
    summary = brief_tool._research_context_actionability_summary(
        prompt_context_visibility_summary={
            "current_run_evidence": True,
            "available": True,
            "aggregate": {
                "signal_density": {
                    "research_signal_tokens": 12,
                    "source_code_tokens": 5,
                    "cross_branch_tokens": 4,
                    "governance_tokens": 7,
                }
            },
        },
        research_continuity_summary={
            "current_run_evidence": True,
            "available": True,
            "aggregate": {
                "branch_lesson_semantic_failure_counts": {
                    "metadata_only": 2,
                    "linkage_unrecognized": 1,
                },
                "branch_lesson_semantic_block_counts": {
                    "linkage_unrecognized": 1,
                },
            },
            "entries": [],
        },
    )

    indicators = summary["indicators"]
    assert indicators["branch_lesson_semantic_failure_count"] == 3
    assert indicators["branch_lesson_semantic_failure_counts"] == {
        "linkage_unrecognized": 1,
        "metadata_only": 2,
    }
    assert indicators["branch_lesson_semantic_block_count"] == 1
    assert indicators["branch_lesson_semantic_block_counts"] == {
        "linkage_unrecognized": 1,
    }
    assert summary["actionability_gaps"] == [
        "branch_lesson_semantic_gap_despite_cross_branch_prompt_signal"
    ]
    assert (
        "inspect hypotheses that filled branch_lesson_usage with metadata-only payloads"
        in summary["recommendations"]
    )
    assert (
        "normalize branch_lesson_usage target/action/mechanism linkage aliases"
        in summary["recommendations"]
    )


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
    assert brief["branch_research_state_summary"]["current_run_evidence"] is False
    assert brief["branch_research_state_summary"]["available"] is False
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
    assert any(
        "prepared-only launch root" in question
        for question in brief["required_questions"]
    )
    assert not any(
        "Did the agent perform effective research" in question
        for question in brief["required_questions"]
    )
    assert markdown.startswith("# Prepared Analysis Brief:")
    assert "do not analyze copied campaign artifacts as current-run research evidence" in (
        markdown
    )
    assert "Inspect prepared_run_contract, launch_readiness" in markdown
    assert "If completion preflight failed, verify operator_action/login status" in (
        markdown
    )
    assert "Start branch-centric, then round/LLM-call centric" not in markdown
    assert "For valid runs, inspect target intent" not in markdown


def test_warehouse_followup_summary_prepared_only_requires_launch(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "warehouse-prepared"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "scion.launcher_prepare.v1",
            "status": "prepared",
            "prepared_only": True,
            "resume_from_campaign": "/tmp/warehouse-source",
        },
    )
    _write_warehouse_manifest(run_root, campaign_dir, rounds=6)

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["warehouse_followup_summary"]
    assert summary["schema_version"] == (
        "scion.postrun_warehouse_followup_summary.v1"
    )
    assert summary["report_only"] is True
    assert summary["quality_judgment"] is False
    assert summary["decision_features_excluded"] is True
    assert summary["available"] is True
    assert summary["current_run_evidence"] is False
    assert summary["launch_required_before_plateau_conclusion"] is True
    assert summary["interpretation"] == "prepared_only_launch_required"
    assert summary["handoff_complete"] is True
    assert all(
        item["available"] is True
        for item in summary["handoff_requirements"].values()
    )
    assert summary["evidence_gaps"] == [
        "launch_required_before_plateau_conclusion"
    ]
    assert summary["deferred_review_axes"] == list(
        brief_tool.WAREHOUSE_FOLLOWUP_REVIEW_AXES
    )
    assert summary["review_axes_actionability"] == (
        "not_actionable_before_launch_current_run_evidence_required"
    )
    assert "## Warehouse Follow-up Summary" in markdown
    assert "- Interpretation: prepared_only_launch_required" in markdown
    assert (
        "prepared warehouse research_focus handoff; current-run protocol" in markdown
    )
    assert "- Deferred post-launch warehouse review axes:" in markdown
    assert "- Required warehouse review axes:" not in markdown
    assert "not_actionable_before_launch_current_run_evidence_required" in markdown
    assert (
        "| warehouse_required_evidence_handoff | True | 1 | "
        "prepared_run_manifest warehouse research_focus required_evidence |"
        in markdown
    )
    assert any(
        "warehouse_followup_summary" in question
        and "incomplete-handoff" in question
        for question in brief["required_questions"]
    )
    assert any(
        "not a research-quality" in question
        for question in brief["required_questions"]
    )
    assert not any(
        "cvrp_large_twoopt_summary" in question
        for question in brief["required_questions"]
    )


def test_cvrp_large_twoopt_summary_prepared_only_requires_launch(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "cvrp-prepared"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "schema": "scion.launcher_prepare.v1",
            "status": "prepared",
            "prepared_only": True,
            "resume_from_campaign": "/tmp/cvrp-source",
        },
    )
    _write_cvrp_large_twoopt_manifest(run_root, campaign_dir, rounds=1)

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["cvrp_large_twoopt_summary"]
    assert summary["schema_version"] == "scion.postrun_cvrp_large_twoopt_summary.v1"
    assert summary["report_only"] is True
    assert summary["quality_judgment"] is False
    assert summary["decision_features_excluded"] is True
    assert summary["available"] is True
    assert summary["current_run_evidence"] is False
    assert summary["launch_required_before_twoopt_conclusion"] is True
    assert summary["interpretation"] == "prepared_only_launch_required"
    assert summary["handoff_complete"] is True
    assert all(
        item["available"] is True
        for item in summary["handoff_requirements"].values()
    )
    assert summary["evidence_gaps"] == [
        "launch_required_before_bounded_twoopt_conclusion"
    ]
    assert summary["deferred_review_axes"] == list(
        brief_tool.CVRP_LARGE_TWOOPT_REVIEW_AXES
    )
    assert summary["review_axes_actionability"] == (
        "not_actionable_before_launch_current_run_evidence_required"
    )
    assert "## CVRP Large Two-Opt Summary" in markdown
    assert "- Interpretation: prepared_only_launch_required" in markdown
    assert (
        "prepared CVRP large-twoopt research_focus handoff; current-run protocol"
        in markdown
    )
    assert "- Deferred post-launch CVRP bounded two-opt review axes:" in markdown
    assert "- Required CVRP bounded two-opt review axes:" not in markdown
    assert "not_actionable_before_launch_current_run_evidence_required" in markdown
    assert "cvrp_large_twoopt_bounded_constraints_handoff" in markdown
    assert any(
        "cvrp_large_twoopt_summary" in question
        and "incomplete handoff" in question
        for question in brief["required_questions"]
    )
    assert any(
        "not a research-quality" in question
        for question in brief["required_questions"]
    )
    assert not any(
        "warehouse_followup_summary" in question
        for question in brief["required_questions"]
    )


def test_cvrp_large_twoopt_summary_requires_review_inputs_after_protocol_eval(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "cvrp-protocol-eval-missing-inputs"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_cvrp_large_twoopt_manifest(run_root, campaign_dir, rounds=1)
    _write_cvrp_protocol_run(
        run_root,
        campaign_dir,
        mechanism_family="bounded_large_twoopt",
        include_runtime=False,
        include_continuity=False,
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["cvrp_large_twoopt_summary"]
    assert summary["current_run_evidence"] is True
    assert summary["launch_required_before_twoopt_conclusion"] is False
    assert summary["interpretation"] == "protocol_evaluated_review_inputs_incomplete"
    assert "no_protocol_evaluated_candidates" not in summary["evidence_gaps"]
    assert "missing_measurement_effect_summary" not in summary["evidence_gaps"]
    assert "missing_runtime_feedback_summary" in summary["evidence_gaps"]
    assert "missing_research_continuity_summary" in summary["evidence_gaps"]
    assert "missing_large_twoopt_mechanism_signal" not in summary["evidence_gaps"]
    assert "- Interpretation: protocol_evaluated_review_inputs_incomplete" in markdown


def test_cvrp_large_twoopt_summary_rejects_protocol_eval_without_twoopt_signal(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "cvrp-protocol-eval-no-twoopt"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_cvrp_large_twoopt_manifest(run_root, campaign_dir, rounds=1)
    _write_cvrp_protocol_run(
        run_root,
        campaign_dir,
        mechanism_family="regret_insertion",
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["cvrp_large_twoopt_summary"]
    assert summary["current_run_evidence"] is True
    assert summary["handoff_complete"] is True
    assert summary["interpretation"] == "protocol_evaluated_without_large_twoopt_signal"
    assert "missing_large_twoopt_mechanism_signal" in summary["evidence_gaps"]
    assert summary["evidence"]["large_twoopt_mechanism"]["available"] is False
    assert "- Interpretation: protocol_evaluated_without_large_twoopt_signal" in markdown


def test_cvrp_large_twoopt_summary_rejects_continuity_only_twoopt_signal(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "cvrp-protocol-eval-continuity-only-twoopt"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_cvrp_large_twoopt_manifest(run_root, campaign_dir, rounds=1)
    _write_cvrp_protocol_run(
        run_root,
        campaign_dir,
        mechanism_family="regret_insertion",
    )
    report_path = (
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "cvrp.research_efficiency.v1.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["research_shape"]["mechanism_family_breadth"]["families"] = {
        "bounded_large_twoopt": 1
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    brief = brief_tool.build_brief(run_root)

    summary = brief["cvrp_large_twoopt_summary"]
    assert summary["current_run_evidence"] is True
    assert summary["handoff_complete"] is True
    assert summary["interpretation"] == "protocol_evaluated_without_large_twoopt_signal"
    assert "missing_large_twoopt_mechanism_signal" in summary["evidence_gaps"]
    mechanism = summary["evidence"]["large_twoopt_mechanism"]
    assert mechanism["available"] is False
    assert mechanism["protocol_row_count"] == 0
    assert mechanism["protocol_families"] == []
    assert mechanism["continuity_families"] == ["bounded_large_twoopt"]
    markdown = brief_tool.render_markdown(brief)
    assert (
        "- Large two-opt protocol/continuity families / top-row signals: "
        "none / bounded_large_twoopt / 0"
    ) in markdown


def test_cvrp_large_twoopt_summary_accepts_top_row_twoopt_protocol_signal(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "cvrp-protocol-eval-top-row-twoopt"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_cvrp_large_twoopt_manifest(run_root, campaign_dir, rounds=1)
    _write_cvrp_protocol_run(
        run_root,
        campaign_dir,
        mechanism_family="bounded_large_twoopt",
    )
    report_path = (
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "cvrp.research_efficiency.v1.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["protocol_effects_vs_mde"]["mechanism_family_effect_summary"][
        "by_family"
    ] = {}
    report_path.write_text(json.dumps(report), encoding="utf-8")

    brief = brief_tool.build_brief(run_root)

    summary = brief["cvrp_large_twoopt_summary"]
    assert summary["interpretation"] == "bounded_twoopt_review_ready"
    mechanism = summary["evidence"]["large_twoopt_mechanism"]
    assert mechanism["available"] is True
    assert mechanism["protocol_families"] == ["bounded_large_twoopt"]
    assert mechanism["protocol_row_count"] == 1
    assert mechanism["top_row_signal_count"] == 1
    markdown = brief_tool.render_markdown(brief)
    assert (
        "- Large two-opt protocol/continuity families / top-row signals: "
        "bounded_large_twoopt / bounded_large_twoopt / 1"
    ) in markdown


def test_cvrp_large_twoopt_summary_marks_bounded_twoopt_review_ready(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "cvrp-twoopt-review-ready"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_cvrp_large_twoopt_manifest(run_root, campaign_dir, rounds=1)
    _write_cvrp_protocol_run(
        run_root,
        campaign_dir,
        mechanism_family="bounded_large_twoopt",
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["cvrp_large_twoopt_summary"]
    assert summary["available"] is True
    assert summary["current_run_evidence"] is True
    assert summary["handoff_complete"] is True
    assert summary["launch_required_before_twoopt_conclusion"] is False
    assert summary["interpretation"] == "bounded_twoopt_review_ready"
    assert summary["evidence_gaps"] == []
    assert summary["deferred_review_axes"] == []
    assert summary["review_axes_actionability"] == (
        "actionable_current_run_evidence_present"
    )
    assert summary["evidence"]["protocol"]["protocol_evaluated_candidates"] == 1
    mechanism = summary["evidence"]["large_twoopt_mechanism"]
    assert mechanism["available"] is True
    assert mechanism["families"] == ["bounded_large_twoopt"]
    assert mechanism["protocol_families"] == ["bounded_large_twoopt"]
    assert mechanism["continuity_families"] == ["bounded_large_twoopt"]
    assert mechanism["protocol_row_count"] == 2
    assert "- Interpretation: bounded_twoopt_review_ready" in markdown
    assert "- Evidence gaps:\n  - none" in markdown


def test_cvrp_large_twoopt_summary_requires_handoff_before_review_ready(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "cvrp-twoopt-incomplete-handoff"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_cvrp_large_twoopt_manifest(
        run_root,
        campaign_dir,
        rounds=1,
        include_large_twoopt_constraints=False,
    )
    _write_cvrp_protocol_run(
        run_root,
        campaign_dir,
        mechanism_family="bounded_large_twoopt",
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["cvrp_large_twoopt_summary"]
    assert summary["current_run_evidence"] is True
    assert summary["handoff_complete"] is False
    assert summary["interpretation"] == "protocol_evaluated_handoff_incomplete"
    assert "cvrp_large_twoopt_handoff_requirements_incomplete" in summary[
        "evidence_gaps"
    ]
    assert summary["evidence"]["protocol"]["protocol_evaluated_candidates"] == 1
    assert summary["evidence"]["large_twoopt_mechanism"]["available"] is True
    assert "- Interpretation: protocol_evaluated_handoff_incomplete" in markdown


def test_warehouse_followup_summary_distinguishes_quality_blocked_run(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "warehouse-quality-blocked"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "requested_rounds": 1,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 0,
            "protocol_evaluated_candidates": 0,
        },
    )
    _write_warehouse_manifest(run_root, campaign_dir, rounds=1)
    _write_json(
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "warehouse.research_efficiency.v1.json",
        {
            "proposal_quality": {
                "proposal_attempts_total": 3,
                "proposal_attempts_consumed": 3,
                "proposal_quality_blocks": 2,
                "quality_blocks": 2,
                "quality_block_ledger_count": 2,
                "quality_block_reasons": ["missing_direct_effect"],
            },
            "run_status": {
                "run_validity_status": "valid",
                "stopped_reason": "proposal_quality_blocked",
                "run_complete": True,
            },
        },
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["warehouse_followup_summary"]
    assert summary["available"] is True
    assert summary["current_run_evidence"] is True
    assert summary["interpretation"] == (
        "quality_blocked_no_protocol_plateau_conclusion"
    )
    assert summary["launch_required_before_plateau_conclusion"] is False
    assert "quality_blocked_before_protocol_evaluation" in summary["evidence_gaps"]
    assert summary["evidence"]["protocol"]["protocol_evaluated_candidates"] == 0
    assert summary["evidence"]["quality_blocks"]["proposal_quality_blocks"] == 2
    assert "- Interpretation: quality_blocked_no_protocol_plateau_conclusion" in (
        markdown
    )
    assert "- Quality-block reasons: missing_direct_effect=1" in markdown


def test_warehouse_followup_summary_marks_protocol_evaluated_plateau_review_ready(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "warehouse-protocol-evaluated"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "requested_rounds": 1,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
        },
    )
    _write_warehouse_manifest(run_root, campaign_dir, rounds=1)
    _write_json(
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "warehouse.research_efficiency.v1.json",
        {
            "protocol_rows": {
                "protocol_metric_results": 2,
                "protocol_evaluated_candidates": 1,
            },
            "formal_candidates": {
                "formal_screened_candidates": 1,
                "protocol_evaluated_candidates": 1,
            },
            "protocol_effects_vs_mde": {
                "schema_version": "scion.research_efficiency_effect_vs_mde.v1",
                "report_only": True,
                "decision_features_excluded": True,
                "protocol_row_count": 2,
                "rows_at_or_above_mde": 0,
                "rows_with_ci_high_below_mde": 2,
                "max_effect_to_mde_ratio": 0.4,
                "interpretation_counts": {"below_mde": 2},
            },
            "fresh_runtime_replay_drain": {
                "status": "not_selected_no_pending",
                "attempts": 1,
                "executed": 0,
                "skipped": 1,
                "counts_toward_max_rounds": False,
            },
            "stage_transition_drain": {
                "status": "not_started",
                "attempts": 0,
                "counts_toward_max_rounds": False,
                "generates_new_hypothesis": False,
            },
            "research_continuity": {
                "same_mechanism_followup": {
                    "observed_opportunity_count": 1,
                    "selected_same_branch_refinement_count": 1,
                },
                "branch_lesson_usage": {
                    "requirement_count": 1,
                    "satisfied_count": 1,
                    "semantic_gap_count": 0,
                },
                "weak_positive_transfer": {
                    "observed_opportunity_count": 0,
                    "accepted_count": 0,
                },
                "lesson_action_counts": {"preserved_same_branch": 1},
                "research_shape_summary": {
                    "max_branch_depth": 2,
                    "branch_depth_distribution": {"2": 1},
                    "active_shape": "focused_followup",
                },
            },
            "run_status": {
                "run_validity_status": "valid",
                "run_completeness_status": "complete",
                "run_complete": True,
            },
        },
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["warehouse_followup_summary"]
    assert summary["available"] is True
    assert summary["current_run_evidence"] is True
    assert summary["handoff_complete"] is True
    assert summary["launch_required_before_plateau_conclusion"] is False
    assert summary["interpretation"] == "protocol_evaluated_plateau_review_ready"
    assert "quality_blocked_before_protocol_evaluation" not in summary[
        "evidence_gaps"
    ]
    assert "no_protocol_evaluated_candidates" not in summary["evidence_gaps"]
    assert summary["evidence"]["protocol"]["formal_screened_candidates"] == 1
    assert summary["evidence"]["protocol"]["protocol_evaluated_candidates"] == 1
    assert summary["evidence"]["protocol"]["protocol_metric_results"] == 2
    continuity = summary["evidence"]["research_continuity"]
    assert continuity["substantive"] is True
    assert continuity["max_branch_depth"] == 2
    assert continuity["same_mechanism_observed"] == 1
    assert "- Research continuity substantive/depth: `True` / 2" in markdown
    assert "- Research continuity same-mechanism selected/observed: 1 / 1" in (
        markdown
    )
    assert "- Interpretation: protocol_evaluated_plateau_review_ready" in markdown


def test_warehouse_followup_summary_rejects_shallow_continuity_for_plateau_ready(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "warehouse-protocol-evaluated-shallow-continuity"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "requested_rounds": 1,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
        },
    )
    _write_warehouse_manifest(run_root, campaign_dir, rounds=1)
    _write_json(
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "warehouse.research_efficiency.v1.json",
        {
            "protocol_rows": {
                "protocol_metric_results": 2,
                "protocol_evaluated_candidates": 1,
            },
            "formal_candidates": {
                "formal_screened_candidates": 1,
                "protocol_evaluated_candidates": 1,
            },
            "protocol_effects_vs_mde": {
                "schema_version": "scion.research_efficiency_effect_vs_mde.v1",
                "report_only": True,
                "decision_features_excluded": True,
                "protocol_row_count": 2,
                "rows_at_or_above_mde": 0,
                "rows_with_ci_high_below_mde": 2,
                "max_effect_to_mde_ratio": 0.4,
                "interpretation_counts": {"below_mde": 2},
            },
            "fresh_runtime_replay_drain": {
                "status": "not_selected_no_pending",
                "attempts": 1,
                "executed": 0,
                "skipped": 1,
                "counts_toward_max_rounds": False,
            },
            "stage_transition_drain": {
                "status": "not_started",
                "attempts": 0,
                "counts_toward_max_rounds": False,
                "generates_new_hypothesis": False,
            },
            "research_continuity": {
                "branch_lesson_usage": {
                    "requirement_count": 0,
                    "satisfied_count": 0,
                    "semantic_gap_count": 0,
                },
                "research_shape_summary": {
                    "max_branch_depth": 1,
                    "branch_depth_distribution": {"1": 1},
                    "active_shape": "shallow_one_off",
                },
            },
            "run_status": {
                "run_validity_status": "valid",
                "run_completeness_status": "complete",
                "run_complete": True,
            },
        },
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["warehouse_followup_summary"]
    assert summary["current_run_evidence"] is True
    assert summary["handoff_complete"] is True
    assert summary["interpretation"] == (
        "protocol_evaluated_research_continuity_too_shallow"
    )
    assert "warehouse_research_continuity_evidence_too_shallow" in summary[
        "evidence_gaps"
    ]
    continuity = summary["evidence"]["research_continuity"]
    assert continuity["available"] is True
    assert continuity["substantive"] is False
    assert continuity["max_branch_depth"] == 1
    assert continuity["same_mechanism_observed"] == 0
    assert continuity["branch_lessons_required"] == 0
    assert "- Research continuity substantive/depth: `False` / 1" in markdown
    assert "- Research continuity same-mechanism selected/observed: 0 / 0" in (
        markdown
    )
    assert "- Interpretation: protocol_evaluated_research_continuity_too_shallow" in (
        markdown
    )


def test_warehouse_followup_summary_requires_handoff_before_plateau_ready(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "warehouse-protocol-evaluated-incomplete-handoff"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "requested_rounds": 1,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
        },
    )
    _write_warehouse_manifest(
        run_root,
        campaign_dir,
        rounds=1,
        include_v2_checkpoint=False,
    )
    _write_json(
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "warehouse.research_efficiency.v1.json",
        {
            "protocol_rows": {
                "protocol_metric_results": 2,
                "protocol_evaluated_candidates": 1,
            },
            "formal_candidates": {
                "formal_screened_candidates": 1,
                "protocol_evaluated_candidates": 1,
            },
            "protocol_effects_vs_mde": {
                "schema_version": "scion.research_efficiency_effect_vs_mde.v1",
                "report_only": True,
                "decision_features_excluded": True,
                "protocol_row_count": 2,
                "rows_at_or_above_mde": 0,
                "rows_with_ci_high_below_mde": 2,
                "max_effect_to_mde_ratio": 0.4,
                "interpretation_counts": {"below_mde": 2},
            },
            "fresh_runtime_replay_drain": {
                "status": "not_selected_no_pending",
                "attempts": 1,
                "executed": 0,
                "skipped": 1,
                "counts_toward_max_rounds": False,
            },
            "stage_transition_drain": {
                "status": "not_started",
                "attempts": 0,
                "counts_toward_max_rounds": False,
                "generates_new_hypothesis": False,
            },
            "research_continuity": {
                "same_mechanism_followup": {
                    "observed_opportunity_count": 1,
                    "selected_same_branch_refinement_count": 1,
                },
                "branch_lesson_usage": {
                    "requirement_count": 1,
                    "satisfied_count": 1,
                    "semantic_gap_count": 0,
                },
            },
            "run_status": {
                "run_validity_status": "valid",
                "run_completeness_status": "complete",
                "run_complete": True,
            },
        },
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["warehouse_followup_summary"]
    assert summary["current_run_evidence"] is True
    assert summary["handoff_complete"] is False
    assert summary["interpretation"] == "protocol_evaluated_handoff_incomplete"
    assert "warehouse_handoff_requirements_incomplete" in summary["evidence_gaps"]
    assert summary["evidence"]["protocol"]["protocol_evaluated_candidates"] == 1
    assert "- Interpretation: protocol_evaluated_handoff_incomplete" in markdown


def test_warehouse_followup_summary_requires_review_inputs_after_protocol_eval(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "warehouse-protocol-eval-missing-inputs"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "requested_rounds": 1,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
        },
    )
    _write_warehouse_manifest(run_root, campaign_dir, rounds=1)
    _write_json(
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "warehouse.research_efficiency.v1.json",
        {
            "protocol_rows": {
                "protocol_metric_results": 2,
                "protocol_evaluated_candidates": 1,
            },
            "formal_candidates": {
                "formal_screened_candidates": 1,
                "protocol_evaluated_candidates": 1,
            },
            "protocol_effects_vs_mde": {
                "schema_version": "scion.research_efficiency_effect_vs_mde.v1",
                "report_only": True,
                "decision_features_excluded": True,
                "protocol_row_count": 2,
                "rows_at_or_above_mde": 0,
                "rows_with_ci_high_below_mde": 2,
                "max_effect_to_mde_ratio": 0.4,
                "interpretation_counts": {"below_mde": 2},
            },
            "run_status": {
                "run_validity_status": "valid",
                "run_completeness_status": "complete",
                "run_complete": True,
            },
        },
    )

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["warehouse_followup_summary"]
    assert summary["current_run_evidence"] is True
    assert summary["launch_required_before_plateau_conclusion"] is False
    assert summary["interpretation"] == "protocol_evaluated_review_inputs_incomplete"
    assert "no_protocol_evaluated_candidates" not in summary["evidence_gaps"]
    assert "missing_measurement_effect_summary" not in summary["evidence_gaps"]
    assert "missing_runtime_feedback_summary" in summary["evidence_gaps"]
    assert "missing_research_continuity_summary" in summary["evidence_gaps"]
    assert summary["evidence"]["protocol"]["protocol_evaluated_candidates"] == 1
    assert "- Interpretation: protocol_evaluated_review_inputs_incomplete" in markdown


def test_warehouse_followup_summary_keeps_screened_only_out_of_plateau_review(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "warehouse-screened-only"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "requested_rounds": 1,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 0,
        },
    )
    _write_warehouse_manifest(run_root, campaign_dir, rounds=1)

    brief = brief_tool.build_brief(run_root)
    markdown = brief_tool.render_markdown(brief)

    summary = brief["warehouse_followup_summary"]
    assert summary["available"] is True
    assert summary["current_run_evidence"] is True
    assert summary["handoff_complete"] is True
    assert summary["launch_required_before_plateau_conclusion"] is False
    assert summary["interpretation"] == "screened_without_protocol_evaluation"
    assert "no_protocol_evaluated_candidates" in summary["evidence_gaps"]
    assert summary["evidence"]["protocol"]["formal_screened_candidates"] == 1
    assert summary["evidence"]["protocol"]["protocol_evaluated_candidates"] == 0
    assert "- Interpretation: screened_without_protocol_evaluation" in markdown


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


def test_problem_summaries_mark_invalid_infra_only_not_actionable(
    tmp_path: Path,
) -> None:
    warehouse_root = tmp_path / "warehouse-infra-run"
    warehouse_campaign = warehouse_root / "campaign"
    warehouse_campaign.mkdir(parents=True)
    _write_json(
        warehouse_root / "run_status.json",
        {
            "run_validity_status": "invalid_infra_only",
            "run_completeness_status": "incomplete",
            "last_stop_reason": "provider_infra_balance_exhausted",
            "invalid_infra_only": True,
            "requested_rounds": 1,
        },
    )
    _write_warehouse_manifest(warehouse_root, warehouse_campaign, rounds=1)

    warehouse_brief = brief_tool.build_brief(warehouse_root)
    warehouse_markdown = brief_tool.render_markdown(warehouse_brief)
    warehouse_summary = warehouse_brief["warehouse_followup_summary"]

    assert warehouse_brief["lifecycle"]["current_run_evidence"] is False
    assert warehouse_summary["available"] is True
    assert warehouse_summary["current_run_evidence"] is False
    assert warehouse_summary["invalid_infra_only"] is True
    assert warehouse_summary["interpretation"] == (
        "invalid_infra_only_no_research_conclusion"
    )
    assert warehouse_summary["evidence_gaps"] == [
        "invalid_infra_only_no_research_conclusion"
    ]
    assert warehouse_summary["review_axes_actionability"] == (
        "not_actionable_invalid_infra_only"
    )
    assert "infra-only run" in warehouse_markdown
    assert "not_actionable_invalid_infra_only" in warehouse_markdown

    cvrp_root = tmp_path / "cvrp-infra-run"
    cvrp_campaign = cvrp_root / "campaign"
    cvrp_campaign.mkdir(parents=True)
    _write_json(
        cvrp_root / "run_status.json",
        {
            "run_validity_status": "invalid_infra_only",
            "run_completeness_status": "incomplete",
            "last_stop_reason": "provider_infra_balance_exhausted",
            "invalid_infra_only": True,
            "requested_rounds": 1,
        },
    )
    _write_cvrp_large_twoopt_manifest(cvrp_root, cvrp_campaign, rounds=1)

    cvrp_brief = brief_tool.build_brief(cvrp_root)
    cvrp_markdown = brief_tool.render_markdown(cvrp_brief)
    cvrp_summary = cvrp_brief["cvrp_large_twoopt_summary"]

    assert cvrp_brief["lifecycle"]["current_run_evidence"] is False
    assert cvrp_summary["available"] is True
    assert cvrp_summary["current_run_evidence"] is False
    assert cvrp_summary["invalid_infra_only"] is True
    assert cvrp_summary["interpretation"] == (
        "invalid_infra_only_no_research_conclusion"
    )
    assert cvrp_summary["evidence_gaps"] == [
        "invalid_infra_only_no_research_conclusion"
    ]
    assert cvrp_summary["review_axes_actionability"] == (
        "not_actionable_invalid_infra_only"
    )
    assert "infra-only run" in cvrp_markdown
    assert "not_actionable_invalid_infra_only" in cvrp_markdown


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
    assert brief["branch_research_state_summary"]["current_run_evidence"] is False
    assert brief["branch_research_state_summary"]["available"] is False
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


def _write_warehouse_manifest(
    run_root: Path,
    campaign_dir: Path,
    *,
    rounds: int,
    include_v2_checkpoint: bool = True,
) -> None:
    research_focus = {
        "current_question": (
            "Starting from champion v2, determine whether continuous "
            "additional useful research remains or whether this is a "
            "real plateau."
        ),
        "required_evidence": [
            "preserve or improve promotion behavior",
            "inspect branch transfer before judging plateau",
            (
                "distinguish quality-blocked proposals from "
                "protocol-evaluated no-effect candidates"
            ),
            "compare cost_delta and split_delta before split-only claims",
            "explain fast completion through the runtime model",
        ],
        "default_avoid_directions": [
            "baseline",
            "proposal-quality",
            "fast completion",
            "split_delta_sum==0",
            "broad warehouse matrix",
        ],
        "decision_boundary": (
            "Proposal/delegated-analysis guidance only; never enter "
            "DecisionFeatures, Protocol gates, promotion input, or "
            "scheduler state."
        ),
    }
    if include_v2_checkpoint:
        research_focus["accepted_checkpoint"] = (
            "Champion v2 promoted from validation-transfer acceptance."
        )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "campaign_state_mutated": False,
            "scheduler_state_mutated": False,
            "promotion_state_mutated": False,
            "problem_family": "warehouse_delivery",
            "run_root": str(run_root),
            "campaign_dir": str(campaign_dir),
            "research_focus": research_focus,
            "model": {"name": "gpt-5.5", "completion_preflight": True},
            "report_metadata": {
                "control_pair_key": "warehouse-v2-followup",
                "postrun_reports": True,
                "postrun_acceptance_families": [
                    "summaries",
                    "failures",
                    "research_efficiency",
                    "manifests",
                    "analysis_brief",
                    "inventory",
                    "rebuild",
                ],
            },
            "execution": {"rounds": rounds},
            "acceptance_focus": [
                "Distinguish real plateau from missed continuous-promotion opportunities."
            ],
        },
    )


def _write_cvrp_large_twoopt_manifest(
    run_root: Path,
    campaign_dir: Path,
    *,
    rounds: int,
    include_large_twoopt_constraints: bool = True,
) -> None:
    research_focus = {
        "measurement_opportunity_diagnostics": {
            "screening_mde_at_power_80": 9.9,
            "practical_screen_delta": 2.0,
            "reason_codes": [
                "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA",
                "TRAJECTORY_DIVERGENT_LOW_SNR",
                "BUDGET_EXHAUSTING_RUNTIME_REPORT_ONLY",
            ],
        },
        "measurable_opportunity_classes": [
            "large_instance_intra_route_two_opt_seed",
            "bounded_local_search_variant",
            "construction_seed_portfolio",
            "destroy_repair_selection",
        ],
        "default_avoid_directions": [
            "broad VNS removal",
            "pure ALNS/no-polish",
            "initial-VNS disablement",
            "unbounded large-instance two-opt fallback",
            "cadence-2",
            "share70 cap",
            "route-merge absorption",
            "demand-slack regret insertion",
            "cross-route 2-opt reconnect",
            "cluster-biased worst removal",
            "route-limit seed diversification",
        ],
        "route_merge_exception_rule": (
            "Require direct objective evidence for route merge claims."
        ),
        "construction_seed_rule": (
            "Require same-run seed baseline or same-mechanism accepted delta."
        ),
        "decision_boundary": (
            "Proposal guidance only; never enter DecisionFeatures, "
            "Protocol gates, promotion input, or scheduler state."
        ),
    }
    if include_large_twoopt_constraints:
        research_focus["large_instance_two_opt_constraints"] = (
            _large_twoopt_constraints()
        )
    _write_json(
        run_root / "prepared_run_manifest.v1.json",
        {
            "schema_version": "scion.launcher_prepared_run_manifest.v1",
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "campaign_state_mutated": False,
            "scheduler_state_mutated": False,
            "promotion_state_mutated": False,
            "problem_family": "cvrp",
            "run_root": str(run_root),
            "campaign_dir": str(campaign_dir),
            "research_focus": research_focus,
            "model": {"name": "gpt-5.5", "completion_preflight": True},
            "report_metadata": {
                "control_pair_key": "cvrp.large-twoopt-bounded:rep01",
                "postrun_reports": True,
                "postrun_acceptance_families": [
                    "summaries",
                    "failures",
                    "research_efficiency",
                    "manifests",
                    "analysis_brief",
                    "inventory",
                    "rebuild",
                ],
            },
            "execution": {"rounds": rounds},
            "acceptance_focus": [
                "Review bounded large-instance intra-route two-opt evidence."
            ],
        },
    )


def _large_twoopt_constraints() -> dict[str, object]:
    return {
        "schema_version": "scion.cvrp_large_instance_two_opt_constraints.v1",
        "scope": "proposal_only_prepared_handoff",
        "seed_report": (
            "scion/docs/experiments/v0.4/"
            "v04-vrp-large-instance-two-opt-seed-evidence-20260618.md"
        ),
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "implementation_constraints": [
            "derive a deadline from the solver time_limit and monotonic start time",
            "check wall-clock remaining time before each route and sweep",
            "do not call unbounded two_opt_intra above the vns_threshold",
        ],
        "required_pair_evidence": [
            "total_distance delta by case and seed",
            "feasibility before and after",
            "route count before and after",
            "wall-clock elapsed status",
        ],
        "default_reject_directions": [
            "unbounded two_opt_intra fallback",
            "activation claims without wall-clock evidence",
        ],
    }


def _write_cvrp_protocol_run(
    run_root: Path,
    campaign_dir: Path,
    *,
    mechanism_family: str,
    include_runtime: bool = True,
    include_continuity: bool = True,
) -> None:
    _write_json(
        run_root / "run_status.json",
        {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "requested_rounds": 1,
        },
    )
    _write_json(
        campaign_dir / "campaign_summary.json",
        {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
        },
    )
    payload: dict[str, object] = {
        "protocol_rows": {
            "effective_protocol_rounds": 1,
            "protocol_metric_results": 2,
            "protocol_evaluated_candidates": 1,
            "stage_counts": {"screening": 2, "validation": 0, "frozen": 0},
        },
        "formal_candidates": {
            "formal_screened_candidates": 1,
            "protocol_evaluated_candidates": 1,
        },
        "formal_candidate_artifacts": {
            "row_count": 1,
            "index_status": "available",
            "unreadable_rows": 0,
        },
        "measurement_readiness": {
            "status": "ready",
            "reason_code": "ok",
            "mde_at_power_80": 9.9,
            "signal_to_noise_tier": "low_power",
        },
        "protocol_effects_vs_mde": {
            "schema_version": "scion.research_efficiency_effect_vs_mde.v1",
            "report_only": True,
            "decision_features_excluded": True,
            "measurement_readiness_status": "ready",
            "mde_at_power_80": 9.9,
            "interpretation": "has_positive_protocol_effect_at_or_above_mde",
            "protocol_row_count": 2,
            "rows_at_or_above_mde": 1,
            "rows_with_ci_high_below_mde": 1,
            "positive_rows": 1,
            "nonpositive_rows": 1,
            "max_effect_to_mde_ratio": 1.1,
            "mechanism_family_effect_summary": {
                "schema_version": "scion.mechanism_family_effect_summary.v1",
                "report_only": True,
                "decision_features_excluded": True,
                "mapping_status": "available",
                "mapped_row_count": 2,
                "unmapped_row_count": 0,
                "mechanism_family_count": 1,
                "by_family": {
                    mechanism_family: {
                        "protocol_row_count": 2,
                        "rows_with_median_delta": 2,
                        "positive_rows": 1,
                        "nonpositive_rows": 1,
                        "rows_at_or_above_mde": 1,
                        "rows_below_mde": 1,
                        "rows_with_ci_high_below_mde": 1,
                        "max_median_delta": 11.0,
                        "max_effect_to_mde_ratio": 1.1,
                    }
                },
            },
            "top_rows_by_effect_to_mde": [
                {
                    "round": 1,
                    "branch_id": "branch-1",
                    "mechanism_family": mechanism_family,
                    "stage": "screening",
                    "decision": "continue_explore",
                    "gate_outcome": "pass",
                    "median_delta": 11.0,
                    "effect_to_mde_ratio": 1.1,
                    "positive_effect_at_or_above_mde": True,
                }
            ],
        },
        "run_status": {
            "run_validity_status": "valid",
            "run_completeness_status": "complete",
            "run_complete": True,
        },
    }
    if include_runtime:
        payload["fresh_runtime_replay_drain"] = {
            "status": "not_selected_no_pending",
            "attempts": 1,
            "executed": 0,
            "skipped": 1,
            "counts_toward_max_rounds": False,
        }
        payload["stage_transition_drain"] = {
            "status": "not_started",
            "attempts": 0,
            "counts_toward_max_rounds": False,
            "generates_new_hypothesis": False,
        }
    if include_continuity:
        payload["research_continuity"] = {
            "same_mechanism_followup": {
                "observed_opportunity_count": 1,
                "selected_same_branch_refinement_count": 1,
            },
            "branch_lesson_usage": {
                "requirement_count": 1,
                "satisfied_count": 1,
                "semantic_gap_count": 0,
            },
            "weak_positive_transfer": {
                "observed_opportunity_count": 0,
                "accepted_count": 0,
            },
            "lesson_action_counts": {"preserved_same_branch": 1},
            "research_shape_summary": {
                "max_branch_depth": 2,
                "branch_depth_distribution": {"2": 1},
                "active_shape": "focused_followup",
                "mechanism_family_count": 1,
            },
        }
        payload["research_shape"] = {
            "mechanism_family_breadth": {
                "family_count": 1,
                "families": {mechanism_family: 1},
            }
        }
    _write_json(
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "cvrp.research_efficiency.v1.json",
        payload,
    )


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
