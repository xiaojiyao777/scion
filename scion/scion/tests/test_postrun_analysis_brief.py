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
            "fresh_runtime_replay_drain": {"attempts": 1},
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
    assert "## Measurement Effect Summary" in markdown
    assert (
        "| normal.research_efficiency.v1.json | ready | 9.9 | "
        "has_positive_protocol_effect_at_or_above_mde | 2 | 1 | 1 | 1.212121 |"
        in markdown
    )
    assert "## Research Continuity Summary" in markdown
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
    assert brief["measurement_effect_summary"]["current_run_evidence"] is False
    assert brief["measurement_effect_summary"]["available"] is False
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
    assert brief["measurement_effect_summary"]["current_run_evidence"] is False
    assert brief["measurement_effect_summary"]["available"] is False
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
