from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


TOOL_PATH = Path(__file__).parents[2] / "tools" / "postrun_artifact_inventory.py"
SPEC = importlib.util.spec_from_file_location("postrun_artifact_inventory", TOOL_PATH)
assert SPEC is not None
inventory_tool = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(inventory_tool)


def test_inventory_json_with_db_trace_index_and_traces(tmp_path: Path) -> None:
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
            "last_stop_reason": "max_rounds_exhausted",
            "wrapper_exit_status": 0,
            "requested_rounds": 2,
        },
    )
    (run_root / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (run_root / "launch.env").write_text("SCION_MODEL=gpt-5.5\n", encoding="utf-8")
    (run_root / "command.txt").write_text("./run.sh\n", encoding="utf-8")
    (run_root / "run.log").write_text(
        "\n".join(
            [
                "POSTRUN_REPORTS_STARTED_AT:2026-06-18T00:00:00Z",
                "POSTRUN_REPORT_DIR:/tmp/run-a/postrun_acceptance",
                "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED:expected=a actual=b paths=docs",
                "POSTRUN_REPORTS_FINISHED_AT:2026-06-18T00:01:00Z",
            ]
        ),
        encoding="utf-8",
    )
    (run_root / "exit.txt").write_text(
        "\n".join(
            [
                "WRAPPER_EXIT_STATUS:0",
                "POSTRUN_ACCEPTANCE_DIR:/tmp/run-a/postrun_acceptance",
            ]
        ),
        encoding="utf-8",
    )
    for subdir, filename in (
        ("summaries", "normal.summary.json"),
        ("failures", "normal.failures.json"),
        ("research_efficiency", "normal.research_efficiency.v1.json"),
        ("manifests", "normal.proposal_trajectory_manifest.v1.json"),
    ):
        _write_json(run_root / "postrun_acceptance" / subdir / filename, {})
    _write_json(
        campaign_dir / "status.json",
        {
            "effective_rounds_completed": 2,
            "screened_experiments": 1,
            "proposal_attempts_total": 3,
        },
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
            "session_count": 1,
            "trace_count": 3,
            "sessions": [
                {
                    "session_id": "s-1",
                    "branch_id": "branch-1",
                    "traces": [
                        {"trace_id": "t-tool", "request_kind": "tool_selection"},
                        {"trace_id": "t-hyp", "request_kind": "hypothesis"},
                        {"trace_id": "t-code", "request_kind": "code"},
                    ],
                }
            ],
        },
    )
    _write_json(
        sessions_dir / "agentic_session_index.json",
        {"sessions": [{"session_id": "s-1", "branch_id": "branch-1"}]},
    )
    _write_json(
        traces_dir / "20260606T000000_tool_selection_branch_1.json",
        {"request_kind": "tool_selection", "ok": True, "branch_id": "branch-1"},
    )
    _write_json(
        traces_dir / "20260606T000000_hypothesis_branch_1.json",
        {"request_kind": "hypothesis", "ok": True, "branch_id": "branch-1"},
    )
    _write_json(
        traces_dir / "20260606T000001_code_branch_1.json",
        {"trace_kind": "code", "status": "failed", "branch_id": "branch-1"},
    )
    _write_db(campaign_dir / "scion.db")

    data = inventory_tool.build_inventory(run_root)

    assert data["run_root"] == str(run_root)
    assert data["campaign_dir"] == str(campaign_dir)
    assert data["run_name"] == "normal-run"
    assert data["validity"]["invalid_infra_only"] is False
    assert data["counters"]["requested_rounds"] == 2
    assert data["counters"]["effective_rounds_completed"] == 2
    assert data["counters"]["formal_screened_candidates"] == 1
    assert data["llm_traces"]["trace_count"] == 3
    assert data["llm_traces"]["by_kind"] == {
        "code": 1,
        "hypothesis": 1,
        "tool_selection": 1,
    }
    assert data["llm_traces"]["by_status"] == {"failed": 1, "ok": 2}
    assert data["llm_traces"]["index_trace_count"] == 3
    assert data["llm_traces"]["index_session_count"] == 1
    assert data["launcher"]["artifacts"] == {
        "command.txt": True,
        "exit.txt": True,
        "launch.env": True,
        "run.log": True,
        "run.sh": True,
    }
    assert data["launcher"]["status_fields"] == {"wrapper_exit_status": 0}
    assert data["launcher"]["run_log_markers"] == {
        "GIT_COMMIT_DOC_ONLY_MISMATCH_ALLOWED": 1,
        "POSTRUN_REPORT_DIR": 1,
        "POSTRUN_REPORTS_FINISHED_AT": 1,
        "POSTRUN_REPORTS_STARTED_AT": 1,
    }
    assert data["launcher"]["exit_markers"] == {
        "POSTRUN_ACCEPTANCE_DIR": 1,
        "WRAPPER_EXIT_STATUS": 1,
    }
    assert data["postrun_reports"]["exists"] is True
    assert data["postrun_reports"]["counts"] == {
        "failures": 1,
        "manifests": 1,
        "research_efficiency": 1,
        "summaries": 1,
    }
    assert data["analysis_handoff"] == (
        "scion/docs/operations/postrun-analysis-handoff.md"
    )

    assert len(data["branches"]) == 1
    branch = data["branches"][0]
    assert branch["branch_id"] == "branch-1"
    assert branch["state"] == "ready_validate"
    assert branch["lineage_id"] == "lineage-1"
    assert branch["base_champion_hash"] == "basehash"
    assert branch["current_code_hash"] == "codehash"
    assert branch["best_quality_checkpoint_id"] == "checkpoint-best"
    assert branch["last_valid_checkpoint_id"] == "checkpoint-last"
    assert branch["rollback_count"] == 1
    assert branch["failure_codes"] == ["CONTRACT"]
    assert branch["hypothesis_count"] == 2
    assert branch["event_count"] == 3
    assert branch["session_count"] == 1
    assert branch["trace_count"] == 3
    assert data["events"]["by_kind"] == {"decision": 1, "experiment": 2}
    assert data["events"]["by_decision"] == {
        "continue_explore": 1,
        "queue_validate": 1,
    }
    assert data["events"]["by_stage"] == {"screening": 2}
    assert data["hypotheses"]["count"] == 2
    assert data["hypotheses"]["by_status"] == {"active": 1, "rejected": 1}
    assert data["hypotheses"]["by_action"] == {"create_new": 1, "modify": 1}
    assert data["hypotheses"]["by_change_locus"] == {"solver_design": 2}


def test_invalid_infra_only_markdown_without_db(tmp_path: Path) -> None:
    run_root = tmp_path / "infra-run"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_json(
        run_root / "run_status.json",
        {
            "run_name": "infra-run",
            "run_validity_status": "invalid_infra_only",
            "run_completeness_status": "incomplete",
            "last_stop_reason": "provider_infra_balance_exhausted",
            "invalid_infra_only": True,
        },
    )

    data = inventory_tool.build_inventory(run_root)
    markdown = inventory_tool.render_markdown(data)

    assert data["validity"]["invalid_infra_only"] is True
    assert data["branches"] == []
    assert data["llm_traces"]["trace_count"] == 0
    assert "INVALID INFRA-ONLY RUN" in markdown
    assert "does not judge research quality" in markdown


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
