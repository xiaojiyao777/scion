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
            "measurement_readiness": {"status": "ready"},
            "protocol_effects_vs_mde": {"mde_source": "readiness"},
            "fresh_runtime_replay_drain": {"attempts": 1},
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
                        {"visibility_ledger_digest": "visibility-ledger-1"}
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
